import re
import unicodedata
from pypdf import PdfReader

from config import BASE_DIR
from core.database import get_connection, init_db


def normalizar_texto(texto: str) -> str:
    """
    Convierte a minusculas, elimina acentos/diacriticos y colapsa espacios multiples.
    Ideal para comparaciones consistentes con Levenshtein.
    """
    texto = texto.lower()
    # descomponer caracteres acentuados y quitar marcas diacriticas (á -> a, ñ -> n)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    # mantener letras, numeros y espacios basicos
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def limpiar_texto_original(texto: str) -> str:
    """Limpia saltos de linea y espacios excesivos conservando puntuacion y acentos."""
    return re.sub(r"\s+", " ", texto).strip()


def dividir_en_fragmentos(texto_pagina: str, max_chars: int = 450) -> list[str]:
    """
    Divide el texto de una pagina en fragmentos contextuales de tamano manejable
    sin cortar palabras a la mitad.
    """
    texto_limpio = limpiar_texto_original(texto_pagina)
    if not texto_limpio:
        return []

    palabras = texto_limpio.split(" ")
    fragmentos = []
    bloque_actual = []
    longitud_actual = 0

    for palabra in palabras:
        # +1 por el espacio entre palabras
        if longitud_actual + len(palabra) + 1 > max_chars and bloque_actual:
            fragmentos.append(" ".join(bloque_actual))
            bloque_actual = [palabra]
            longitud_actual = len(palabra)
        else:
            bloque_actual.append(palabra)
            longitud_actual += len(palabra) + 1

    if bloque_actual:
        fragmentos.append(" ".join(bloque_actual))

    return fragmentos


def indexar_documentos_pendientes() -> dict:
    """
    Procesa todos los documentos en estado 'pendiente', extrae su texto,
    guarda los fragmentos en SQLite y reporta los PDFs ilegibles o sin texto.
    """
    init_db()

    resumen = {
        "procesados": 0,
        "indexados": 0,
        "sin_texto": 0,
        "fragmentos_creados": 0,
    }

    with get_connection() as conn:
        pendientes = conn.execute(
            """
            SELECT id, titulo_enlace, ruta_local
            FROM documentos
            WHERE estado_extraccion = 'pendiente'
            ORDER BY id ASC;
            """
        ).fetchall()

    if not pendientes:
        print("No hay documentos pendientes por indexar.")
        return resumen

    print(f"\n=== Indexando {len(pendientes)} documento(s) pendiente(s) ===")

    for doc in pendientes:
        doc_id = doc["id"]
        titulo = doc["titulo_enlace"]
        ruta_fisica = BASE_DIR / doc["ruta_local"]
        resumen["procesados"] += 1

        if not ruta_fisica.exists():
            _actualizar_estado(doc_id, "sin_texto", "Archivo PDF no encontrado en disco.")
            resumen["sin_texto"] += 1
            print(f"  [SIN TEXTO] {titulo} -> Archivo no encontrado.")
            continue

        try:
            reader = PdfReader(str(ruta_fisica))
            fragmentos_a_insertar = []

            for num_pagina, pagina in enumerate(reader.pages, start=1):
                texto_crudo = pagina.extract_text() or ""
                bloques = dividir_en_fragmentos(texto_crudo)

                for bloque in bloques:
                    norm = normalizar_texto(bloque)
                    if len(norm) >= 10:  # ignorar fragmentos basura de 1 o 2 letras
                        fragmentos_a_insertar.append((doc_id, num_pagina, bloque, norm))

            if not fragmentos_a_insertar:
                _actualizar_estado(
                    doc_id,
                    "sin_texto",
                    "No se pudo extraer texto (posible PDF escaneado como imagen o vacío).",
                )
                resumen["sin_texto"] += 1
                print(f"  [SIN TEXTO] {titulo} -> Sin capa de texto extraíble.")
                continue

            with get_connection() as conn:
                # limpiar fragmentos previos por seguridad antes de insertar
                conn.execute("DELETE FROM fragmentos WHERE documento_id = ?;", (doc_id,))
                conn.executemany(
                    """
                    INSERT INTO fragmentos (documento_id, numero_pagina, texto_original, texto_normalizado)
                    VALUES (?, ?, ?, ?);
                    """,
                    fragmentos_a_insertar,
                )
                conn.execute(
                    """
                    UPDATE documentos
                    SET estado_extraccion = 'indexado',
                        mensaje_estado = ?
                    WHERE id = ?;
                    """,
                    (f"Indexado correctamente ({len(fragmentos_a_insertar)} fragmentos).", doc_id),
                )
                conn.commit()

            resumen["indexados"] += 1
            resumen["fragmentos_creados"] += len(fragmentos_a_insertar)
            print(f"  [OK] {titulo} -> {len(fragmentos_a_insertar)} fragmentos indexados.")

        except Exception as e:
            _actualizar_estado(doc_id, "sin_texto", f"Error al leer PDF: {e}")
            resumen["sin_texto"] += 1
            print(f"  [ERROR] {titulo} -> {e}")

    print("\n=== Resumen de Indexación ===")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")

    return resumen


def _actualizar_estado(doc_id: int, estado: str, mensaje: str) -> None:
    """Actualiza el estado de extraccion y mensaje de un documento."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE documentos
            SET estado_extraccion = ?, mensaje_estado = ?
            WHERE id = ?;
            """,
            (estado, mensaje, doc_id),
        )
        conn.commit()

if __name__ == "__main__":
    indexar_documentos_pendientes()