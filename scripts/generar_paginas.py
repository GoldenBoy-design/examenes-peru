"""Genera los historiales, simulacros, noticias y el sitemap público."""

import json
from html import escape
from xml.etree import ElementTree as ET

from generar_html import (
    RAIZ, cargar_historial, cargar_noticias, cargar_padron, cargar_simulacros,
    actividad_html, enlace_oficial, fecha_html, foto_noticia, imagen_noticia, logo_html, ruta_noticia,
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


def material_pregunta(pregunta: dict) -> str:
    contenido = []
    if pregunta.get("datos"):
        datos = "".join(f"<li>{escape(dato)}</li>" for dato in pregunta["datos"])
        contenido.append(f'                    <ul class="datos-pregunta">{datos}</ul>')
    if pregunta.get("figura") == "cuadrados-superpuestos":
        contenido.append('''                    <div class="cuadrados-superpuestos" role="img"
                         aria-label="Dos cuadrados superpuestos. El cuadrado girado tiene P en el vértice superior y Q en el inferior.">
                        <span class="rotulo-p" aria-hidden="true">P</span>
                        <span class="rotulo-q" aria-hidden="true">Q</span>
                    </div>''')
    return "\n".join(contenido)


def pregunta_simulacro(pregunta: dict, numero: int) -> str:
    letras = "abcde"
    correcta = pregunta["correcta"]
    identificador = pregunta.get("numero", numero)
    etiquetas = [
        f"{letra.upper()}. {escape(opcion)}"
        for letra, opcion in zip(letras, pregunta["opciones"], strict=True)
    ]
    opciones = "\n".join(
        f'                        <label><input type="radio" name="p{numero}" value="{letra}"> {etiqueta}</label>'
        for letra, etiqueta in zip(letras, etiquetas, strict=True)
    )
    return f'''
                <fieldset class="pregunta" data-correcta="{letras[correcta]}">
                    <legend>{identificador}. {escape(pregunta["enunciado"])}</legend>
{material_pregunta(pregunta)}
                    <div class="opciones">
{opciones}
                    </div>
                    <details>
                        <summary>Ver solución de la pregunta {identificador}</summary>
                        <p><strong>{etiquetas[correcta]}</strong></p>
                        <p>{escape(pregunta["solucion"])}</p>
                    </details>
                </fieldset>'''


def preguntas_para_revision(preguntas: list) -> str:
    if not preguntas:
        return ""
    ejercicios = []
    for pregunta in preguntas:
        opciones = "".join(f"<li>{escape(opcion)}</li>" for opcion in pregunta["opciones"])
        ejercicios.append(f'''
                    <article class="pregunta-revision">
                        <p><strong>{pregunta["numero"]}. {escape(pregunta["enunciado"])}</strong></p>
{material_pregunta(pregunta)}
                        <ol type="A">{opciones}</ol>
                        <p>{escape(pregunta["solucion"])}</p>
                    </article>''')
    return f'''
                <details class="revision-cuadernillo">
                    <summary>Preguntas para revisión sin puntuación</summary>
{"".join(ejercicios)}
                </details>'''


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
        preguntas = [
            pregunta_simulacro(pregunta, n)
            for n, pregunta in enumerate(bloque["preguntas"], start=numero)
        ]
        numero += len(preguntas)
        secciones.append(f'''
            <section id="{area}" aria-labelledby="{area}-titulo">
                <h2 id="{area}-titulo">{nombre}</h2>
{lectura}
{"".join(preguntas)}
            </section>''')
        resultados.append(f'<div><dt>{nombre}</dt><dd data-area="{area}"></dd></div>')
    if simulacro.get("formato") == "cuadernillo":
        instrucciones = f'''
                <p>{numero - 1} preguntas digitalizadas con su numeración original. Marca una alternativa por pregunta y corrige tus respuestas al terminar.</p>'''
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
{preguntas_para_revision(simulacro.get("revision", []))}
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
            descripcion = f"{nombre} · Cuadernillo digitalizado con alternativas, corrección y soluciones explicadas."
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


def generar_noticias() -> tuple:
    ruta_indice = "/noticias/"
    titulo_indice = "Noticias de admisión universitaria"
    bajada_indice = "Fechas, modalidades y avisos de inscripción, con enlaces a las universidades que los publican."
    noticias = cargar_noticias()
    instituciones = {item["id"]: item for item in cargar_padron()["universidades"]}
    actividad = actividad_html("consultar")
    rutas, tarjetas = [ruta_indice], []
    for noticia in sorted(noticias, key=lambda item: item["publicado"], reverse=True):
        institucion = instituciones[noticia["institucion"]]
        siglas = escape(institucion["siglas"])
        ruta = ruta_noticia(noticia)
        rutas.append(ruta)
        titulo, resumen = escape(noticia["titulo"]), escape(noticia["resumen"])
        lugar = escape(noticia["lugar"])
        entrada = escape(noticia["entrada"])
        pie_foto = escape(noticia["pie_foto"])
        foto = foto_noticia(noticia, "news-article-photo", "(max-width: 1100px) 94vw, 1056px", True)
        modalidad = escape(noticia["modalidad"])
        fechas = "\n".join(
            f"                        <dt>{escape(etiqueta)}</dt><dd>{fecha_html(dia)}</dd>"
            for etiqueta, dia in noticia["fechas"]
        )
        secciones = "\n".join(
            f'                    <section class="news-section"><h2>{escape(encabezado)}</h2><p>{escape(parrafo)}</p></section>'
            for encabezado, parrafo in noticia["secciones"]
        )
        fuentes = "\n".join(
            f"                            <li>{enlace_oficial(url, nombre, institucion['siglas'])}</li>"
            for nombre, url in noticia["fuentes"]
        )
        publicado = fecha_html(noticia["publicado"])
        relacionados = "\n".join(
            f"""                <li>
                    <a href="{escape(ruta_noticia(otra))}">
                        <img src="{escape(imagen_noticia(otra, miniatura=True))}" alt="" width="640" height="427" loading="lazy" decoding="async">
                        <span>{escape(otra["titulo"])}</span>
                    </a>
                </li>"""
            for otra in [otra for otra in noticias if otra["slug"] != noticia["slug"]][:2]
        )
        contenido = f"""        <article class="news-article">
            <header class="news-article-header">
                <div class="news-article-label">
                    {logo_html(institucion)}
                    <div><p>{siglas} · {lugar}</p><p>{modalidad}</p></div>
                </div>
                <h1>{titulo}</h1>
                <p class="news-article-lead">{resumen}</p>
                <div class="news-byline">
                    <span class="brand-mark" aria-hidden="true">EP</span>
                    <div><p><strong>Redacción de Exámenes Perú</strong></p><p>Publicado el {publicado}</p></div>
                </div>
            </header>
            <figure class="news-figure">
                {foto}
                <figcaption><span>{pie_foto}</span><span>Ilustración generada con IA</span></figcaption>
            </figure>
            <div class="news-article-grid">
                <aside class="news-keydates" aria-labelledby="news-dates-title">
                    <h2 id="news-dates-title">Agenda del postulante</h2>
                    <dl>
{fechas}
                    </dl>
                </aside>
                <div class="news-article-text">
                    <p class="news-opening">{entrada}</p>
{secciones}
                    <section class="news-section news-sources">
                        <h2>Fuentes oficiales</h2>
                        <ul>
{fuentes}
                        </ul>
                    </section>
                </div>
            </div>
        </article>
        <section class="news-related" aria-labelledby="news-related-title">
            <h2 id="news-related-title">Más noticias de admisión</h2>
            <ul>
{relacionados}
            </ul>
        </section>"""
        guardar_pagina(ruta, "noticias.template.html", {
            "TITULO": titulo, "DESCRIPCION": resumen, "CANONICAL": f"{DOMINIO}{ruta}",
            "TIPO": "article", "NAV_ACTIVA": "", "CONTENIDO": contenido, "ACTIVIDAD": actividad,
            "OG_IMAGEN": f'    <meta property="og:image" content="{DOMINIO}{escape(imagen_noticia(noticia))}">',
            "MIGAS": '<a href="/">Inicio</a> / <a href="/noticias/">Noticias</a>',
        })
        tarjetas.append(f"""            <article class="news-card">
                <img src="{escape(imagen_noticia(noticia, miniatura=True))}" alt="" width="640" height="427" loading="lazy" decoding="async">
                <div>
                    <p class="story-kicker">{siglas} · {lugar}</p>
                    <h2><a href="{escape(ruta)}">{titulo}</a></h2>
                    <p class="news-card-date">Publicado el {publicado}</p>
                    <p class="story-summary">{resumen}</p>
                </div>
            </article>""")

    lista = "\n".join(tarjetas)
    contenido_indice = f"""        <header class="news-index-hero">
            <h1>{titulo_indice}</h1>
            <p>{bajada_indice}</p>
        </header>
        <div class="news-index">
{lista}
        </div>"""
    guardar_pagina(ruta_indice, "noticias.template.html", {
        "TITULO": titulo_indice, "DESCRIPCION": bajada_indice, "CANONICAL": f"{DOMINIO}{ruta_indice}",
        "TIPO": "website", "NAV_ACTIVA": ' aria-current="page"', "CONTENIDO": contenido_indice,
        "OG_IMAGEN": "", "ACTIVIDAD": actividad,
        "MIGAS": '<a href="/">Inicio</a> / <span aria-current="page">Noticias</span>',
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
    generar_sitemap(RUTAS + generar_simulacros() + generar_noticias())
