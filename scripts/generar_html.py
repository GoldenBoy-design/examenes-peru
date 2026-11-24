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


def fecha_calendario_html(fecha: date) -> str:
    mes = MESES[fecha.month - 1]
    return (
        f'<time datetime="{fecha.isoformat()}">'
        f'<span class="event-day">{fecha.day}</span> '
        f'<span class="event-month">{mes} {fecha.year}</span></time>'
    )


def logo_html(institucion: dict) -> str:
    logo = "/logos/pronabec.png" if institucion["id"] == "beca18" else f'/logos/{institucion["id"]}.png'
    if (RAIZ / logo.lstrip("/")).is_file():
        return (
            '<span class="institution-logo">'
            f'<img src="{escape(logo)}" alt="" width="52" height="52" loading="lazy" decoding="async">'
            '</span>'
        )
    return f'<span class="institution-logo logo-text" aria-hidden="true">{escape(institucion["siglas"][:4])}</span>'


def enlace_oficial(url: str, texto: str, contexto: str) -> str:
    destino = urlsplit(url)
    if destino.scheme != "https" or not destino.hostname:
        raise ValueError(f"Se requiere un enlace HTTPS institucional: {url}")
    etiqueta = escape(f"{texto} de {contexto}")
    return f'<a class="official-link" href="{escape(url)}" aria-label="{etiqueta}">{escape(texto)}</a>'


def tipo_institucion(institucion: dict) -> str:
    if institucion["id"] == "beca18":
        return "beca"
    return institucion["tipo"].replace("ú", "u")


def ficha_evento(evento: dict, instituciones: dict, sedes: dict) -> str:
    institucion = instituciones[evento["institucion"]]
    siglas = institucion["siglas"]
    proceso = escape(evento["proceso"])
    ubicacion = escape(evento.get("ubicacion", sedes.get(institucion["id"], institucion["provincia"])))
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
            <li class="event" data-fecha="{fecha.isoformat()}" data-tipo="{escape(tipo_institucion(institucion))}"
                data-apertura="{escape(apertura)}" data-cierre="{cierre}" data-hora-cierre="{hora_cierre}">
                <div class="event-date">{fecha_calendario_html(fecha)}<span class="event-state" hidden></span></div>
                <div class="event-detail">
                    {logo_html(institucion)}
                    <div>
                        <h3>{escape(siglas)}</h3>
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


def ficha_directorio(registro: dict, instituciones: dict) -> str:
    institucion = instituciones[registro["institucion"]]
    siglas = institucion["siglas"]
    nombre = escape(institucion["nombre"])
    sede = escape(registro.get("sede", institucion["provincia"]))
    tipo = "Pública" if tipo_institucion(institucion) == "publica" else "Privada"
    enlace = enlace_oficial(registro["portal"], registro.get("etiqueta", "Portal de admisión"), siglas)
    return f"""
            <li class="directory-item">
                <div class="directory-heading">
                    {logo_html(institucion)}
                    <div>
                        <h3>{escape(siglas)}</h3>
                        <p class="directory-location">{sede} · {tipo}</p>
                    </div>
                </div>
                <p class="directory-name">{nombre}</p>
                {enlace}
            </li>"""


def main():
    datos = json.loads((RAIZ / "data/cronogramas-verificados.json").read_text(encoding="utf-8"))
    registro = json.loads((RAIZ / "data/universidades.json").read_text(encoding="utf-8"))
    instituciones = {item["id"]: item for item in registro["universidades"]}
    plantilla = (RAIZ / "templates/index.template.html").read_text(encoding="utf-8")

    def orden_institucion(entrada):
        institucion = instituciones[entrada["institucion"]]
        return tipo_institucion(institucion) != "publica", institucion["siglas"]

    eventos = sorted(datos["eventos"], key=lambda evento: (evento["fecha"], orden_institucion(evento)))
    directorio = sorted(datos["directorio"], key=orden_institucion)
    sedes = {entrada["institucion"]: entrada["sede"] for entrada in directorio if "sede" in entrada}
    html = (
        plantilla
        .replace("{{ADSENSE}}", ADSENSE)
        .replace("{{FECHA_REVISION}}", fecha_html(datos["revision"]))
        .replace("{{EVENTOS}}", "\n".join(ficha_evento(evento, instituciones, sedes) for evento in eventos))
        .replace("{{DIRECTORIO}}", "\n".join(ficha_directorio(entrada, instituciones) for entrada in directorio))
    )
    (RAIZ / "index.html").write_text(html, encoding="utf-8", newline="\n")
    print(f"Portada generada con {len(eventos)} fechas cotejadas y {len(directorio)} portales de admisión.")


if __name__ == "__main__":
    main()
