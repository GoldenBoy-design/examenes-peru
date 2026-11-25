"""Genera las páginas de historial, los simulacros y el sitemap público."""

import json
from html import escape
from xml.etree import ElementTree as ET

from generar_html import (
    RAIZ, cargar_historial, cargar_padron, cargar_simulacros, enlace_oficial, fecha_html, logo_html,
)

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
    carpeta.mkdir(parents=True, exist_ok=True)
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


def pregunta_simulacro(pregunta: dict, numero: int) -> str:
    letras = "abcde"
    correcta = pregunta["correcta"]
    identificador = pregunta.get("numero", numero)
    alternativas = pregunta.get("opciones")
    etiquetas = list(letras.upper())
    estilo = "pregunta pregunta--cuadernillo"
    if alternativas:
        etiquetas = [f"{letra.upper()}. {escape(opcion)}" for letra, opcion in zip(letras, alternativas, strict=True)]
        estilo = "pregunta"
    opciones = "\n".join(
        f'                        <label><input type="radio" name="p{numero}" value="{letra}"> {etiqueta}</label>'
        for letra, etiqueta in zip(letras, etiquetas, strict=True)
    )
    return f'''
                <fieldset class="{estilo}" data-correcta="{letras[correcta]}">
                    <legend>{identificador}. {escape(pregunta["enunciado"])}</legend>
                    <div class="opciones">
{opciones}
                    </div>
                    <details>
                        <summary>Ver solución de la pregunta {identificador}</summary>
                        <p><strong>{etiquetas[correcta]}</strong></p>
                        <p>{escape(pregunta["solucion"])}</p>
                    </details>
                </fieldset>'''


def contenido_simulacro(simulacro: dict, siglas: str) -> str:
    numero = 1
    secciones = []
    resultados = []
    enlaces_secciones = []
    for indice, bloque in enumerate(simulacro["bloques"], start=1):
        area = f"bloque-{indice}"
        nombre = escape(bloque["nombre"])
        enlaces_secciones.append(f'<a href="#{area}">{nombre}</a>')
        lectura = f'                <div class="lectura"><p>{escape(bloque["lectura"])}</p></div>' if bloque.get("lectura") else ""
        fotos = []
        for foto in bloque.get("fotos", []):
            etiqueta = foto.get("etiqueta") or f'Página {simulacro.get("prefijo_pagina", "")}{foto["pagina"]}'
            fotos.append(f'<a href="{escape(foto["url"])}" target="_blank" rel="noopener">{escape(etiqueta)} en Facebook</a>')
        cuadernillo = f'                <p>{" · ".join(fotos)}</p>' if fotos else ""
        preguntas = [
            pregunta_simulacro(pregunta, n)
            for n, pregunta in enumerate(bloque["preguntas"], start=numero)
        ]
        numero += len(preguntas)
        secciones.append(f'''
            <section id="{area}" aria-labelledby="{area}-titulo">
                <h2 id="{area}-titulo">{nombre}</h2>
{lectura}
{cuadernillo}
{"".join(preguntas)}
            </section>''')
        resultados.append(f'<div><dt>{nombre}</dt><dd data-area="{area}"></dd></div>')
    observaciones = ""
    if simulacro.get("formato") == "cuadernillo":
        instrucciones = f'''
                <p>{numero - 1} preguntas corregibles. Abre las fotos del cuadernillo, localiza cada número y marca aquí la letra elegida. Facebook puede pedir que inicies sesión.</p>
                <p>Al terminar, corrige tus respuestas y consulta las soluciones elaboradas por Exámenes Perú.</p>'''
        notas = "".join(f"<li>{escape(nota)}</li>" for nota in simulacro["observaciones"])
        observaciones = f'                <details><summary>Observaciones sobre las preguntas</summary><ul>{notas}</ul></details>'
        etiqueta_fuente = simulacro.get("etiqueta_fuente", "Convocatoria oficial")
    else:
        instrucciones = f'''
                <p>{numero - 1} preguntas originales · Tiempo sugerido de {simulacro["minutos"]} minutos.</p>
                <p>Marca una alternativa por pregunta. Al terminar, corrige tus respuestas y abre las soluciones para revisar el procedimiento.</p>'''
        etiqueta_fuente = "Referencia oficial de admisión"
    fuente = enlace_oficial(simulacro["fuente"], etiqueta_fuente, siglas)
    return f'''
            <section aria-labelledby="instrucciones">
                <h2 id="instrucciones">{escape(simulacro["enfoque"])}</h2>
{instrucciones}
{observaciones}
                <nav class="simulacro-secciones" aria-label="Secciones del simulacro">
                    {" ".join(enlaces_secciones)} <a href="#revision">Revisar respuestas</a>
                </nav>
            </section>
{"".join(secciones)}
            <section aria-labelledby="revision">
                <h2 id="revision">Revisa tus respuestas</h2>
                <button type="button" id="corregir" hidden>Corregir simulacro</button>
                <div id="resultado" hidden>
                    <h3 id="titulo-resultado" tabindex="-1">Resultado</h3>
                    <p id="resumen-resultado" aria-live="polite"></p>
                    <dl>{"".join(resultados)}</dl>
                </div>
                <p>{fuente}</p>
                <p><a href="/simulacros/">Ver los simulacros de otras universidades</a></p>
            </section>'''


def generar_simulacros() -> tuple:
    instituciones = {item["id"]: item for item in cargar_padron()["universidades"]}
    rutas = ["/simulacros/"]
    tarjetas = {}
    simulacros = cargar_simulacros()
    for codigo, simulacro in sorted(simulacros.items(), key=lambda entrada: entrada[1].get("institucion", entrada[0])):
        institucion = instituciones[simulacro.get("institucion", codigo)]
        ruta = f"/simulacros/{codigo}/"
        rutas.append(ruta)
        titulo = simulacro.get("titulo", f'Simulacro de admisión {institucion["siglas"]}')
        enfoque = escape(simulacro["enfoque"])
        nombre = escape(institucion["nombre"])
        if simulacro.get("formato") == "cuadernillo":
            descripcion = f"{nombre} · Cuadernillo histórico con hoja de respuestas y soluciones explicadas."
        else:
            descripcion = f"{nombre} · Práctica original con corrección y soluciones explicadas."
        tarjeta = f'<li><strong><a href="{ruta}">{escape(titulo)}</a></strong><br>{enfoque}</li>'
        tarjetas.setdefault(institucion["id"], []).append(tarjeta)
        guardar_pagina(ruta, "simulacros.template.html", {
            "TITULO": escape(titulo),
            "CANONICAL": DOMINIO + ruta,
            "DESCRIPCION": descripcion,
            "SCRIPT": '    <script src="/practica-admision/practica.js" defer></script>',
            "MIGAS": f'<a href="/">Inicio</a> / <a href="/simulacros/">Simulacros</a> / {escape(institucion["siglas"])}',
            "CONTENIDO": contenido_simulacro(simulacro, institucion["siglas"]),
        })
    catalogo = "\n".join(
        f'            <section id="institucion-{codigo}"><h2>{escape(instituciones[codigo]["nombre"])}</h2>'
        f'<ul class="links">{"".join(fichas)}</ul></section>'
        for codigo, fichas in tarjetas.items()
    )
    guardar_pagina(rutas[0], "simulacros.template.html", {
        "TITULO": "Simulacros de admisión por universidad",
        "CANONICAL": DOMINIO + rutas[0],
        "DESCRIPCION": "Elige una universidad para resolver ejercicios originales o practicar con un cuadernillo histórico. Revisa tus respuestas y las soluciones.",
        "SCRIPT": "",
        "MIGAS": '<a href="/">Inicio</a> / Simulacros',
        "CONTENIDO": catalogo,
    })
    return tuple(rutas)


def generar_sitemap(rutas):
    mapa = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for ruta in rutas:
        pagina = RAIZ / ruta.strip("/") / "index.html"
        if not pagina.is_file():
            raise FileNotFoundError(f"Falta el HTML para la ruta pública {ruta}")
        url = ET.SubElement(mapa, "url")
        ET.SubElement(url, "loc").text = f"{DOMINIO}{ruta}"

    ET.indent(mapa, space="  ")
    with (RAIZ / "sitemap.xml").open("w", encoding="utf-8", newline="\n") as archivo:
        ET.ElementTree(mapa).write(archivo, encoding="unicode", xml_declaration=True)
    print(f"Sitemap generado con {len(rutas)} rutas editoriales.")


if __name__ == "__main__":
    generar_historiales()
    generar_sitemap(RUTAS + generar_simulacros())
