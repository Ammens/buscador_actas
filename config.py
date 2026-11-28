from pathlib import Path

# directorio raiz del proyecto
BASE_DIR = Path(__file__).resolve().parent

# directorios y archivos de datos
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "actas.db"

# asegurar que los directorios existan
DATA_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

# configuracion inicial del scrapping
URL_INICIAL = "https://fi-ing.unison.mx/actas/"
DESCRIPCION_INICIAL = "Portal de actas de la Facultad Interdiciplinaria de Ingenieria (UNISON)"

# limites y cortesia del scraper
MAX_PROFUNDIDAD = 3
MAX_PAG_POR_SEMILLA = 50
MAX_PDFS_POR_SEMILLA = 30    # limite de PDFs a procesar por cada URL semilla
PAUSA_ENTRE_PETICIONES = 1.0
TIMEOUT_PETICION = 15

# configuracion del buscador con Levenshtein
UMBRAL_SIMILITUD = 0.65    # similitud para considerar un resultado como relevante
MAX_RESULTADOS = 30