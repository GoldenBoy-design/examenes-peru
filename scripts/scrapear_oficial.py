"""
Scraper del "banco de universidades": visita la web OFICIAL de cada
universidad (campo url_oficial en data/universidades.json), sigue enlaces
internos relacionados a admisión (cronograma, costos, inscripción), extrae
el texto y le pide a la IA (Groq) que lo estructure y PARAFRASEE.

A diferencia de detectar_rss.py + extraer_ia.py (que solo miran titulares
de noticias), este script lee la fuente primaria: la propia universidad.

Escribe SIEMPRE un reporte en data/propuestas_scraper.json con todo lo
encontrado. Además, aplica automáticamente a universidades.json los campos
que pasan validaciones estrictas (fecha ISO real, costo numérico razonable,
etc.) — igual que ya hace extraer_ia.py con las fechas de noticias. Lo que
no pasa la validación queda solo en el reporte para revisión.

Requiere:
    pip install requests beautifulsoup4
    Variable de entorno GROQ_API_KEY

Uso:
    python scripts/scrapear_oficial.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
SALIDA_PATH = RAIZ / "data" / "propuestas_scraper.json"

MODELO = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
API_KEY = os.environ.get("GROQ_API_KEY")
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; examenes-peru-bot/1.0; "
                  "+https://github.com/GoldenBoy-design/examenes-peru)"
}

TIMEOUT = 20
PAUSA_ENTRE_SITIOS = 2
PAUSA_ENTRE_LLAMADAS_IA = 3
MAX_REINTENTOS_IA = 4
MAX_SUBPAGINAS = 4          # además de la home
MAX_CARACTERES_TEXTO = 9000  # tope de texto que le mandamos a la IA por universidad

# Palabras clave para decidir qué enlaces de la web oficial vale la pena seguir
PALABRAS_CLAVE_ENLACES = [
    "admision", "admisión", "cronograma", "costo", "costos", "pago",
    "inscrip", "vacante", "proceso", "calendario", "postulante", "postula",
    "requisito", "prospecto", "tasa",
]

FECHA_ISO_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

PROMPT_BASE = """Eres un asistente que extrae datos de admisión desde el texto de la propia web oficial de una universidad peruana.

Universidad: "{universidad}"
Fecha de hoy: {hoy}

Texto extraído de su web oficial (puede incluir varias páginas, separadas por "---PÁGINA---"):
\"\"\"
{texto}
\"\"\"

Extrae SOLO datos que estén EXPLÍCITAMENTE en el texto. Nunca inventes ni calcules cifras que no aparezcan escritas. Si un dato no aparece, usa null.

Responde SOLO con este JSON (sin markdown, sin texto adicional):
{{
  "fechas_examen": ["YYYY-MM-DD", "..."] o [],
  "inscripcion_inicio": "YYYY-MM-DD o null",
  "inscripcion_fin": "YYYY-MM-DD o null",
  "costo_prospecto": número en soles o null,
  "costo_inscripcion_estatal": número en soles o null,
  "costo_inscripcion_privado": número en soles o null,
  "modalidad": "texto breve o null",
  "resumen_parafraseado": "1-2 frases en tus propias palabras resumiendo el proceso vigente (NUNCA copies frases textuales de la web), o null si no hay info suficiente",
  "confianza": "alta" | "media" | "baja"
}}

Reglas estrictas:
- Las fechas DEBEN ser calendario exactas en formato YYYY-MM-DD. Si el texto solo dice un mes o es ambiguo, no la incluyas.
- Los costos deben ser números en soles peruanos tal como aparecen escritos, sin inventar ni redondear de más.
- "resumen_parafraseado" debe ser una reescritura completa en tus propias palabras, nunca una copia ni una paráfrasis cercana de la redacción original.
- Si el texto no trae información clara de admisión (p.ej. es solo el menú de navegación), responde con todos los campos en null/[] y "confianza": "baja".
"""


def verificar_configuracion():
    if not API_KEY:
        print("❌ No encontré la variable de entorno GROQ_API_KEY.")
        print("   Consigue una gratis en https://console.groq.com/keys")
        sys.exit(1)


def descargar(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"    ⚠️  {url} respondió {resp.status_code}")
            return None
        return resp.text
    except requests.exceptions.RequestException as e:
        print(f"    ⚠️  Error de red en {url}: {e}")
        return None


def extraer_texto_y_enlaces(html: str, url_base: str):
    sopa = BeautifulSoup(html, "html.parser")

    for tag in sopa(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    texto = sopa.get_text(separator=" ", strip=True)
    texto = re.sub(r"\s+", " ", texto)

    dominio_base = urlparse(url_base).netloc
    enlaces_relevantes = []
    vistos = set()
    for a in sopa.find_all("a", href=True):
        href = a["href"]
        texto_enlace = (a.get_text() or "").lower()
        href_absoluto = urljoin(url_base, href)
        parsed = urlparse(href_absoluto)

        if parsed.netloc != dominio_base:
            continue  # solo seguimos dentro del mismo dominio oficial
        if parsed.scheme not in ("http", "https"):
            continue
        if href_absoluto in vistos:
            continue

        combinado = f"{texto_enlace} {href.lower()}"
        if any(palabra in combinado for palabra in PALABRAS_CLAVE_ENLACES):
            vistos.add(href_absoluto)
            enlaces_relevantes.append(href_absoluto)

    return texto, enlaces_relevantes


def recolectar_texto_sitio(url_oficial: str) -> str:
    """Descarga la home + hasta MAX_SUBPAGINAS enlaces relevantes del mismo
    dominio, y devuelve el texto combinado (recortado)."""
    html_home = descargar(url_oficial)
    if html_home is None:
        return ""

    texto_home, enlaces = extraer_texto_y_enlaces(html_home, url_oficial)
    partes = [f"---PÁGINA--- ({url_oficial})\n{texto_home}"]

    for enlace in enlaces[:MAX_SUBPAGINAS]:
        time.sleep(1)
        html_sub = descargar(enlace)
        if html_sub is None:
            continue
        texto_sub, _ = extraer_texto_y_enlaces(html_sub, enlace)
        partes.append(f"---PÁGINA--- ({enlace})\n{texto_sub}")

    texto_total = "\n\n".join(partes)
    return texto_total[:MAX_CARACTERES_TEXTO]


def llamar_ia(prompt: str):
    payload = {
        "model": MODELO,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}

    for intento in range(1, MAX_REINTENTOS_IA + 1):
        try:
            resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=45)
        except requests.exceptions.RequestException as e:
            print(f"    ⚠️  Error de red al llamar a Groq: {e}")
            return None

        if resp.status_code == 429:
            espera = 15 * intento
            print(f"    ⏳ Rate limit (429). Esperando {espera}s...")
            time.sleep(espera)
            continue

        if resp.status_code != 200:
            print(f"    ⚠️  Groq respondió {resp.status_code}: {resp.text[:300]}")
            return None

        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            return None

    return None


def limpiar_json_de_texto(texto: str):
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.lower().startswith("json"):
            texto = texto[4:]
    try:
        return json.loads(texto.strip())
    except json.JSONDecodeError:
        return None


def fecha_es_valida(fecha_str) -> bool:
    if not fecha_str or not isinstance(fecha_str, str):
        return False
    if not FECHA_ISO_REGEX.match(fecha_str):
        return False
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def costo_es_razonable(valor) -> bool:
    """Filtro de sanidad: un costo de admisión en Perú no debería ser
    absurdamente alto ni negativo. Evita que la IA aplique un número mal
    leído de la página (p.ej. un año o un teléfono)."""
    if valor is None:
        return False
    if not isinstance(valor, (int, float)):
        return False
    return 0 < valor <= 2000


def aplicar_hallazgo(universidad: dict, hallazgo: dict) -> list:
    """Aplica al dict de la universidad SOLO los campos que pasan
    validación. Devuelve la lista de campos que sí se aplicaron."""
    aplicados = []

    if hallazgo.get("confianza") == "baja":
        return aplicados

    fechas_nuevas = [f for f in hallazgo.get("fechas_examen") or [] if fecha_es_valida(f)]
    for f in fechas_nuevas:
        if f not in universidad.get("fechas_examen", []):
            universidad.setdefault("fechas_examen", []).append(f)
            universidad["fechas_examen"].sort()
            aplicados.append(f"fecha_examen:{f}")

    if fecha_es_valida(hallazgo.get("inscripcion_inicio")):
        universidad.setdefault("inscripcion", {})["inicio"] = hallazgo["inscripcion_inicio"]
        aplicados.append("inscripcion.inicio")
    if fecha_es_valida(hallazgo.get("inscripcion_fin")):
        universidad.setdefault("inscripcion", {})["fin"] = hallazgo["inscripcion_fin"]
        aplicados.append("inscripcion.fin")

    detalle = universidad.setdefault("detalle", {})
    for campo in ("costo_prospecto", "costo_inscripcion_estatal", "costo_inscripcion_privado"):
        valor = hallazgo.get(campo)
        if costo_es_razonable(valor):
            detalle[campo] = valor
            aplicados.append(campo)

    if hallazgo.get("resumen_parafraseado") and hallazgo.get("confianza") in ("alta", "media"):
        detalle["resumen_oficial"] = hallazgo["resumen_parafraseado"]
        detalle["fuente_resumen"] = universidad.get("url_oficial")
        detalle["resumen_actualizado"] = datetime.now().strftime("%Y-%m-%d")
        aplicados.append("detalle.resumen_oficial")

    if not detalle:
        universidad.pop("detalle", None)

    return aplicados


def main():
    verificar_configuracion()

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    hoy = datetime.now().strftime("%Y-%m-%d")
    reporte = {"generado": datetime.now().isoformat(), "universidades": {}}
    hubo_cambios = False

    for u in data["universidades"]:
        siglas = u["siglas"]
        url_oficial = u.get("url_oficial")
        if not url_oficial:
            print(f"— {siglas}: sin url_oficial, se omite")
            continue

        print(f"Scrapeando {siglas} ({url_oficial})...")
        texto = recolectar_texto_sitio(url_oficial)
        if not texto.strip():
            print(f"  ⚠️  No se pudo obtener texto de la web oficial")
            reporte["universidades"][siglas] = {"error": "no se pudo descargar la web oficial"}
            time.sleep(PAUSA_ENTRE_SITIOS)
            continue

        prompt = PROMPT_BASE.format(universidad=u["nombre"], hoy=hoy, texto=texto)
        respuesta_texto = llamar_ia(prompt)
        time.sleep(PAUSA_ENTRE_LLAMADAS_IA)

        if respuesta_texto is None:
            print(f"  ⚠️  Sin respuesta de la IA")
            reporte["universidades"][siglas] = {"error": "sin respuesta de la IA"}
            continue

        hallazgo = limpiar_json_de_texto(respuesta_texto)
        if hallazgo is None:
            print(f"  ⚠️  No pude parsear la respuesta como JSON: {respuesta_texto[:200]}")
            reporte["universidades"][siglas] = {"error": "respuesta no parseable"}
            continue

        hallazgo["fuente_url"] = url_oficial
        reporte["universidades"][siglas] = hallazgo

        aplicados = aplicar_hallazgo(u, hallazgo)
        if aplicados:
            hubo_cambios = True
            print(f"  ✏️  Aplicado ({hallazgo.get('confianza')}): {', '.join(aplicados)}")
        else:
            print(f"  ⏭️  Nada lo bastante confiable para aplicar (confianza: {hallazgo.get('confianza')})")

        time.sleep(PAUSA_ENTRE_SITIOS)

    SALIDA_PATH.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Reporte completo guardado en {SALIDA_PATH.relative_to(RAIZ)}")

    if hubo_cambios:
        JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("✅ universidades.json actualizado con los datos oficiales validados.")
    else:
        print("— Ningún dato pasó las validaciones para aplicarse automáticamente esta corrida.")


if __name__ == "__main__":
    main()
