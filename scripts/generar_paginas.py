"""Genera las páginas de historial y el sitemap público."""

import json
from html import escape
from xml.etree import ElementTree as ET

from generar_html import RAIZ, cargar_historial, cargar_padron, enlace_oficial, fecha_html, logo_html

DOMINIO = "https://examenesperu.netlify.app"
RUTAS = (
    "/",
    "/acerca-de/",
    "/guia-preparacion-examen-admision-peru/",
    "/historial/",
    "/practica-admision/",
    "/privacidad/",
    "/san-marcos/",
    "/uni/",
)


def guardar_pagina(ruta: str, plantilla: str, campos: dict):
    html = (RAIZ / "templates" / plantilla).read_text(encoding="utf-8")
    for nombre, valor in campos.items():
        html = html.replace("{{" + nombre + "}}", str(valor))
    carpeta = RAIZ / ruta.strip("/")
    carpeta.mkdir(exist_ok=True)
    (carpeta / "index.html").write_text(html, encoding="utf-8", newline="\n")


def contenido_ciclo(ciclo: dict, siglas: str) -> str:
    jornadas = "".join(
        f'<li>{fecha_html(jornada["fecha"])}<span>{escape(jornada["detalle"])}</span></li>'
        for jornada in sorted(ciclo["jornadas"], key=lambda jornada: jornada["fecha"])
    )
    recursos = "".join(
        f'<li>{enlace_oficial(recurso["url"], recurso["titulo"], siglas)}</li>'
        for recurso in ciclo["recursos"]
    )
    fechas = (
        f'<div><p class="archive-label">Jornadas de examen</p><ol class="archive-dates">{jornadas}</ol></div>'
        if jornadas else ""
    )
    return f'''
                            <p>{escape(ciclo["descripcion"])}</p>
                            <div class="archive-documents">{fechas}
                                <div><p class="archive-label">Fuentes y documentos</p><ul class="archive-links">{recursos}</ul></div>
                            </div>'''


def tarjeta_archivo(universidad: dict, ciclos: list) -> str:
    siglas = universidad["siglas"]
    periodos = "\n".join(
        f'<section class="archive-cycle"><h3>{escape(ciclo["periodo"])}</h3>{contenido_ciclo(ciclo, siglas)}</section>'
        for ciclo in ciclos
    )
    portal = enlace_oficial(universidad["portal"], universidad["etiqueta"], siglas)
    total = f"{len(ciclos)} ciclos" if len(ciclos) > 1 else "1 ciclo o archivo"
    return f'''
                    <details class="archive-item" id="{escape(universidad["id"])}">
                        <summary class="archive-summary">
                            {logo_html(universidad)}
                            <span class="archive-identity"><strong>{escape(universidad["nombre"])}</strong>
                            <span>{escape(siglas)} · {escape(universidad["sede"])}</span></span>
                            <span class="archive-period-count">{total}</span>
                            <span class="archive-toggle" aria-hidden="true"></span>
                        </summary>
                        <div class="archive-panel">{periodos}
                            <p class="archive-source">{portal}</p>
                        </div>
                    </details>'''


def ficha_ciclo_marcos(ciclo: dict, primero: bool) -> str:
    jornadas = len(ciclo["jornadas"])
    total = f"{jornadas} jornadas" if jornadas > 1 else "1 jornada"
    abierto = " open" if primero else ""
    return f'''
                        <details class="archive-item" id="ciclo-{escape(ciclo["periodo"].lower())}"{abierto}>
                            <summary class="archive-summary">
                                <span class="archive-identity"><strong>Admisión {escape(ciclo["periodo"])}</strong></span>
                                <span class="archive-period-count">{total}</span>
                                <span class="archive-toggle" aria-hidden="true"></span>
                            </summary>
                            <div class="archive-panel">{contenido_ciclo(ciclo, "UNMSM")}
                            </div>
                        </details>'''


def fila_puntajes(escuela: dict) -> str:
    nombre = escape(escuela["escuela"])
    intervalo = []
    for limite in ("minimo", "maximo"):
        valor = escuela[limite]
        texto = escape(valor.replace(".", ",")) if valor is not None else "—"
        intervalo.append(f'<td data-score="{escape(valor or "")}">{texto}</td>')
    conteo = escuela["puntajes"]
    cantidad = f"{conteo} puntajes" if conteo != 1 else "1 puntaje"
    return (
        f'                                <tr><th scope="row"><a href="{escape(escuela["fuente"])}">{nombre}</a>'
        f'<span>{cantidad} con vacante</span></th>{"".join(intervalo)}</tr>'
    )


def generar_historiales():
    padron = cargar_padron()
    historial = cargar_historial()
    archivos = [
        (universidad, historial[universidad["id"]])
        for universidad in sorted(padron["universidades"], key=lambda u: u["siglas"])
        if universidad["id"] in historial and universidad["id"] != "unmsm"
    ]
    guardar_pagina("/historial/", "historial.template.html", {
        "ARCHIVOS": "\n".join(tarjeta_archivo(universidad, ciclos) for universidad, ciclos in archivos),
        "CANTIDAD_ARCHIVOS": len(archivos),
    })

    datos = json.loads((RAIZ / "data/puntajes-san-marcos.json").read_text(encoding="utf-8"))
    escuelas = datos["escuelas"]
    guardar_pagina("/san-marcos/", "san-marcos.template.html", {
        "CONVOCATORIAS": "\n".join(ficha_ciclo_marcos(ciclo, i == 0) for i, ciclo in enumerate(historial["unmsm"])),
        "CICLO": escape(datos["ciclo"]),
        "ESCUELAS": len(escuelas),
        "PUNTAJES": format(sum(escuela["puntajes"] for escuela in escuelas), ",").replace(",", "&nbsp;"),
        "FILAS_PUNTAJES": "\n".join(fila_puntajes(escuela) for escuela in escuelas),
        "FUENTE_PUNTAJES": escape(datos["fuente"]),
        "REVISION_PUNTAJES": fecha_html(datos["revision"]),
    })


def generar_sitemap():
    mapa = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for ruta in RUTAS:
        pagina = RAIZ / ruta.strip("/") / "index.html"
        if not pagina.is_file():
            raise FileNotFoundError(f"Falta el HTML para la ruta pública {ruta}")
        url = ET.SubElement(mapa, "url")
        ET.SubElement(url, "loc").text = f"{DOMINIO}{ruta}"

    ET.indent(mapa, space="  ")
    with (RAIZ / "sitemap.xml").open("w", encoding="utf-8", newline="\n") as archivo:
        ET.ElementTree(mapa).write(archivo, encoding="unicode", xml_declaration=True)
    print(f"Sitemap generado con {len(RUTAS)} rutas editoriales.")


if __name__ == "__main__":
    generar_historiales()
    generar_sitemap()
