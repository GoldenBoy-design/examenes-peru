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

    destino = RAIZ / u["pagina_propia"].strip("/") / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


def generar_sitemap(vigentes: list, hoy: date):
    urls = ['<url><loc>https://examenesperu.netlify.app/</loc>'
            f'<lastmod>{hoy.isoformat()}</lastmod></url>']
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
    print(f"✅ sitemap.xml regenerado con {len(vigentes) + 1} URLs (incluye home)")


if __name__ == "__main__":
    main()
