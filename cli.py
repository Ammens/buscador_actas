import argparse

from core.database import agregar_url_semilla, init_db, obtener_urls_semilla
from core.indexer import indexar_documentos_pendientes
from core.scraper import ejecutar_scraping
from core.search import buscar_en_indice


def main():
    parser = argparse.ArgumentParser(
        description="CLI - Sistema de recopilación y búsqueda de actas en PDF (UNISON)"
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    # subcomando scrape
    subparsers.add_parser("scrape", help="Descarga PDFs nuevos desde las URLs semilla activas.")

    # subcomando index
    subparsers.add_parser("index", help="Extrae texto e indexa los PDFs pendientes en SQLite.")

    # ubcomando update
    subparsers.add_parser("update", help="Ejecuta scraping y luego indexación en un solo paso.")

    # subcomando add-url
    p_add = subparsers.add_parser("add-url", help="Agrega una nueva URL semilla a la base de datos.")
    p_add.add_argument("url", help="Dirección web a escanear (http:// o https://)")
    p_add.add_argument("-d", "--descripcion", default="", help="Descripción opcional de la fuente")

    # subcomando list-urls
    subparsers.add_parser("list-urls", help="Muestra las URLs semilla registradas.")

    # subcomando search
    p_search = subparsers.add_parser("search", help="Busca un término en el índice local.")
    p_search.add_argument("consulta", help="Texto o frase a buscar")
    p_search.add_argument("-n", "--limite", type=int, default=5, help="Máximo de resultados a mostrar")

    args = parser.parse_args()
    init_db()

    if args.comando == "scrape":
        ejecutar_scraping()
    elif args.comando == "index":
        indexar_documentos_pendientes()
    elif args.comando == "update":
        ejecutar_scraping()
        indexar_documentos_pendientes()
    elif args.comando == "add-url":
        if not args.url.startswith(("http://", "https://")):
            print("Error: la URL debe comenzar con http:// o https://")
            return
        if agregar_url_semilla(args.url, args.descripcion):
            print(f"URL agregada correctamente: {args.url}")
        else:
            print("La URL ya estaba registrada en el sistema.")
    elif args.comando == "list-urls":
        for row in obtener_urls_semilla(solo_activas=False):
            print(f"[{row['id']}] {row['url']} - {row['descripcion'] or 'Sin descripción'}")
    elif args.comando == "search":
        resultados = buscar_en_indice(args.consulta, limite=args.limite)
        if not resultados:
            print("No se encontraron coincidencias relevantes.")
            return
        for i, r in enumerate(resultados, start=1):
            print(f"\n{i}. [{r['porcentaje']}%] {r['titulo_enlace']} (Pág. {r['numero_pagina']})")
            print(f"   URL: {r['url_origen']}")
            print(f"   Fragmento: {r['texto_original'][:200]}...")


if __name__ == "__main__":
    main()