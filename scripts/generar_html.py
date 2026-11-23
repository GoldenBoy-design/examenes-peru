"""
Genera la portada con las convocatorias cotejadas con fuentes oficiales.

Los scripts de búsqueda guardan sus hallazgos en universidades.json. Las fechas
públicas proceden de cronogramas-verificados.json y se incorporan tras revisar
el aviso de la institución y la modalidad que le corresponde.
"""

import json
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

RAIZ = Path(__file__).resolve().parents[1]
ADSENSE = (
    '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
    '?client=ca-pub-4574160139184005" crossorigin="anonymous"></script>'
)
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def fecha_html(valor: str) -> str:
    fecha = date.fromisoformat(valor)
    texto = f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"
    return f'<time datetime="{fecha.isoformat()}">{texto}</time>'


def enlace_oficial(url: str, texto: str, contexto: str) -> str:
    destino = urlsplit(url)
    if destino.scheme != "https" or not destino.hostname:
        raise ValueError(f"Se requiere un enlace HTTPS institucional: {url}")
    etiqueta = escape(f"{texto} de {contexto}")
    return f'<a href="{escape(url)}" aria-label="{etiqueta}">{escape(texto)}</a>'


def ficha_evento(evento: dict, instituciones: dict) -> str:
    institucion = instituciones[evento["institucion"]]
    siglas = institucion["siglas"]
    proceso = escape(evento["proceso"])
    inscripcion = evento.get("inscripcion", {})
    inicio = inscripcion.get("inicio")
    fin = inscripcion.get("fin")

    if inicio and fin:
        if date.fromisoformat(inicio) > date.fromisoformat(fin):
            raise ValueError(f"Fechas de inscripción invertidas: {proceso}")
        plazo = f"Del {fecha_html(inicio)} al {fecha_html(fin)}"
    elif fin:
        plazo = f"Hasta el {fecha_html(fin)}"
    else:
        plazo = "Consulta el plazo en la fuente"

    fuente = enlace_oficial(evento["fuente"], "Ver convocatoria oficial", siglas)
    fecha = date.fromisoformat(evento["fecha"]).isoformat()
    cierre = date.fromisoformat(fin).isoformat() if fin else ""
    nota = f'\n                    <p class="event-note">{escape(evento["nota"])}</p>' if evento.get("nota") else ""
    return f"""
            <li class="event" data-fecha="{fecha}" data-cierre="{cierre}">
                <div class="event-date">{fecha_html(fecha)}<span class="event-state" hidden></span></div>
                <div class="event-detail">
                    <h3>{escape(siglas)}</h3>
                    <p>{proceso}</p>{nota}
                </div>
                <div class="event-deadline">
                    <p><strong>Inscripción</strong></p>
                    <p>{plazo}</p>
                    <p class="registration-state" hidden>Plazo vencido</p>
                    {fuente}
                </div>
            </li>"""


def ficha_directorio(registro: dict, instituciones: dict) -> str:
    institucion = instituciones[registro["institucion"]]
    siglas = institucion["siglas"]
    nombre = escape(institucion["nombre"])
    sede = escape(registro.get("sede", institucion["provincia"]))
    enlace = enlace_oficial(registro["portal"], "Portal de admisión", siglas)
    return f"""
            <li>
                <h3>{escape(siglas)}</h3>
                <p>{nombre}</p>
                <p class="directory-location">{sede}</p>
                {enlace}
            </li>"""


def main():
    datos = json.loads((RAIZ / "data/cronogramas-verificados.json").read_text(encoding="utf-8"))
    registro = json.loads((RAIZ / "data/universidades.json").read_text(encoding="utf-8"))
    instituciones = {item["id"]: item for item in registro["universidades"]}
    plantilla = (RAIZ / "templates/index.template.html").read_text(encoding="utf-8")
    eventos = sorted(datos["eventos"], key=lambda evento: (evento["fecha"], evento["institucion"]))
    directorio = sorted(datos["directorio"], key=lambda entrada: instituciones[entrada["institucion"]]["siglas"])
    html = (
        plantilla
        .replace("{{ADSENSE}}", ADSENSE)
        .replace("{{FECHA_REVISION}}", fecha_html(datos["revision"]))
        .replace("{{EVENTOS}}", "\n".join(ficha_evento(evento, instituciones) for evento in eventos))
        .replace("{{DIRECTORIO}}", "\n".join(ficha_directorio(entrada, instituciones) for entrada in directorio))
    )
    (RAIZ / "index.html").write_text(html, encoding="utf-8", newline="\n")
    print(f"Portada generada con {len(eventos)} fechas cotejadas y {len(directorio)} portales de admisión.")


if __name__ == "__main__":
    main()
