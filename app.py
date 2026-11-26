from flask import Flask, flash, redirect, render_template, request, url_for

from core.database import agregar_url_semilla, get_connection, init_db, obtener_urls_semilla
from core.indexer import indexar_documentos_pendientes
from core.scraper import ejecutar_scraping
from core.search import buscar_en_indice

app = Flask(__name__)
app.secret_key = "actas-unison-clave-sesion"

# garantizar que la base de datos exista al iniciar la aplicacion
init_db()

def obtener_estadisticas() -> dict:
    """Consulta el estado general del índice en SQLite."""
    with get_connection() as conn:
        total_docs = conn.execute("SELECT COUNT(*) FROM documentos;").fetchone()[0]
        indexados = conn.execute(
            "SELECT COUNT(*) FROM documentos WHERE estado_extraccion = 'indexado';"
        ).fetchone()[0]
        pendientes = conn.execute(
            "SELECT COUNT(*) FROM documentos WHERE estado_extraccion = 'pendiente';"
        ).fetchone()[0]
        sin_texto = conn.execute(
            "SELECT COUNT(*) FROM documentos WHERE estado_extraccion = 'sin_texto';"
        ).fetchone()[0]
        errores_descarga = conn.execute(
            "SELECT COUNT(*) FROM documentos WHERE estado_extraccion = 'error_descarga';"
        ).fetchone()[0]
        total_fragmentos = conn.execute("SELECT COUNT(*) FROM fragmentos;").fetchone()[0]

    return {
        "total_docs": total_docs,
        "indexados": indexados,
        "pendientes": pendientes,
        "sin_texto": sin_texto,
        "errores_descarga": errores_descarga,
        "total_fragmentos": total_fragmentos,
    }

@app.route("/", methods=["GET"])
def index():
    consulta_enviada = "q" in request.args
    consulta = request.args.get("q", "").strip()
    resultados = []
    mensaje_vacio = None

    if consulta_enviada:
        if not consulta:
            mensaje_vacio = "Por favor, escribe al menos una palabra o frase para buscar."
        else:
            resultados = buscar_en_indice(consulta)

    stats = obtener_estadisticas()
    return render_template(
        "index.html",
        consulta=consulta,
        consulta_enviada=consulta_enviada,
        resultados=resultados,
        mensaje_vacio=mensaje_vacio,
        stats=stats,
    )

@app.route("/urls", methods=["GET", "POST"])
def gestionar_urls():
    if request.method == "POST":
        nueva_url = request.form.get("url", "").strip()
        descripcion = request.form.get("descripcion", "").strip()

        if not nueva_url.startswith(("http://", "https://")):
            flash("La URL debe comenzar con http:// o https://", "warning")
        else:
            insertada = agregar_url_semilla(nueva_url, descripcion)
            if insertada:
                flash(f"URL agregada correctamente: {nueva_url}", "success")
            else:
                flash("Esa URL ya estaba registrada en el sistema.", "info")

        return redirect(url_for("gestionar_urls"))

    urls = obtener_urls_semilla(solo_activas=False)
    return render_template("urls.html", urls=urls)

@app.route("/estado", methods=["GET"])
def estado_sistema():
    stats = obtener_estadisticas()
    with get_connection() as conn:
        problematicos = conn.execute(
            """
            SELECT titulo_enlace, url_origen, estado_extraccion, mensaje_estado, fecha_descarga
            FROM documentos
            WHERE estado_extraccion IN ('sin_texto', 'error_descarga')
            ORDER BY id DESC;
            """
        ).fetchall()

        documentos_indexados = conn.execute(
            """
            SELECT d.titulo_enlace, d.url_origen, d.mensaje_estado, d.fecha_descarga,
                   COUNT(f.id) AS num_fragmentos
            FROM documentos d
            LEFT JOIN fragmentos f ON d.id = f.documento_id
            WHERE d.estado_extraccion = 'indexado'
            GROUP BY d.id
            ORDER BY d.id DESC;
            """
        ).fetchall()

    return render_template(
        "status.html",
        stats=stats,
        problematicos=problematicos,
        documentos_indexados=documentos_indexados,
    )

@app.route("/accion/<tipo>", methods=["POST"])
def ejecutar_accion(tipo):
    if tipo == "scraping":
        res = ejecutar_scraping()
        flash(
            f"Scraping finalizado: {res['descargados']} nuevos, "
            f"{res['omitidos']} omitidos (ya existían), {res['errores']} errores.",
            "success",
        )
    elif tipo == "indexar":
        res = indexar_documentos_pendientes()
        flash(
            f"Indexación finalizada: {res['indexados']} indexados, "
            f"{res['sin_texto']} sin texto, {res['fragmentos_creados']} fragmentos creados.",
            "success",
        )
    elif tipo == "todo":
        res_s = ejecutar_scraping()
        res_i = indexar_documentos_pendientes()
        flash(
            f"Actualización completa: {res_s['descargados']} descargados "
            f"({res_s['omitidos']} omitidos) y {res_i['indexados']} indexados.",
            "success",
        )
    else:
        flash("Acción no reconocida.", "danger")

    return redirect(request.referrer or url_for("estado_sistema"))

if __name__ == "__main__":
    app.run(debug=True)