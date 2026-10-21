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
from html import escape as html_escape
from pathlib import Path

from generar_html import universidad_esta_vigente, formatear_fecha

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


def fechas_futuras(u: dict, hoy: date) -> list[date]:
    return sorted({
        datetime.strptime(fecha, "%Y-%m-%d").date()
        for fecha in u.get("fechas_examen", [])
        if datetime.strptime(fecha, "%Y-%m-%d").date() >= hoy
    })


def generar_parrafo_intro(u: dict, hoy: date) -> str:
    """Describe lo que figura en el registro y deriva al portal de admisión."""
    fechas = fechas_futuras(u, hoy)
    n_fechas = len(fechas)
    frase_fechas = "una fecha próxima" if n_fechas == 1 else f"{n_fechas} fechas próximas"
    primera_fecha = formatear_fecha(fechas[0].isoformat()) if fechas else "sin fecha próxima registrada"

    nombre = html_escape(u["nombre"])
    siglas = html_escape(u["siglas"])
    tipo_texto = "universidad pública" if u.get("tipo") == "publica" else "universidad privada"
    provincia = html_escape(u.get("provincia", ""))
    modalidad = html_escape(str(u.get("modalidad", "no indicada")))
    url_oficial = html_escape(u["url_oficial"], quote=True)

    resumen = (u.get("detalle") or {}).get("resumen_oficial")
    resumen_html = f"<p>{html_escape(resumen)}</p>" if resumen else ""

    return f'''<p>La {nombre} ({siglas}) es una {tipo_texto} con sede en {provincia}. En el registro de este sitio, el proceso de admisión figura bajo la modalidad {modalidad} y tiene {frase_fechas}; la primera es {primera_fecha}.</p>
{resumen_html}
<p>Las fechas y los requisitos pueden cambiar. Antes de inscribirte o realizar un pago, confirma el calendario, la modalidad y los documentos directamente en el <a href="{url_oficial}" target="_blank" rel="noopener noreferrer">portal oficial de admisión de {siglas}</a>.</p>'''


def generar_nota_fuente(u: dict) -> str:
    detalle = u.get("detalle") or {}
    fuente = detalle.get("fuente_resumen")
    if not fuente or not detalle.get("resumen_oficial"):
        return ""
    fecha = detalle.get("resumen_actualizado")
    fecha_html = f" Fecha indicada en el registro: {html_escape(formatear_fecha(fecha))}." if fecha else ""
    fuente_html = html_escape(fuente, quote=True)
    return (
        '<p class="ref-note">Fuente enlazada para el resumen: '
        f'<a href="{fuente_html}" target="_blank" rel="noopener noreferrer">consultar publicación</a>.'
        f'{fecha_html} Confirma siempre el proceso vigente en el portal oficial.</p>'
    )


def generar_filas_cronograma(u: dict, hoy: date) -> str:
    detalle = u.get("detalle", {})
    jornadas = detalle.get("cronograma_jornadas")
    if jornadas:
        jornadas_futuras = [
            j for j in jornadas
            if datetime.strptime(j["fecha"], "%Y-%m-%d").date() >= hoy
        ]
        if jornadas_futuras:
            return "\n".join(
                f'<tr><td>{formatear_fecha(j["fecha"])}</td><td>{html_escape(j["evaluacion"])}</td></tr>'
                for j in jornadas_futuras
            )
    return "\n".join(
        f'<tr><td>{formatear_fecha(fecha)}</td><td>Examen de admisión</td></tr>'
        for fecha in u["fechas_examen"]
        if datetime.strptime(fecha, "%Y-%m-%d").date() >= hoy
    )


def generar_pagina_universidad(u: dict, hoy: date):
    plantilla = PLANTILLA_PATH.read_text(encoding="utf-8")
    fechas = fechas_futuras(u, hoy)
    anio = fechas[0].year
    fechas_texto = ", ".join(formatear_fecha(f.isoformat()) for f in fechas)

    html = plantilla
    html = html.replace("{{SIGLAS}}", u["siglas"])
    html = html.replace("{{ANIO}}", str(anio))
    html = html.replace("{{NOMBRE_COMPLETO}}", u["nombre"])
    html = html.replace("{{RUTA}}", u["pagina_propia"])
    html = html.replace("{{FECHAS_TEXTO}}", fechas_texto)
    html = html.replace("{{FECHA_ACTUALIZACION}}", formatear_fecha(hoy.isoformat()))
    html = html.replace("{{FECHA_ISO_ACTUALIZACION}}", hoy.isoformat())
    html = html.replace("{{URL_OFICIAL}}", u["url_oficial"])
    html = html.replace("{{FILAS_CRONOGRAMA}}", generar_filas_cronograma(u, hoy))
    html = html.replace("{{SECCION_COSTOS}}", generar_seccion_costos(u.get("detalle"), u["siglas"]))
    html = html.replace("{{PARRAFO_INTRO}}", generar_parrafo_intro(u, hoy))
    html = html.replace("{{NOTA_FUENTE}}", generar_nota_fuente(u))

    destino = RAIZ / u["pagina_propia"].strip("/") / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


PAGINAS_ESTATICAS = [
    "/acerca-de/",
    "/guia-preparacion-examen-admision-peru/",
    "/uni/",
]


def generar_sitemap(vigentes: list, hoy: date):
    rutas = list(dict.fromkeys(PAGINAS_ESTATICAS))
    for u in vigentes:
        ruta = u.get("pagina_propia")
        if ruta and ruta not in rutas:
            rutas.append(ruta)

    urls = [
        '<url><loc>https://examenesperu.netlify.app/</loc>'
        f'<lastmod>{hoy.isoformat()}</lastmod></url>'
    ]
    for ruta in rutas:
        urls.append(
            f'<url><loc>https://examenesperu.netlify.app{ruta}</loc>'
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
    vigentes.sort(key=lambda u: fechas_futuras(u, hoy)[0])

    generadas = []
    for u in vigentes:
        if u.get("pagina_propia"):
            destino = generar_pagina_universidad(u, hoy)
            generadas.append(str(destino.relative_to(RAIZ)))

    generar_sitemap(vigentes, hoy)

    print(f"✅ {len(generadas)} página(s) individual(es) generada(s):")
    for g in generadas:
        print(f"   - {g}")
    total_urls = 1 + len(dict.fromkeys(PAGINAS_ESTATICAS + [
        u["pagina_propia"] for u in vigentes if u.get("pagina_propia")
    ]))
    print(f"✅ sitemap.xml regenerado con {total_urls} URLs (incluye home y páginas estáticas)")


if __name__ == "__main__":
    main()
