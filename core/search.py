import Levenshtein

from config import UMBRAL_SIMILITUD, MAX_RESULTADOS
from core.database import get_connection
from core.indexer import normalizar_texto

def calcular_similitud(consulta_norm: str, texto_norm: str) -> float:
    """
    Calcula la similitud (0.0 a 1.0) entre una consulta normalizada y un texto
    utilizando la biblioteca Levenshtein.
    """
    if not consulta_norm or not texto_norm:
        return 0.0

    # coincidencia exacta de subcadena
    if consulta_norm in texto_norm:
        return 1.0

    palabras_consulta = consulta_norm.split()
    palabras_texto = texto_norm.split()

    if not palabras_consulta or not palabras_texto:
        return 0.0

    # similitud por palabras individuales, tolera errores tipograficos y orden distinto
    puntajes_palabras = []
    for p_consulta in palabras_consulta:
        mejor_ratio = max(
            Levenshtein.ratio(p_consulta, p_texto) for p_texto in palabras_texto
        )
        puntajes_palabras.append(mejor_ratio)

    similitud_por_palabras = sum(puntajes_palabras) / len(puntajes_palabras)

    # similitud por ventana deslizante de frases (para consultas de 2+ palabras)
    similitud_ventana = 0.0
    n = len(palabras_consulta)
    if n > 1 and len(palabras_texto) >= n:
        for i in range(len(palabras_texto) - n + 1):
            ventana = " ".join(palabras_texto[i : i + n])
            ratio = Levenshtein.ratio(consulta_norm, ventana)
            if ratio > similitud_ventana:
                similitud_ventana = ratio

    return max(similitud_por_palabras, similitud_ventana)

def buscar_en_indice(
    consulta: str,
    umbral: float = UMBRAL_SIMILITUD,
    limite: int = MAX_RESULTADOS,
) -> list[dict]:
    """
    Busca la consulta sobre los fragmentos almacenados en SQLite.
    Retorna los resultados ordenados de mayor a menor similitud.
    """
    consulta_norm = normalizar_texto(consulta)
    if not consulta_norm:
        return []

    with get_connection() as conn:
        filas = conn.execute(
            """
            SELECT
                f.id AS fragmento_id,
                f.documento_id,
                f.numero_pagina,
                f.texto_original,
                f.texto_normalizado,
                d.titulo_enlace,
                d.url_origen
            FROM fragmentos f
            INNER JOIN documentos d ON f.documento_id = d.id
            WHERE d.estado_extraccion = 'indexado';
            """
        ).fetchall()

    resultados = []
    for fila in filas:
        # evaluar similitud contra el fragmento y contra el titulo del acta
        sim_fragmento = calcular_similitud(consulta_norm, fila["texto_normalizado"])
        sim_titulo = calcular_similitud(consulta_norm, normalizar_texto(fila["titulo_enlace"]))
        similitud = max(sim_fragmento, sim_titulo)

        if similitud >= umbral:
            resultados.append(
                {
                    "documento_id": fila["documento_id"],
                    "titulo_enlace": fila["titulo_enlace"],
                    "url_origen": fila["url_origen"],
                    "numero_pagina": fila["numero_pagina"],
                    "texto_original": fila["texto_original"],
                    "similitud": round(similitud, 4),
                    "porcentaje": round(similitud * 100, 1),
                }
            )

    # ordenar de mayor a menor similitud
    resultados.sort(key=lambda r: r["similitud"], reverse=True)
    return resultados[:limite]

if __name__ == "__main__":
    # prueba desde consola
    while True:
        termino = input("\nEscribe una búsqueda (o Enter para salir): ").strip()
        if not termino:
            break

        encontrados = buscar_en_indice(termino)
        if not encontrados:
            print("No se encontraron coincidencias relevantes.")
            continue

        print(f"Se encontraron {len(encontrados)} resultado(s) (mostrando top 5):")
        for idx, res in enumerate(encontrados[:5], start=1):
            print(f"\n{idx}. [{res['porcentaje']}%] {res['titulo_enlace']} (Pág. {res['numero_pagina']})")
            print(f"   URL: {res['url_origen']}")
            print(f"   Fragmento: {res['texto_original'][:180]}...")