"""
Detector de novedades de admisión vía RSS (Google News).

Por cada universidad en data/universidades.json, busca noticias recientes
con palabras clave de admisión y las compara contra lo que ya sabemos
(fecha de examen, estado del proceso). No modifica el JSON directamente:
solo genera un reporte (novedades.json) para revisión — humana o, más
adelante, para pasarlo al paso de extracción con IA.

Estrategia de búsqueda (ampliada):
1. Varias variantes de consulta por universidad (nombre completo, siglas,
   "examen"/"vacantes" además de "admisión") — antes solo había una consulta
   exacta con el nombre completo + "admisión", lo que dejaba fuera
   coberturas que no repetían esa redacción exacta.
2. Una consulta "site:gob.pe" por universidad, para priorizar fuentes
   oficiales del Estado peruano cuando existen (no hay un feed RSS único
   del gobierno con cronogramas de admisión — SUNEDU/MINEDU no lo
   centralizan — así que esto es lo más cercano a "fuente oficial" que se
   puede pedir vía RSS).
3. Una consulta "red ancha" (sin universidad específica) que busca
   cobertura general de admisión universitaria en Perú y luego revisa si
   el titular menciona el nombre o las siglas de alguna universidad
   conocida. Esto atrapa noticias que no calzan con ninguna consulta
   específica (medios chicos, redacciones distintas, etc.)

Requiere: pip install feedparser

Uso:
    python scripts/detectar_rss.py
"""

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import feedparser

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
SALIDA_PATH = RAIZ / "data" / "novedades.json"
VISTOS_PATH = RAIZ / "data" / "rss_vistos.json"

DIAS_RECIENCIA = 60  # solo para filtrar ruido si el script no corrió en mucho tiempo
PAUSA_ENTRE_CONSULTAS = 1  # segundos, para no golpear Google News RSS muy rápido

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


def _parsear_feed(url: str):
    feed = feedparser.parse(url)
    limite = datetime.now() - timedelta(days=DIAS_RECIENCIA)

    resultados = []
    for entrada in feed.entries:
        if not getattr(entrada, "published_parsed", None):
            continue
        fecha_pub = datetime(*entrada.published_parsed[:6])
        if fecha_pub < limite:
            continue

        titulo_original = entrada.title
        titulo_comparar = titulo_original.lower()

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


def _consultar(query: str):
    url = f'https://news.google.com/rss/search?q={quote(query)}&hl=es-419&gl=PE&ceid=PE:es-419'
    return _parsear_feed(url)


def variantes_de_consulta(nombre_universidad: str, siglas: str, anio: int):
    """Genera varias formas de buscar la misma universidad, para no
    depender de que un medio repita exactamente 'admisión' + nombre completo."""
    return [
        f'"{nombre_universidad}" admisión {anio} Perú',
        f'{siglas} admisión {anio} Perú',
        f'"{nombre_universidad}" examen OR vacantes {anio}',
        f'"{nombre_universidad}" cronograma admisión site:gob.pe',
    ]


def buscar_noticias(nombre_universidad: str, siglas: str):
    """Consulta varias variantes del RSS de Google News para una universidad
    y devuelve los resultados combinados y sin duplicados (por link)."""
    anio = datetime.now().year
    vistos_en_esta_busqueda = set()
    combinados = []

    for consulta in variantes_de_consulta(nombre_universidad, siglas, anio):
        try:
            resultados = _consultar(consulta)
        except Exception as e:
            print(f"    ⚠️  Error en variante de consulta '{consulta}': {e}")
            continue
        for r in resultados:
            if r["link"] not in vistos_en_esta_busqueda:
                vistos_en_esta_busqueda.add(r["link"])
                combinados.append(r)
        time.sleep(PAUSA_ENTRE_CONSULTAS)

    return combinados


def buscar_red_ancha(universidades: list, anio: int):
    """Una consulta general de admisión universitaria en Perú, sin atarse
    a una universidad específica. Devuelve un dict {siglas: [noticias]}
    para las universidades cuyo nombre o siglas aparezcan en el titular."""
    query = f'admisión universidad Perú {anio} examen fecha cronograma'
    try:
        resultados = _consultar(query)
    except Exception as e:
        print(f"  ⚠️  Error en la consulta de red ancha: {e}")
        return {}

    encontrados_por_universidad = {}
    for r in resultados:
        titulo_lower = r["titulo"].lower()
        for u in universidades:
            nombre_lower = u["nombre"].lower()
            siglas = u["siglas"]
            # Coincide por nombre completo, o por siglas como palabra suelta
            # (evita que "UNI" matchee dentro de otra palabra)
            if nombre_lower in titulo_lower or re.search(rf'\b{re.escape(siglas.lower())}\b', titulo_lower):
                encontrados_por_universidad.setdefault(siglas, []).append(r)

    return encontrados_por_universidad


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
    anio = datetime.now().year
    vistos = cargar_vistos()
    vistos_nuevos = set(vistos)

    novedades = {"generado": hoy, "universidades": {}}
    noticias_por_universidad = {u["siglas"]: [] for u in data["universidades"]}

    for u in data["universidades"]:
        siglas = u["siglas"]
        print(f"Buscando noticias de {siglas}...")
        try:
            noticias = buscar_noticias(u["nombre"], siglas)
        except Exception as e:
            print(f"  ⚠️  Error consultando RSS para {siglas}: {e}")
            noticias = []
        noticias_por_universidad[siglas].extend(noticias)

    print("Buscando cobertura general de admisión (red ancha)...")
    red_ancha = buscar_red_ancha(data["universidades"], anio)
    for siglas, noticias in red_ancha.items():
        noticias_por_universidad.setdefault(siglas, []).extend(noticias)
        print(f"  🌐 red ancha sumó {len(noticias)} noticia(s) candidata(s) para {siglas}")

    for u in data["universidades"]:
        siglas = u["siglas"]
        # Dedup por link entre todas las variantes + red ancha
        vistos_en_esta_universidad = set()
        noticias_unicas = []
        for n in noticias_por_universidad.get(siglas, []):
            if n["link"] not in vistos_en_esta_universidad:
                vistos_en_esta_universidad.add(n["link"])
                noticias_unicas.append(n)

        # Filtramos las que ya reportamos en una corrida anterior
        noticias_nuevas = [n for n in noticias_unicas if n["link"] not in vistos]
        for n in noticias_nuevas:
            vistos_nuevos.add(n["link"])

        if noticias_nuevas:
            novedades["universidades"][siglas] = {
                "estado_actual_json": u.get("estado_proceso"),
                "fechas_actuales_json": u.get("fechas_examen"),
                "noticias_encontradas": noticias_nuevas,
            }
            print(f"  🔔 {siglas}: {len(noticias_nuevas)} noticia(s) NUEVA(S) desde la última corrida")
        elif noticias_unicas:
            print(f"  — {siglas}: {len(noticias_unicas)} noticia(s) encontrada(s), pero ya reportadas antes")
        else:
            print(f"  — {siglas}: sin novedades")

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