# Buscador de Actas en PDF — Facultad Interdisciplinaria de Ingeniería UNISON

## 1. Integrantes
* Jonathan Rascón Sifuentes
* Constantino Grijalva Yanez

## 2. Descripcion del sistema
Sistema web y de linea de comandos desarrollado en Python que automatiza el flujo completo de **registro de URLs → web scraping y descarga de PDFs → extracción e indexacion de texto → búsqueda aproximada**.

El objetivo es facilitar la localización de información dentro de las actas oficiales publicadas por la Facultad Interdisciplinaria de Ingeniería de la Universidad de Sonora (`https://fi-ing.unison.mx/actas/`), tolerando variaciones de escritura, acentos y errores tipográficos mediante la biblioteca **Levenshtein**.

## 3. Instalación y ejecucion

### Requisitos previos
* Python 3.10 o superior
* `pip` y `venv`

### Pasos de instalación
1. Clonar el repositorio:
   ```bash
   git clone [https://github.com/Ammens/buscador_actas_unison.git](https://github.com/Ammens/buscador_actas_unison.git)
   cd buscador_actas_unison