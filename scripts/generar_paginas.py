"""Genera sitemap.xml con las rutas editoriales públicas del proyecto."""

from pathlib import Path
from xml.etree import ElementTree as ET

RAIZ = Path(__file__).resolve().parents[1]
DOMINIO = "https://examenesperu.netlify.app"
RUTAS = (
    "/",
    "/acerca-de/",
    "/guia-preparacion-examen-admision-peru/",
    "/practica-admision/",
    "/privacidad/",
    "/uni/",
)


def main():
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
    main()
