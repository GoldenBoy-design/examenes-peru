"""
Scraper del "banco de universidades": visita la web OFICIAL de cada
universidad (campo url_oficial en data/universidades.json), sigue enlaces
internos relacionados a admisión (cronograma, costos, inscripción), extrae
el texto y le pide a la IA (Groq) que lo estructure y PARAFRASEE.

A diferencia de detectar_rss.py + extraer_ia.py (que solo miran titulares
de noticias), este script lee la fuente primaria: la propia universidad.

CÓMO FUNCIONA (2 fases):

  Fase 1 — rápida, en paralelo, solo HTTP (requests + BeautifulSoup).
  Sirve para sitios "clásicos" renderizados en el servidor (WordPress,
  PHP, HTML estático). Muchísimas webs de admisión en Perú SÍ son así.

  Fase 2 — lenta, en serie, con navegador headless (Playwright).
  Varias webs oficiales (p.ej. Angular/Vue/React, rutas tipo
  "sitio.edu.pe/#/admision/cronograma") no traen contenido real en el
  HTML crudo: todo lo pinta JavaScript en el navegador. Para esas,
  requests.get() solo devuelve el "cascarón" de la app (menú, script
  tags, casi nada de texto) y por eso la IA respondía "confianza: baja"
  o "sin datos" — parecía que el scraper no servía, pero en realidad
  nunca llegó a ver el contenido. Detectamos esto automáticamente
  (texto útil por debajo de un umbral) y reintentamos SOLO esas
  universidades con un navegador real.

Escribe SIEMPRE un reporte en data/propuestas_scraper.json con todo lo
encontrado, incluyendo el motivo exacto de cada fallo. Además, aplica
automáticamente a universidades.json los campos que pasan validaciones
estrictas (fecha ISO real, costo numérico razonable, etc.) — igual que ya
hace extraer_ia.py con las fechas de noticias. Lo que no pasa la
validación queda solo en el reporte para revisión.

Requiere:
    pip install requests beautifulsoup4 playwright
    playwright install --with-deps chromium
    Variable de entorno GROQ_API_KEY

Si Playwright no está instalado, el script sigue funcionando (solo se
salta la Fase 2 y avisa qué universidades se quedaron sin revisar).

Uso:
    python scripts/scrapear_oficial.py
"""

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.exceptions import SSLError

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_DISPONIBLE = True
except ImportError:
    PLAYWRIGHT_DISPONIBLE = False

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
SALIDA_PATH = RAIZ / "data" / "propuestas_scraper.json"

MODELO = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
API_KEY = os.environ.get("GROQ_API_KEY")
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.6",
}

# Cuántas universidades se procesan EN PARALELO en la Fase 1 (solo HTTP).
# Cada una hace sus propias llamadas HTTP + 1 llamada a Groq, así que esto
# es paralelismo de I/O (threads), no de CPU. 6 es prudente para no
# saturar el rate-limit gratuito de Groq (que es por cuenta, no por hilo).
MAX_UNIVERSIDADES_EN_PARALELO = 6

TIMEOUT = 12
TIMEOUT_JS_MS = 15000        # timeout de navegación por página en Fase 2 (ms)
ESPERA_RENDER_MS = 2000      # espera extra tras cargar, para que Angular/Vue/React pinten
PAUSA_ENTRE_SUBPAGINAS = 0.3
PAUSA_ENTRE_LLAMADAS_IA = 0.5
MAX_REINTENTOS_IA = 3
MAX_SUBPAGINAS = 3
MAX_CARACTERES_TEXTO = 7000  # tope de texto que le mandamos a la IA por universidad

# Por debajo de este umbral de texto "limpio", asumimos que la Fase 1 no
# alcanzó el contenido real (sitio dinámico, bloqueo, página casi vacía)
# y la universidad pasa a la Fase 2 (navegador headless).
UMBRAL_TEXTO_SUFICIENTE = 400

# Palabras clave para decidir qué enlaces de la web oficial vale la pena seguir
PALABRAS_CLAVE_ENLACES = [
    "admision", "admisión", "cronograma", "costo", "costos", "pago",
    "inscrip", "vacante", "proceso", "calendario", "postulante", "postula",
    "requisito", "prospecto", "tasa",
]

# Palabras clave para priorizar QUÉ PARTE del texto mandamos a la IA cuando
# el sitio trae mucho más contenido del que cabe en MAX_CARACTERES_TEXTO.
# Antes se cortaba a ciegas con texto[:7000], lo que a veces descartaba la
# tabla de fechas si venía después del menú/noticias/pie de página.
PALABRAS_CLAVE_CONTENIDO = [
    "cronograma", "fecha", "examen", "inscrip", "vacante", "costo", "s/.",
    "soles", "admisión", "admision", "prospecto", "modalidad", "postulante",
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
    if not PLAYWRIGHT_DISPONIBLE:
        print("⚠️  Playwright no está instalado: la Fase 2 (sitios dinámicos tipo")
        print("   Angular/Vue/React) se saltará. Para activarla:")
        print("     pip install playwright && playwright install --with-deps chromium")


def descargar(url: str, verificar_ssl: bool = True):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=verificar_ssl)
        if resp.status_code != 200:
            print(f"    ⚠️  {url} respondió {resp.status_code}")
            return None
        return resp.text
    except SSLError:
        if verificar_ssl:
            # Varios .edu.pe tienen certificados mal configurados (cadena
            # incompleta, vencidos). Reintentamos una vez sin verificar,
            # que sigue siendo mejor que descartar el sitio entero.
            return descargar(url, verificar_ssl=False)
        print(f"    ⚠️  Error SSL persistente en {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"    ⚠️  Error de red en {url}: {e}")
        return None


def parsear_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def extraer_texto(sopa: BeautifulSoup) -> str:
    """Texto limpio para mandar a la IA: aquí SÍ conviene quitar nav/footer/
    script, porque son ruido (menús repetidos, boilerplate) que le resta
    espacio útil al presupuesto de caracteres."""
    sopa_limpia = BeautifulSoup(str(sopa), "html.parser")
    for tag in sopa_limpia(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    texto = sopa_limpia.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", texto)


def extraer_enlaces(sopa: BeautifulSoup, url_base: str):
    """Devuelve dos listas separadas:
    - enlaces_normales: rutas distintas (sirven para requests.get en Fase 1)
    - rutas_hash: enlaces tipo #/admision/cronograma (rutas de un SPA).
      Pedirle esa URL a requests.get() devuelve exactamente el mismo HTML
      que la home (el navegador es quien resuelve el fragmento), así que
      en Fase 1 NO tiene sentido descargarlas — pero si la universidad
      termina en Fase 2, Playwright sí puede navegar a ellas de verdad.
    """
    dominio_base = urlparse(url_base).netloc
    enlaces_normales, rutas_hash = [], []
    vistos = set()

    for a in sopa.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href == "#":
            continue
        texto_enlace = (a.get_text() or "").lower()
        combinado = f"{texto_enlace} {href.lower()}"
        if not any(palabra in combinado for palabra in PALABRAS_CLAVE_ENLACES):
            continue

        if href.startswith("#"):
            if href not in rutas_hash:
                rutas_hash.append(href)
            continue

        href_absoluto = urljoin(url_base, href)
        parsed = urlparse(href_absoluto)
        if parsed.netloc != dominio_base or parsed.scheme not in ("http", "https"):
            continue
        # Dos URLs que solo difieren en el fragmento son la misma página
        # para requests.get() — las tratamos como una sola.
        clave = href_absoluto.split("#")[0]
        if clave in vistos:
            continue
        vistos.add(clave)
        enlaces_normales.append(href_absoluto)

    return enlaces_normales, rutas_hash


def priorizar_texto(texto: str, presupuesto: int) -> str:
    """En vez de cortar a ciegas en el carácter N (lo que a veces descarta
    la tabla de fechas si viene después de secciones irrelevantes), junta
    primero los fragmentos alrededor de palabras clave de contenido y
    rellena el resto del presupuesto con lo que sobre del texto."""
    if len(texto) <= presupuesto:
        return texto

    texto_lower = texto.lower()
    ventanas = []
    for palabra in PALABRAS_CLAVE_CONTENIDO:
        for m in re.finditer(re.escape(palabra), texto_lower):
            inicio = max(0, m.start() - 250)
            fin = min(len(texto), m.end() + 350)
            ventanas.append((inicio, fin))

    if not ventanas:
        return texto[:presupuesto]

    ventanas.sort()
    fusionadas = []
    for inicio, fin in ventanas:
        if fusionadas and inicio <= fusionadas[-1][1]:
            fusionadas[-1] = (fusionadas[-1][0], max(fusionadas[-1][1], fin))
        else:
            fusionadas.append((inicio, fin))

    partes, usado, cubierto = [], 0, set()
    for inicio, fin in fusionadas:
        if usado >= presupuesto:
            break
        fragmento = texto[inicio:fin]
        partes.append(fragmento)
        usado += len(fragmento)
        cubierto.add((inicio, fin))

    resultado = " [...] ".join(partes)
    if len(resultado) < presupuesto:
        resultado += " [...] " + texto[:presupuesto - len(resultado)]
    return resultado[:presupuesto]


def recolectar_texto_sitio(url_oficial: str):
    """Fase 1: descarga la home + hasta MAX_SUBPAGINAS enlaces relevantes
    (solo requests, sin JS) y arma el texto combinado.

    Devuelve (texto, rutas_hash_detectadas, motivo_si_fallo).
    """
    html_home = descargar(url_oficial)
    if html_home is None:
        return "", [], "no se pudo descargar la home"

    sopa_home = parsear_html(html_home)
    texto_home = extraer_texto(sopa_home)
    enlaces, rutas_hash = extraer_enlaces(sopa_home, url_oficial)

    partes = [f"---PÁGINA--- ({url_oficial})\n{texto_home}"]

    for enlace in enlaces[:MAX_SUBPAGINAS]:
        time.sleep(PAUSA_ENTRE_SUBPAGINAS)
        html_sub = descargar(enlace)
        if html_sub is None:
            continue
        texto_sub = extraer_texto(parsear_html(html_sub))
        partes.append(f"---PÁGINA--- ({enlace})\n{texto_sub}")

    texto_total = "\n\n".join(partes)
    return texto_total, rutas_hash, None


def recolectar_texto_sitio_js(navegador, url_oficial: str, rutas_hash: list):
    """Fase 2: igual que la anterior pero con un navegador real, para
    sitios cuyo contenido lo pinta JavaScript (Angular/Vue/React, rutas
    tipo #/admision/cronograma que requests.get() nunca puede ver)."""
    contexto = navegador.new_context(user_agent=HEADERS["User-Agent"], locale="es-PE")
    pagina = contexto.new_page()
    partes = []

    # Rutas a visitar con el navegador: la home, y cada ruta-hash relevante
    # detectada en el HTML crudo (p.ej. "#/admision/cronograma"), navegando
    # a url_oficial + esa ruta para que el router del SPA la resuelva.
    rutas_a_visitar = [url_oficial] + [urljoin(url_oficial, r) for r in rutas_hash[:MAX_SUBPAGINAS]]

    for ruta in rutas_a_visitar:
        try:
            pagina.goto(ruta, timeout=TIMEOUT_JS_MS, wait_until="domcontentloaded")
            pagina.wait_for_timeout(ESPERA_RENDER_MS)
            html_render = pagina.content()
            texto = extraer_texto(parsear_html(html_render))
            partes.append(f"---PÁGINA--- ({ruta})\n{texto}")
        except Exception as e:
            print(f"    ⚠️  Playwright no pudo cargar {ruta}: {e}")

    contexto.close()
    return "\n\n".join(partes)


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
            espera = 5 * intento
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


def preguntar_a_ia(universidad: dict, texto: str, hoy: str):
    texto_final = priorizar_texto(texto, MAX_CARACTERES_TEXTO)
    prompt = PROMPT_BASE.format(universidad=universidad["nombre"], hoy=hoy, texto=texto_final)
    respuesta_texto = llamar_ia(prompt)
    time.sleep(PAUSA_ENTRE_LLAMADAS_IA)

    if respuesta_texto is None:
        return None, "sin respuesta de la IA"

    hallazgo = limpiar_json_de_texto(respuesta_texto)
    if hallazgo is None:
        return None, f"respuesta no parseable: {respuesta_texto[:200]}"

    hallazgo["fuente_url"] = universidad.get("url_oficial")
    return hallazgo, None


def procesar_universidad_fase1(u: dict):
    """Trabajo de UN hilo en la Fase 1: solo descarga + limpieza de texto.
    No llama a la IA todavía y no toca el dict `u`. Devuelve además si el
    texto obtenido parece insuficiente (candidato a Fase 2)."""
    siglas = u["siglas"]
    url_oficial = u.get("url_oficial")
    if not url_oficial:
        return siglas, "", [], "sin url_oficial"

    texto, rutas_hash, motivo = recolectar_texto_sitio(url_oficial)
    return siglas, texto, rutas_hash, motivo


def texto_es_suficiente(texto: str) -> bool:
    # Le restamos el "ruido" típico de menús/breadcrumbs repetidos y nos
    # quedamos con una medida simple de longitud del texto útil.
    return len(texto.strip()) >= UMBRAL_TEXTO_SUFICIENTE


def main():
    verificar_configuracion()

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    hoy = datetime.now().strftime("%Y-%m-%d")
    reporte = {"generado": datetime.now().isoformat(), "universidades": {}}
    hubo_cambios = False

    universidades_por_siglas = {u["siglas"]: u for u in data["universidades"]}
    print_lock = Lock()

    textos = {}          # siglas -> texto recolectado
    rutas_hash_por_u = {}  # siglas -> rutas #/... detectadas
    candidatas_fase2 = []  # siglas que necesitan navegador

    print("── Fase 1: descarga rápida (requests) ──")
    with ThreadPoolExecutor(max_workers=MAX_UNIVERSIDADES_EN_PARALELO) as pool:
        futuros = {
            pool.submit(procesar_universidad_fase1, u): u["siglas"]
            for u in data["universidades"]
        }
        for futuro in as_completed(futuros):
            siglas, texto, rutas_hash, motivo = futuro.result()
            with print_lock:
                if motivo:
                    print(f"— {siglas}: {motivo}")
                    reporte["universidades"][siglas] = {"error": motivo}
                    continue
                textos[siglas] = texto
                rutas_hash_por_u[siglas] = rutas_hash
                if not texto_es_suficiente(texto):
                    candidatas_fase2.append(siglas)
                    print(f"— {siglas}: texto insuficiente ({len(texto.strip())} car.) → posible sitio dinámico")
                else:
                    print(f"✓ {siglas}: {len(texto.strip())} caracteres de texto útil")

    if candidatas_fase2:
        if PLAYWRIGHT_DISPONIBLE:
            print(f"\n── Fase 2: navegador headless para {len(candidatas_fase2)} sitio(s) dinámico(s) ──")
            with sync_playwright() as pw:
                navegador = pw.chromium.launch(headless=True)
                for siglas in candidatas_fase2:
                    u = universidades_por_siglas[siglas]
                    url_oficial = u.get("url_oficial")
                    print(f"  … renderizando {siglas} ({url_oficial})")
                    try:
                        texto_js = recolectar_texto_sitio_js(navegador, url_oficial, rutas_hash_por_u.get(siglas, []))
                    except Exception as e:
                        print(f"    ⚠️  Fallo de Playwright en {siglas}: {e}")
                        texto_js = ""
                    if texto_es_suficiente(texto_js):
                        print(f"  ✓ {siglas}: {len(texto_js.strip())} caracteres tras renderizar")
                        textos[siglas] = texto_js
                    else:
                        # Nos quedamos con lo que teníamos de Fase 1 si algo
                        # obtuvimos; igual lo mandamos a la IA por si acaso,
                        # pero queda registrado el motivo por si sale "baja".
                        print(f"  — {siglas}: seguía insuficiente tras renderizar ({len(texto_js.strip())} car.)")
                        if len(texto_js.strip()) > len(textos.get(siglas, "").strip()):
                            textos[siglas] = texto_js
                navegador.close()
        else:
            print(f"\n⚠️  {len(candidatas_fase2)} sitio(s) necesitaban navegador headless "
                  f"(Playwright) y se quedaron con texto insuficiente: {', '.join(candidatas_fase2)}")

    print("\n── Consultando a la IA ──")
    for siglas, texto in textos.items():
        u = universidades_por_siglas[siglas]
        if not texto.strip():
            reporte["universidades"][siglas] = {"error": "sin texto utilizable tras ambas fases"}
            print(f"— {siglas}: sin texto utilizable tras ambas fases")
            continue

        hallazgo, error = preguntar_a_ia(u, texto, hoy)
        if error:
            reporte["universidades"][siglas] = {"error": error}
            print(f"— {siglas}: {error}")
            continue

        reporte["universidades"][siglas] = hallazgo
        aplicados = aplicar_hallazgo(u, hallazgo)
        if aplicados:
            hubo_cambios = True
            print(f"✏️  {siglas} ({hallazgo.get('confianza')}): {', '.join(aplicados)}")
        else:
            print(f"⏭️  {siglas}: nada lo bastante confiable (confianza: {hallazgo.get('confianza')})")

    SALIDA_PATH.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Reporte completo guardado en {SALIDA_PATH.relative_to(RAIZ)}")

    if hubo_cambios:
        JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("✅ universidades.json actualizado con los datos oficiales validados.")
    else:
        print("— Ningún dato pasó las validaciones para aplicarse automáticamente esta corrida.")


if __name__ == "__main__":
    main()