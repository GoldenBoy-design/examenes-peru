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
from unicodedata import combining, normalize
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
HISTORIALES_PROPIOS = {"uni": "/uni/", "unmsm": "/san-marcos/"}


def cargar_padron() -> dict:
    return json.loads((RAIZ / "data/padron-sunedu.json").read_text(encoding="utf-8"))


def cargar_historial() -> dict:
    return json.loads((RAIZ / "data/historial-admision.json").read_text(encoding="utf-8"))


def ruta_historial(institucion_id: str, historial: dict) -> str:
    return HISTORIALES_PROPIOS.get(institucion_id, f"/historial/#{institucion_id}" if institucion_id in historial else "")


def fecha_html(valor: str) -> str:
    fecha = date.fromisoformat(valor)
    texto = f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"
    return f'<time datetime="{fecha.isoformat()}">{texto}</time>'


def fecha_calendario_html(fecha: date) -> str:
    mes = MESES[fecha.month - 1]
    return (
        f'<time datetime="{fecha.isoformat()}">'
        f'<span class="event-day">{fecha.day}</span> '
        f'<span class="event-month">{mes} {fecha.year}</span></time>'
    )


def logo_html(institucion: dict) -> str:
    logo = f'/logos/{institucion["id"]}.png'
    if (RAIZ / logo.lstrip("/")).is_file():
        return (
            '<span class="institution-logo">'
            f'<img src="{escape(logo)}" alt="" width="52" height="52" loading="lazy" decoding="async">'
            '</span>'
        )
    return f'<span class="institution-logo logo-text" aria-hidden="true">{escape(institucion["siglas"])}</span>'


def enlace_oficial(url: str, texto: str, contexto: str) -> str:
    destino = urlsplit(url)
    if destino.scheme != "https" or not destino.hostname:
        raise ValueError(f"Se requiere un enlace HTTPS institucional: {url}")
    etiqueta = escape(f"{texto} de {contexto}")
    return f'<a class="official-link" href="{escape(url)}" aria-label="{etiqueta}">{escape(texto)}</a>'


def ficha_evento(evento: dict, instituciones: dict, historial: dict) -> str:
    institucion = instituciones[evento["institucion"]]
    siglas = institucion["siglas"]
    proceso = escape(evento["proceso"])
    ubicacion = escape(evento.get("ubicacion", institucion["sede"]))
    archivo = ruta_historial(institucion["id"], historial)
    titulo = f'<a href="{archivo}">{escape(siglas)}</a>' if archivo else escape(siglas)
    inscripcion = evento.get("inscripcion", {})
    inicio = inscripcion.get("inicio")
    fin = inscripcion.get("fin")
    # "abierta_al" documenta una inscripción activa sin inventar su fecha de inicio.
    apertura = inicio or inscripcion.get("abierta_al", "")

    if inicio and fin:
        if date.fromisoformat(inicio) > date.fromisoformat(fin):
            raise ValueError(f"Fechas de inscripción invertidas: {proceso}")
        plazo = f"Del {fecha_html(inicio)} al {fecha_html(fin)}"
    elif fin:
        plazo = f"Hasta el {fecha_html(fin)}"
    else:
        plazo = "Consulta el plazo en la fuente"

    fuente = enlace_oficial(evento["fuente"], "Ver convocatoria oficial", siglas)
    fecha = date.fromisoformat(evento["fecha"])
    cierre = date.fromisoformat(fin).isoformat() if fin else ""
    hora_cierre = escape(inscripcion.get("hora_cierre", ""))
    nota = f'\n                    <p class="event-note">{escape(evento["nota"])}</p>' if evento.get("nota") else ""
    return f"""
            <li class="event" data-fecha="{fecha.isoformat()}" data-tipo="{escape(institucion["tipo"])}"
                data-apertura="{escape(apertura)}" data-cierre="{cierre}" data-hora-cierre="{hora_cierre}">
                <div class="event-date">{fecha_calendario_html(fecha)}<span class="event-state" hidden></span></div>
                <div class="event-detail">
                    {logo_html(institucion)}
                    <div>
                        <h3>{titulo}</h3>
                        <p class="event-process">{proceso}</p>{nota}
                    </div>
                </div>
                <div class="event-location">
                    <p class="deadline-label">Ubicación</p>
                    <p>{ubicacion}</p>
                </div>
                <div class="event-deadline">
                    <p class="deadline-label">Inscripción</p>
                    <p>{plazo}</p>
                    <p class="registration-state" hidden></p>
                    {fuente}
                </div>
            </li>"""


def ficha_directorio(institucion: dict, historial: dict) -> str:
    institucion_id = institucion["id"]
    siglas = escape(institucion["siglas"])
    nombre = escape(institucion["nombre"])
    sede = escape(institucion["sede"])
    region = escape(institucion["departamento"])
    tipo = "Nacional" if institucion["tipo"] == "publica" else "Privada"
    archivo = ruta_historial(institucion_id, historial)
    enlace = escape(archivo or institucion["portal"])
    etiqueta = "Historial de admisión" if archivo else institucion["etiqueta"]
    portal = f'\n                    {enlace_oficial(institucion["portal"], institucion["etiqueta"], institucion["siglas"])}' if archivo else ""
    licencia = enlace_oficial(institucion["licencia"], "Licencia SUNEDU", institucion["siglas"])
    return f"""
            <li class="directory-item" id="universidad-{institucion_id}" data-region="{region}">
                <div class="directory-heading">
                    {logo_html(institucion)}
                    <div>
                        <p class="directory-code">{siglas} <span>{tipo}</span></p>
                        <p class="directory-location">{sede}</p>
                    </div>
                </div>
                <h3 class="directory-name"><a href="{enlace}">{nombre}</a></h3>
                <div class="directory-actions">
                    <a class="directory-primary" href="{enlace}" aria-label="{escape(etiqueta)} de {siglas}">{escape(etiqueta)}</a>{portal}
                    {licencia}
                </div>
            </li>"""


def main():
    datos = json.loads((RAIZ / "data/cronogramas-verificados.json").read_text(encoding="utf-8"))
    registro = cargar_padron()
    instituciones = {item["id"]: item for item in registro["universidades"]}
    historial = cargar_historial()
    plantilla = (RAIZ / "templates/index.template.html").read_text(encoding="utf-8")

    def orden_institucion(institucion):
        return institucion["tipo"] != "publica", institucion["siglas"]

    eventos = sorted(datos["eventos"], key=lambda evento: (evento["fecha"], orden_institucion(instituciones[evento["institucion"]])))
    directorio = sorted(instituciones.values(), key=lambda u: (u["id"] != "unmsm", orden_institucion(u)))
    regiones = sorted(
        {u["departamento"] for u in directorio},
        key=lambda region: "".join(letra for letra in normalize("NFD", region) if not combining(letra)),
    )
    opciones = "\n".join(f'                            <option value="{escape(region)}">{escape(region)}</option>' for region in regiones)
    nacionales = sum(u["tipo"] == "publica" for u in directorio)
    html = (
        plantilla
        .replace("{{ADSENSE}}", ADSENSE)
        .replace("{{FECHA_REVISION}}", fecha_html(datos["revision"]))
        .replace("{{EVENTOS}}", "\n".join(ficha_evento(evento, instituciones, historial) for evento in eventos))
        .replace("{{DIRECTORIO}}", "\n".join(ficha_directorio(entrada, historial) for entrada in directorio))
        .replace("{{REGIONES}}", opciones)
        .replace("{{NACIONALES}}", str(nacionales))
        .replace("{{TOTAL_DIRECTORIO}}", str(len(directorio)))
        .replace("{{FUENTE_SUNEDU}}", escape(registro["fuente"]))
    )
    (RAIZ / "index.html").write_text(html, encoding="utf-8", newline="\n")
    print(f"Portada generada con {len(eventos)} fechas cotejadas y {len(directorio)} portales de admisión.")


if __name__ == "__main__":
    main()
