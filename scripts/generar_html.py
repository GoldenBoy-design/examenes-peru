"""
Genera index.html a partir de data/universidades.json.

Regla central: solo se incluyen universidades con estado_proceso == "abierto".
Si una universidad ya cerró su proceso (o el script determina que la fecha ya
pasó), se excluye automáticamente del HTML, aunque el registro siga en el JSON
para reutilizarlo el próximo año.

Uso:
    python scripts/generar_html.py
"""

import json
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
SALIDA_HTML = RAIZ / "index.html"
SALIDA_SITEMAP = RAIZ / "sitemap.xml"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def formatear_fecha(iso: str) -> str:
    d = datetime.strptime(iso, "%Y-%m-%d").date()
    return f"{d.day:02d} de {MESES[d.month - 1].capitalize()}, {d.year}"


def formatear_rango_inscripcion(inscripcion: dict) -> str:
    if not inscripcion.get("inicio") or not inscripcion.get("fin"):
        return inscripcion.get("nota", "Sin información")
    di = datetime.strptime(inscripcion["inicio"], "%Y-%m-%d").date()
    df = datetime.strptime(inscripcion["fin"], "%Y-%m-%d").date()
    return f"{di.day:02d} {MESES[di.month-1][:3]} - {df.day:02d} {MESES[df.month-1][:3]}"


def universidad_esta_vigente(u: dict, hoy: date) -> bool:
    """Una universidad se publica solo si su proceso está marcado como abierto
    Y al menos una de sus fechas de examen es hoy o futura."""
    if u.get("estado_proceso") != "abierto":
        return False
    fechas = [datetime.strptime(f, "%Y-%m-%d").date() for f in u.get("fechas_examen", [])]
    if not fechas:
        return False
    return any(f >= hoy for f in fechas)


def generar_fila(u: dict, hoy: date) -> str:
    fechas = [datetime.strptime(f, "%Y-%m-%d").date() for f in u["fechas_examen"]]
    # Mostramos la PRÓXIMA fecha vigente, no la más antigua del historial.
    # Antes, una universidad con fechas pasadas y futuras mezcladas (p.ej.
    # un examen de julio ya rendido + uno nuevo de septiembre agregado por
    # el scraper) seguía mostrando la de julio porque min() ignora si ya pasó.
    futuras = [f for f in fechas if f >= hoy]
    fecha_principal = min(futuras) if futuras else min(fechas)
    fecha_txt = formatear_fecha(fecha_principal.isoformat())
    inscripcion_txt = formatear_rango_inscripcion(u["inscripcion"])
    link = u["pagina_propia"] if u.get("pagina_propia") else u["url_oficial"]
    texto_boton = "Ver fechas y requisitos" if u.get("pagina_propia") else "Más Info"
    target = "" if u.get("pagina_propia") else ' target="_blank"'

    return f"""
<tr>
    <td class="universidad"><span class="logo-box"><img src="{u['logo']}" alt="Logo {u['siglas']}"></span><span class="uni-name">{u['nombre']} ({u['siglas']})</span></td>
    <td class="provincia">{u['provincia']}</td>
    <td><span class="modalidad">{u['modalidad']}</span></td>
    <td class="fecha">{fecha_txt}</td>
    <td>{inscripcion_txt}</td>
    <td><a href="{link}"{target} class="btn-info">{texto_boton}</a></td>
</tr>"""


def main():
    hoy = date.today()
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    vigentes = [u for u in data["universidades"] if universidad_esta_vigente(u, hoy)]
    excluidas = [u for u in data["universidades"] if u not in vigentes]

    vigentes.sort(key=lambda u: min(u["fechas_examen"]))

    filas_html = "\n".join(generar_fila(u, hoy) for u in vigentes)

    plantilla = (RAIZ / "templates" / "index.template.html").read_text(encoding="utf-8")
    html_final = plantilla.replace("{{FILAS_UNIVERSIDADES}}", filas_html)
    html_final = html_final.replace("{{FECHA_ACTUALIZACION}}", hoy.strftime("%d de %B, %Y"))

    SALIDA_HTML.write_text(html_final, encoding="utf-8")

    print(f"✅ index.html generado con {len(vigentes)} universidades vigentes")
    if excluidas:
        nombres = ", ".join(u["siglas"] for u in excluidas)
        print(f"⏸️  Excluidas por estar cerradas o sin fecha vigente: {nombres}")


if __name__ == "__main__":
    main()