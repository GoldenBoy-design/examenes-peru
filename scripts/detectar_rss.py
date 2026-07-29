"""
Detector de novedades de admisión vía RSS (Google News).

Por cada universidad en data/universidades.json, busca noticias recientes
con palabras clave de admisión y las compara contra lo que ya sabemos
(fecha de examen, estado del proceso). No modifica el JSON directamente:
solo genera un reporte (novedades.json) para revisión — humana o, más
adelante, para pasarlo al paso de extracción con IA.

Requiere: pip install feedparser

Uso:
    python scripts/detectar_rss.py
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import feedparser

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
SALIDA_PATH = RAIZ / "data" / "novedades.json"
VISTOS_PATH = RAIZ / "data" / "rss_vistos.json"

DIAS_RECIENCIA = 60  # solo para filtrar ruido si el script no corrió en mucho tiempo

# Palabras que indican cobertura de un examen YA rendido — no nos interesa
# para actualizar fechas futuras, aunque mencione "admisión"
PALABRAS_NEGATIVAS = [
    "resultados", "ingresantes", "puntaje", "ingresó", "ingreso a la",
    "lista de ingresantes", "fraude", "suplant",
]

# Ya no exigimos una lista blanca de palabras positivas: era demasiado
# estricta y descartaba anuncios reales con otra redacción. Dejamos pasar
# cualquier noticia que NO sea cobertura de resultados/fraude, y confiamos
# en el paso de extracción con IA (extraer_ia.py) para decidir si trae un
# dato de cronograma real o no.


def buscar_noticias(nombre_universidad: str, siglas: str):
    """Consulta el RSS de Google News usando nombre completo + Perú
    para evitar colisiones con siglas iguales de otros países."""
    anio = datetime.now().year
    consulta = f'"{nombre_universidad}" admisión {anio} Perú'
    url = f'https://news.google.com/rss/search?q={quote(consulta)}&hl=es-419&gl=PE&ceid=PE:es-419'

    feed = feedparser.parse(url)
    limite = datetime.now() - timedelta(days=DIAS_RECIENCIA)

    resultados = []
    for entrada in feed.entries:
        # feedparser da published_parsed como struct_time
        if not getattr(entrada, "published_parsed", None):
            continue
        fecha_pub = datetime(*entrada.published_parsed[:6])
        if fecha_pub < limite:
            continue

        titulo_original = entrada.title
        titulo_comparar = titulo_original.lower()

        # No debe ser cobertura de resultados/fraude ya ocurridos
        if any(n in titulo_comparar for n in PALABRAS_NEGATIVAS):
            continue

        resultados.append({
            "titulo": titulo_original,
            "fuente": getattr(entrada, "source", {}).get("title", "desconocida")
                      if hasattr(entrada, "source") else "desconocida",
            "fecha_publicacion": fecha_pub.isoformat(),
            "link": entrada.link,
        })

    return resultados


def cargar_vistos() -> set:
    if not VISTOS_PATH.exists():
        return set()
    return set(json.loads(VISTOS_PATH.read_text(encoding="utf-8")))


def guardar_vistos(vistos: set):
    # Guardamos como lista; no hace falta limitar el tamaño para el volumen
    # de noticias que maneja este proyecto.
    VISTOS_PATH.write_text(
        json.dumps(sorted(vistos), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    hoy = datetime.now().isoformat()
    vistos = cargar_vistos()
    vistos_nuevos = set(vistos)

    novedades = {"generado": hoy, "universidades": {}}

    for u in data["universidades"]:
        siglas = u["siglas"]
        print(f"Buscando noticias de {siglas}...")
        try:
            noticias = buscar_noticias(u["nombre"], siglas)
        except Exception as e:
            print(f"  ⚠️  Error consultando RSS para {siglas}: {e}")
            continue

        # Filtramos las que ya reportamos en una corrida anterior
        noticias_nuevas = [n for n in noticias if n["link"] not in vistos]
        for n in noticias_nuevas:
            vistos_nuevos.add(n["link"])

        if noticias_nuevas:
            novedades["universidades"][siglas] = {
                "estado_actual_json": u.get("estado_proceso"),
                "fechas_actuales_json": u.get("fechas_examen"),
                "noticias_encontradas": noticias_nuevas,
            }
            print(f"  🔔 {len(noticias_nuevas)} noticia(s) NUEVA(S) desde la última corrida")
        elif noticias:
            print(f"  — {len(noticias)} noticia(s) encontrada(s), pero ya reportadas antes")
        else:
            print("  — sin novedades")

    SALIDA_PATH.write_text(
        json.dumps(novedades, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    guardar_vistos(vistos_nuevos)

    total = len(novedades["universidades"])
    print(f"\n✅ Reporte guardado en {SALIDA_PATH.relative_to(RAIZ)}")
    print(f"   {total} universidad(es) con novedades genuinamente nuevas.")
    if total:
        print("   Revísalas antes de actualizar universidades.json a mano,")
        print("   o espera al siguiente paso (extracción automática con IA).")


if __name__ == "__main__":
    main()
