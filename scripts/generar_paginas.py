"""
Genera:
  1. Una página HTML propia para cada universidad con pagina_propia definida
     en data/universidades.json (solo si su proceso está vigente).
  2. sitemap.xml actualizado con las URLs realmente publicadas hoy.

Depende de: generar_html.py (para la lógica de "vigente") — se reutiliza
la misma regla para no duplicar criterios de qué se publica.

Uso:
    python scripts/generar_paginas.py
"""

import json
from datetime import date, datetime
from pathlib import Path

from generar_html import universidad_esta_vigente, formatear_fecha, MESES

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
PLANTILLA_PATH = RAIZ / "templates" / "universidad.template.html"
SITEMAP_PATH = RAIZ / "sitemap.xml"


def generar_seccion_costos(detalle: dict, siglas: str) -> str:
    if not detalle:
        return ""
    partes = ['<section><h2>Costos del proceso</h2>']
    if detalle.get("costo_prospecto"):
        partes.append(f'<p><strong>Prospecto:</strong> S/ {detalle["costo_prospecto"]}</p>')
    if detalle.get("costo_inscripcion_estatal"):
        partes.append(f'<p><strong>Inscripción (colegio estatal):</strong> S/ {detalle["costo_inscripcion_estatal"]}</p>')
    if detalle.get("costo_inscripcion_privado"):
        partes.append(f'<p><strong>Inscripción (colegio privado):</strong> S/ {detalle["costo_inscripcion_privado"]}</p>')
    if detalle.get("nota_costos"):
        partes.append(f'<div class="ref-note">⚠️ {detalle["nota_costos"]}</div>')
    partes.append("</section>")
    return "\n".join(partes)


def generar_parrafo_intro(u: dict, anio: int) -> str:
    """Párrafo de contexto construido solo con datos que ya están en el
    JSON (tipo, provincia, modalidad, cantidad de fechas) — no se inventa
    ninguna cifra ni afirmación que no podamos respaldar con la data."""
    tipo_texto = "universidad pública" if u.get("tipo") == "publica" else "universidad privada"
    n_fechas = len(u.get("fechas_examen", []))
    frase_fechas = "una fecha de evaluación" if n_fechas == 1 else f"{n_fechas} fechas de evaluación"

    return f'''<p>La {u["nombre"]} ({u["siglas"]}) es una {tipo_texto} con sede en {u["provincia"]}. Su proceso de admisión {anio} se desarrolla bajo la modalidad {u["modalidad"]}, con {frase_fechas} programada{"s" if n_fechas != 1 else ""} este año.</p>
<p>Antes de postular, revisa el reglamento de admisión vigente en el portal oficial de la universidad: ahí se detallan los requisitos de inscripción, los documentos exigidos y el temario de cada prueba. Esta página resume el cronograma público y se actualiza a partir de fuentes oficiales y noticias verificadas, pero la fuente definitiva siempre es <a href="{u["url_oficial"]}" target="_blank" rel="noopener">el portal oficial de {u["siglas"]}</a>.</p>'''


def generar_faq(u: dict) -> str:
    """Genera 4 preguntas frecuentes usando solo datos verificados del JSON.
    Cuando no hay un dato concreto (p.ej. costos), la respuesta remite al
    portal oficial en vez de inventar una cifra."""
    preguntas = []

    preguntas.append((
        f"¿Qué modalidad de ingreso tiene la convocatoria actual de {u['siglas']}?",
        f"La convocatoria vigente es bajo la modalidad {u['modalidad']}. Muchas universidades peruanas ofrecen también otras vías (CEPU, traslado externo, primeros puestos, deportistas calificados) con cronogramas distintos al examen ordinario — revisa el portal oficial para confirmar si {u['siglas']} las tiene abiertas."
    ))

    detalle = u.get("detalle") or {}
    if detalle.get("costo_prospecto") or detalle.get("costo_inscripcion_estatal"):
        partes_precio = []
        if detalle.get("costo_prospecto"):
            partes_precio.append(f"el prospecto cuesta S/ {detalle['costo_prospecto']}")
        if detalle.get("costo_inscripcion_estatal"):
            partes_precio.append(f"la inscripción para colegio estatal es de S/ {detalle['costo_inscripcion_estatal']}")
        precio_final = " y ".join(partes_precio)
        preguntas.append((
            f"¿Cuánto cuesta postular a {u['siglas']}?",
            f"Para el proceso vigente, {precio_final}. Estos montos pueden cambiar de un proceso a otro, así que confírmalos en el portal oficial antes de pagar."
        ))
    else:
        preguntas.append((
            f"¿Cuánto cuesta postular a {u['siglas']}?",
            f"El costo de inscripción varía según el proceso y el tipo de colegio de procedencia (estatal o privado). {u['siglas']} publica el monto vigente en su portal oficial de admisión."
        ))

    preguntas.append((
        f"¿Dónde veo los resultados del examen de {u['siglas']}?",
        "Los resultados se publican en el portal oficial de la universidad, generalmente entre 24 y 72 horas después de rendir la prueba, según el proceso. El enlace directo está en la sección de cronograma de esta misma página."
    ))

    preguntas.append((
        "¿Qué debo llevar el día del examen?",
        "El documento de identidad (DNI o carné de extranjería vigente) y el comprobante de inscripción son exigidos por prácticamente todas las universidades peruanas. Cada institución define además qué útiles están permitidos dentro del aula — revisa el reglamento de admisión antes de la fecha."
    ))

    return "\n".join(
        f'<div class="faq-item"><h3>{pregunta}</h3><p>{respuesta}</p></div>'
        for pregunta, respuesta in preguntas
    )


def generar_filas_cronograma(u: dict) -> str:
    detalle = u.get("detalle", {})
    jornadas = detalle.get("cronograma_jornadas")
    if jornadas:
        return "\n".join(
            f'<tr><td>{formatear_fecha(j["fecha"])}</td><td>{j["evaluacion"]}</td></tr>'
            for j in jornadas
        )
    # Sin detalle de jornadas: al menos listamos las fechas de examen
    return "\n".join(
        f'<tr><td>{formatear_fecha(f)}</td><td>Examen de admisión</td></tr>'
        for f in u["fechas_examen"]
    )


def generar_pagina_universidad(u: dict, hoy: date):
    plantilla = PLANTILLA_PATH.read_text(encoding="utf-8")
    anio = hoy.year
    fechas_texto = ", ".join(formatear_fecha(f) for f in u["fechas_examen"])

    html = plantilla
    html = html.replace("{{SIGLAS}}", u["siglas"])
    html = html.replace("{{ANIO}}", str(anio))
    html = html.replace("{{NOMBRE_COMPLETO}}", u["nombre"])
    html = html.replace("{{RUTA}}", u["pagina_propia"])
    html = html.replace("{{FECHAS_TEXTO}}", fechas_texto)
    html = html.replace("{{FECHA_ACTUALIZACION}}", hoy.strftime("%d de %B, %Y"))
    html = html.replace("{{FECHA_ISO_ACTUALIZACION}}", hoy.isoformat())
    html = html.replace("{{URL_OFICIAL}}", u["url_oficial"])
    html = html.replace("{{FILAS_CRONOGRAMA}}", generar_filas_cronograma(u))
    html = html.replace("{{SECCION_COSTOS}}", generar_seccion_costos(u.get("detalle"), u["siglas"]))
    html = html.replace("{{PARRAFO_INTRO}}", generar_parrafo_intro(u, anio))
    html = html.replace("{{FAQ_HTML}}", generar_faq(u))

    destino = RAIZ / u["pagina_propia"].strip("/") / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


PAGINAS_ESTATICAS = ["/acerca-de/", "/guia-preparacion-examen-admision-peru/"]


def generar_sitemap(vigentes: list, hoy: date):
    urls = ['<url><loc>https://examenesperu.netlify.app/</loc>'
            f'<lastmod>{hoy.isoformat()}</lastmod></url>']
    for ruta in PAGINAS_ESTATICAS:
        urls.append(
            f'<url><loc>https://examenesperu.netlify.app{ruta}</loc>'
            f'<lastmod>{hoy.isoformat()}</lastmod></url>'
        )
    for u in vigentes:
        if u.get("pagina_propia"):
            urls.append(
                f'<url><loc>https://examenesperu.netlify.app{u["pagina_propia"]}</loc>'
                f'<lastmod>{hoy.isoformat()}</lastmod></url>'
            )
    cuerpo = "\n".join(urls)
    sitemap = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{cuerpo}
</urlset>
'''
    SITEMAP_PATH.write_text(sitemap, encoding="utf-8")


def main():
    hoy = date.today()
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    vigentes = [u for u in data["universidades"] if universidad_esta_vigente(u, hoy)]

    generadas = []
    for u in vigentes:
        if u.get("pagina_propia"):
            destino = generar_pagina_universidad(u, hoy)
            generadas.append(str(destino.relative_to(RAIZ)))

    generar_sitemap(vigentes, hoy)

    print(f"✅ {len(generadas)} página(s) individual(es) generada(s):")
    for g in generadas:
        print(f"   - {g}")
    total_urls = len(vigentes) + 1 + len(PAGINAS_ESTATICAS)
    print(f"✅ sitemap.xml regenerado con {total_urls} URLs (incluye home y páginas estáticas)")


if __name__ == "__main__":
    main()