import sqlite3
from pathlib import Path
from config import DB_PATH, URL_INICIAL, DESCRIPCION_INICIAL

def get_connection() -> sqlite3.Connection:
    """Devuelve conexion a SQLite con acceso por nombre de columna y FK activas"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreing_keys = ON;")
    return conn

def init_db() -> None:
    """Crea las tablas si no existen e inserta la URL semilla"""
    with get_connection() as conn:
        cursor = conn.cursor() 

        # tabla de URLs semilla
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS urls_semilla (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                descripcion TEXT,
                activa INTEGER NOT NULL DEFAULT 1,
                fecha_agregada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # tabla de PDFs descubiertos y descargados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_origen TEXT UNIQUE NOT NULL,
                titulo_enlace TEXT NOT NULL,
                nombre_archivo_local TEXT UNIQUE NOT NULL,
                ruta_local TEXT NOT NULL,
                estado_extraccion TEXT NOT NULL DEFAULT 'pendiente',
                mensaje_estado TEXT,
                fecha_descarga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # tabla de fragmentos de texto indexados por pagina/parrafo
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fragmentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documento_id INTEGER NOT NULL,
                numero_pagina INTEGER NOT NULL,
                texto_original TEXT NOT NULL,
                texto_normalizado TEXT NOT NULL,
                FOREIGN KEY (documento_id) REFERENCES documentos(id) ON DELETE CASCADE
            );
        """)

        # indices para acelerar consultas de estado y busqueda
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_documentos_estado 
            ON documentos(estado_extraccion);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fragmentos_doc 
            ON fragmentos(documento_id);
        """)

        # insetar la URL inicial si no existe
        cursor.execute("""
            INSERT OR IGNORE INTO urls_semilla (url, descripcion)
            VALUES (?, ?);
        """, (URL_INICIAL, DESCRIPCION_INICIAL))

        conn.commit()

def agregar_url_semilla(url: str, descripcion: str = "") -> bool:
    """Agrega una nueva URL semilla. Devuelve True si se inserto, False si ya existia"""
    url_limpia = url.strip()
    if not url_limpia:
        return False
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO urls_semilla (url, descripcion)
            VALUES (?, ?);
        """, (url_limpia, descripcion.strip()))
        conn.commit()
        return cursor.rowcount > 0

def obtener_urls_semilla(solo_activas: bool = True) -> list[sqlite3.Row]:
    """Obtiene la lista de URLs registradas"""
    query = "SELECT * FROM urls_semilla"
    if solo_activas:
        query += " WHERE activa = 1"
    query += " ORDER BY id ASC;"
    
    with get_connection() as conn:
        return conn.execute(query).fetchall()        

if __name__ == "__main__":
    init_db()
    print(f"Base de datos inicializada correctamente en: {DB_PATH}")
    for row in obtener_urls_semilla(solo_activas=False):
        print(f" - [{row['id']}] {row['url']} ({row['descripcion']})")        