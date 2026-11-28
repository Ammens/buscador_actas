# Buscador de Actas en PDF — Facultad Interdisciplinaria de Ingeniería UNISON

## 1. Integrantes
* Jonathan Rascón Sifuentes
* Constantino Grijalva Yanez

## 2. Descripción del sistema
Sistema web y de línea de comandos desarrollado en Python que automatiza el flujo completo de **registro de URLs → web scraping y descarga de PDFs → extracción e indexación de texto → búsqueda aproximada**.

El objetivo es facilitar la localización de información dentro de las actas oficiales publicadas por la Facultad Interdisciplinaria de Ingeniería de la Universidad de Sonora (`https://fi-ing.unison.mx/actas/`), tolerando variaciones de escritura, acentos y errores tipográficos mediante la biblioteca **Levenshtein**.

## 3. Instalación y ejecución

### Requisitos previos
* Python 3.10 o superior
* `pip` y `venv`

### Pasos de instalación
1. Clonar el repositorio:
   ```bash
   git clone [https://github.com/Ammens/buscador_actas_unison.git](https://github.com/Ammens/buscador_actas_unison.git)
   cd buscador_actas_unison
   ```

2. Crear y activar el entorno virtual:
   * **Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
   * **Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Iniciar la aplicación web:
   ```bash
   python app.py
   ```
   Abrir en el navegador: `http://127.0.0.1:5000`

## 4. Procedimiento para agregar nuevas URLs e incorporar nuevas actas
No es necesario modificar el código fuente para agregar nuevas fuentes de escaneo:

* **Desde la interfaz web:** Ir a la pestaña **URLs Semilla** (`/urls`), ingresar la nueva dirección (`http://` o `https://`) junto con una descripción opcional y presionar **Guardar URL**. Luego hacer clic en **Escanear e Indexar ahora**.
* **Desde la terminal (CLI):**
  ```bash
  python cli.py add-url "[https://ejemplo.unison.mx/actas-nuevas/](https://ejemplo.unison.mx/actas-nuevas/)" -d "Actas adicionales"
  python cli.py update
  ```
Todas las URLs agregadas se almacenan de forma persistente en la tabla `urls_semilla` de SQLite.

## 5. Instrucciones para descargar, indexar, actualizar y buscar

### Desde la interfaz web
* **Buscar:** En la página principal (`/`), escribir una palabra o frase y presionar **Buscar**. Las consultas se ejecutan únicamente sobre el índice local en SQLite (sin volver a hacer scraping).
* **Descargar / Indexar / Actualizar:** En la pestaña **Estado e Índice** (`/estado`), utilizar los botones **1. Ejecutar Scraping**, **2. Indexar Pendientes** o **Actualizar Todo**.

### Desde la terminal (CLI)
* Descargar PDFs nuevos: `python cli.py scrape`
* Indexar PDFs pendientes: `python cli.py index`
* Ejecutar ambos procesos: `python cli.py update`
* Buscar desde consola: `python cli.py search "convocatoria covid"`

## 6. Almacenamiento y control de archivos descargados
El sistema utiliza una base de datos **SQLite** (`data/actas.db`) y una carpeta local (`data/pdfs/`):

* **Tablas principales:**
  * `urls_semilla`: Almacena las direcciones base para el crawler.
  * `documentos`: Registra `url_origen` (única), `titulo_enlace`, `nombre_archivo_local`, `ruta_local`, `estado_extraccion` (`pendiente`, `indexado`, `sin_texto`, `error_descarga`) y `mensaje_estado`.
  * `fragmentos`: Almacena el texto extraído dividido en bloques (~450 caracteres) con su `numero_pagina`, `texto_original` y `texto_normalizado`.
* **Prevención de duplicados:** Antes de descargar, se verifica que `url_origen` exista en SQLite y que el archivo físico siga presente en `data/pdfs/`. Si ya existe, se omite.
* **Prevención de colisiones de nombres:** Cada archivo se guarda con un prefijo hash MD5 de 8 caracteres derivado de su URL original (`<hash>_<nombre_limpio>.pdf`), evitando que dos documentos distintos con el mismo nombre se sobrescriban.
* **Control del crawler:** Se implementa búsqueda en anchura (BFS) con límite de profundidad (`MAX_PROFUNDIDAD = 3`), límite de páginas por semilla (`MAX_PAGINAS_POR_SEMILLA = 50`), filtro de dominio/rutas pertinentes y pausas entre peticiones (`1.0 s`).

## 7. Criterio de similitud y ordenamiento
El motor de búsqueda (`core/search.py`) utiliza `Levenshtein.ratio`:

1. **Normalización:** Tanto la consulta como los fragmentos indexados se convierten a minúsculas y se eliminan acentos y signos especiales.
2. **Cálculo de relevancia (0.0 a 1.0):**
   * Si la consulta normalizada es subcadena exacta del fragmento o del título del acta, obtiene `1.0` (100%).
   * De lo contrario, se calcula el máximo entre la **similitud promedio por palabras individuales** (que tolera errores tipográficos y orden distinto) y la **similitud por ventana deslizante** de frases del mismo número de palabras.
3. **Umbral y ordenamiento**: Se descartan coincidencias menores a `UMBRAL_SIMILITUD = 0.65` (65%) y los resultados válidos se ordenan de mayor a menor similitud.

## 8. Limitaciones conocidas y extras implementados

### Limitaciones conocidas
* Los documentos PDF compuestos únicamente por imágenes escaneadas sin capa de texto no pueden ser indexados automáticamente (se identifican y reportan en la vista `/estado` con estado `sin_texto`).
* En sitios con cientos de PDFs, la primera ejecución del scraping puede tomar varios minutos debido a las pausas de cortesía entre peticiones.

### Extras implementados
* **Interfaz profesional adaptable (Bootstrap 5):** Diseño responsivo con la paleta institucional de la UNISON (`#FFFFFF`, `#FFA41C`, `#553CDF`).
* **Panel de administración y monitoreo (`/estado`):** Métricas en tiempo real, listado de documentos indexados y tabla dedicada de reporte de PDFs sin texto o con errores de descarga.
* **Interfaz de línea de comandos (`cli.py`):** Permite operar todo el sistema tanto desde web como desde terminal.