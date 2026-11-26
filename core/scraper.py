import hashlib
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

from config import (
    BASE_DIR,
    PDF_DIR,
    MAX_PROFUNDIDAD,
    MAX_PAG_POR_SEMILLA,
    PAUSA_ENTRE_PETICIONES,
    TIMEOUT_PETICION,
)
from core.database import get_connection, init_db, obtener_urls_semilla

# extensiones que ignoramos al seguir enlaces HTML
EXTENSIONES_IGNORADAS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".zip", ".rar", ".mp4", ".mp3", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BuscadorActasUNISON/1.0; +ProyectoAcademico)"
}


def normalizar_url(url: str) -> str:
    """Elimina fragmentos (#seccion) y espacios en blanco de una URL."""
    parsed = urlparse(url.strip())
    return parsed._replace(fragment="").geturl()


def es_url_pdf(url: str) -> bool:
    """Determina si la ruta de la URL apunta a un archivo PDF."""
    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


def generar_nombre_unico(url_pdf: str) -> str:
    """
    Genera un nombre de archivo seguro y unico usando un hash corto de la URL
    para evitar sobrescribir documentos distintos con el mismo nombre.
    """
    hash_corto = hashlib.md5(url_pdf.encode("utf-8")).hexdigest()[:8]
    nombre_original = Path(unquote(urlparse(url_pdf).path)).name

    if not nombre_original or not nombre_original.lower().endswith(".pdf"):
        nombre_original = "documento.pdf"

    # limpiar caracteres no seguros para nombres de archivo en Windows o Linux
    nombre_limpio = re.sub(r"[^a-zA-Z0-9._-]", "_", nombre_original)
    # limitar longitud para evitar errores de ruta larga en Windows
    if len(nombre_limpio) > 80:
        nombre_limpio = nombre_limpio[-80:]

    return f"{hash_corto}_{nombre_limpio}"


def es_enlace_pertinente(url_destino: str, url_semilla: str) -> bool:
    """
    Evita visitas innecesarias a sitios externos o secciones ajenas a las actas.
    Permite navegar dentro del mismo dominio y bajo la ruta base de la semilla
    (o rutas que contengan palabras clave relacionadas con actas).
    """
    parsed_dest = urlparse(url_destino)
    parsed_seed = urlparse(url_semilla)

    if parsed_dest.scheme not in ("http", "https"):
        return False

    # mantenerse en el mismo dominio
    if parsed_dest.netloc.lower() != parsed_seed.netloc.lower():
        return False

    # ignorar archivos estaticos o multimedia
    ext = Path(parsed_dest.path.lower()).suffix
    if ext in EXTENSIONES_IGNORADAS:
        return False

    # si es un PDF dentro del mismo dominio, siempre es pertinente
    if ext == ".pdf":
        return True

    # para paginas HTML intermedias, restringir a la ruta base de la semilla o palabras clave
    ruta_semilla = parsed_seed.path.rstrip("/").lower()
    ruta_dest = parsed_dest.path.lower()

    if ruta_semilla and ruta_dest.startswith(ruta_semilla):
        return True

    palabras_clave = ("acta", "sesion", "consejo", "acuerdo", "minuta", "colegiado")
    return any(palabra in ruta_dest for palabra in palabras_clave)


def documento_ya_disponible(url_pdf: str) -> bool:
    """
    Verifica en SQLite si la URL ya fue descargada y si el archivo fisico
    sigue existiendo en la carpeta local.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT ruta_local, estado_extraccion FROM documentos WHERE url_origen = ?",
            (url_pdf,),
        ).fetchone()

    if not row:
        return False

    if row["estado_extraccion"] == "error_descarga":
        return False

    ruta_fisica = BASE_DIR / row["ruta_local"]
    return ruta_fisica.exists() and ruta_fisica.stat().st_size > 0


def registrar_documento(
    url_origen: str,
    titulo_enlace: str,
    nombre_archivo_local: str,
    ruta_local: str,
    estado: str = "pendiente",
    mensaje: str | None = None,
) -> None:
    """Inserta o actualiza el registro de un documento en SQLite."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO documentos (
                url_origen, titulo_enlace, nombre_archivo_local,
                ruta_local, estado_extraccion, mensaje_estado
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_origen) DO UPDATE SET
                titulo_enlace = excluded.titulo_enlace,
                nombre_archivo_local = excluded.nombre_archivo_local,
                ruta_local = excluded.ruta_local,
                estado_extraccion = excluded.estado_extraccion,
                mensaje_estado = excluded.mensaje_estado,
                fecha_descarga = CURRENT_TIMESTAMP;
            """,
            (url_origen, titulo_enlace, nombre_archivo_local, ruta_local, estado, mensaje),
        )
        conn.commit()


def descargar_pdf(session: requests.Session, url_pdf: str, titulo_enlace: str) -> str:
    """
    Descarga un PDF si no existe localmente.
    Retorna: 'descargado', 'omitido' o 'error'.
    """
    if documento_ya_disponible(url_pdf):
        return "omitido"

    nombre_unico = generar_nombre_unico(url_pdf)
    ruta_absoluta = PDF_DIR / nombre_unico
    ruta_relativa = str(ruta_absoluta.relative_to(BASE_DIR)).replace("\\", "/")

    try:
        time.sleep(PAUSA_ENTRE_PETICIONES)
        resp = session.get(url_pdf, timeout=TIMEOUT_PETICION, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type and not es_url_pdf(url_pdf):
            raise ValueError(f"El recurso no es un PDF válido (Content-Type: {content_type})")

        with open(ruta_absoluta, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        registrar_documento(
            url_origen=url_pdf,
            titulo_enlace=titulo_enlace or nombre_unico,
            nombre_archivo_local=nombre_unico,
            ruta_local=ruta_relativa,
            estado="pendiente",
            mensaje="Descargado correctamente",
        )
        print(f"  [OK] Descargado: {titulo_enlace} -> {nombre_unico}")
        return "descargado"

    except Exception as e:
        registrar_documento(
            url_origen=url_pdf,
            titulo_enlace=titulo_enlace or nombre_unico,
            nombre_archivo_local=nombre_unico,
            ruta_local=ruta_relativa,
            estado="error_descarga",
            mensaje=str(e),
        )
        print(f"  [ERROR] No se pudo descargar {url_pdf}: {e}")
        return "error"


def ejecutar_scraping() -> dict:
    """
    Recorre todas las URLs semilla activas, descubre enlaces a PDFs
    y los descarga evitando duplicados.
    """
    init_db()
    semillas = obtener_urls_semilla(solo_activas=True)

    resumen = {
        "semillas_procesadas": 0,
        "paginas_visitadas": 0,
        "descargados": 0,
        "omitidos": 0,
        "errores": 0,
    }

    session = requests.Session()
    session.headers.update(HEADERS)

    for semilla in semillas:
        url_inicial = normalizar_url(semilla["url"])
        print(f"\n=== Escaneando semilla: {url_inicial} ===")
        resumen["semillas_procesadas"] += 1

        cola = deque([(url_inicial, 0)])
        visitadas = {url_inicial}
        paginas_esta_semilla = 0

        while cola and paginas_esta_semilla < MAX_PAG_POR_SEMILLA:
            url_actual, profundidad = cola.popleft()

            try:
                time.sleep(PAUSA_ENTRE_PETICIONES)
                resp = session.get(url_actual, timeout=TIMEOUT_PETICION)
                resp.raise_for_status()
            except Exception as e:
                print(f"  [ERROR] No se pudo acceder a {url_actual}: {e}")
                resumen["errores"] += 1
                continue

            paginas_esta_semilla += 1
            resumen["paginas_visitadas"] += 1
            print(f"[Nivel {profundidad}] Visitando: {url_actual}")

            # si la propia URL semilla apunta directo a un PDF
            if "application/pdf" in resp.headers.get("Content-Type", "").lower() or es_url_pdf(url_actual):
                resultado = descargar_pdf(session, url_actual, Path(urlparse(url_actual).path).name)
                if resultado == "descargado":
                    resumen["descargados"] += 1
                elif resultado == "omitido":
                    resumen["omitidos"] += 1
                else:
                    resumen["errores"] += 1
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            for enlace in soup.find_all("a", href=True):
                href = enlace["href"].strip()
                if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue

                url_completa = normalizar_url(urljoin(url_actual, href))
                texto_enlace = " ".join(enlace.get_text(strip=True).split())

                # es un enlace a PDF
                if es_url_pdf(url_completa):
                    titulo = texto_enlace or Path(unquote(urlparse(url_completa).path)).name
                    resultado = descargar_pdf(session, url_completa, titulo)
                    if resultado == "descargado":
                        resumen["descargados"] += 1
                    elif resultado == "omitido":
                        resumen["omitidos"] += 1
                    else:
                        resumen["errores"] += 1

                # es una pagina intermedia pertinente dentro del limite de profundidad
                elif (
                    profundidad < MAX_PROFUNDIDAD
                    and url_completa not in visitadas
                    and es_enlace_pertinente(url_completa, url_inicial)
                ):
                    visitadas.add(url_completa)
                    cola.append((url_completa, profundidad + 1))

    print("\n=== Resumen de Scraping ===")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")

    return resumen


if __name__ == "__main__":
    ejecutar_scraping()