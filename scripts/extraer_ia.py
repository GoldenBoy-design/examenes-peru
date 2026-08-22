"""
Extractor de datos estructurados con Groq (modelos Llama, gratis).

Lee data/novedades.json (generado por detectar_rss.py), le pide al modelo
que extraiga fechas concretas de cada noticia, y SI la fecha extraída es
válida y confiable, actualiza data/universidades.json directamente.

El único paso humano que queda es aprobar el Pull Request que abre
GitHub Actions (revisar el diff de universidades.json y darle merge) —
no hace falta editar el JSON a mano.

Por qué le pasamos la fecha de publicación de cada noticia al modelo:
titulares como "examen este domingo" son relativos — sin saber cuándo se
publicó la noticia, es imposible calcular a qué fecha calendario corresponde.
Se lo damos explícitamente para que el modelo calcule la fecha absoluta.

Requiere:
    pip install requests
    Variable de entorno GROQ_API_KEY (gratis en console.groq.com/keys)

Variable opcional:
    GROQ_MODEL (default: llama-3.3-70b-versatile)

Uso:
    python scripts/extraer_ia.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
NOVEDADES_PATH = RAIZ / "data" / "novedades.json"
SALIDA_PATH = RAIZ / "data" / "propuestas_ia.json"

MODELO = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
API_KEY = os.environ.get("GROQ_API_KEY")

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

PAUSA_ENTRE_LLAMADAS = 3
MAX_REINTENTOS = 4

FECHA_ISO_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")

PROMPT_BASE = """Eres un asistente que extrae datos de admisión universitaria peruana desde titulares de noticias.

Noticia publicada el: {fecha_publicacion} (formato YYYY-MM-DD)
Titular: "{titulo}"
Universidad: "{universidad}"

Si el titular menciona una fecha de examen (incluso relativa, como "este domingo" o "el próximo lunes"), calcula la fecha calendario EXACTA usando la fecha de publicación de arriba como referencia.

Responde SOLO con un JSON (sin markdown, sin texto adicional):
{{"hay_dato_nuevo": true, "fecha_examen": "YYYY-MM-DD", "inscripcion_inicio": "YYYY-MM-DD o null", "inscripcion_fin": "YYYY-MM-DD o null", "resumen": "una frase breve de qué cambió"}}

Reglas estrictas:
- "fecha_examen" DEBE ser una fecha calendario exacta en formato YYYY-MM-DD, o null. NUNCA texto como "domingo" o "próxima semana".
- Si no puedes calcular una fecha exacta con certeza, responde exactamente: {{"hay_dato_nuevo": false}}
- Si el titular no menciona ningún dato concreto de cronograma, responde exactamente: {{"hay_dato_nuevo": false}}
"""


def verificar_configuracion():
    if not API_KEY:
        print("❌ No encontré la variable de entorno GROQ_API_KEY.")
        print("   Consigue una gratis en https://console.groq.com/keys")
        sys.exit(1)


def llamar_ia(prompt: str):
    payload = {
        "model": MODELO,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=30)
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Error de red al llamar a Groq: {e}")
            return None

        if resp.status_code == 429:
            espera = 15 * intento
            print(f"  ⏳ Rate limit (429). Esperando {espera}s ({intento}/{MAX_REINTENTOS})...")
            time.sleep(espera)
            continue

        if resp.status_code != 200:
            print(f"  ⚠️  Groq respondió {resp.status_code} — modelo usado: '{MODELO}'")
            print(f"      Cuerpo de la respuesta: {resp.text[:500]}")
            return None

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            print(f"  ⚠️  Respuesta 200 pero sin el campo esperado: {json.dumps(data)[:500]}")
            return None

    print(f"  ❌ Se agotaron los {MAX_REINTENTOS} reintentos por rate limit.")
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
    """Valida que sea un string YYYY-MM-DD real y parseable, no texto suelto."""
    if not fecha_str or not isinstance(fecha_str, str):
        return False
    if not FECHA_ISO_REGEX.match(fecha_str):
        return False
    try:
        datetime.strptime(fecha_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def aplicar_cambio(data: dict, siglas: str, hallazgo: dict) -> bool:
    """Actualiza la universidad en el JSON si la fecha extraída es válida
    y distinta a lo que ya teníamos. Devuelve True si aplicó un cambio."""
    fecha_nueva = hallazgo.get("fecha_examen")
    if not fecha_es_valida(fecha_nueva):
        print(f"  ⏭️  Fecha no válida/confiable ('{fecha_nueva}') — no se aplica, queda solo en el reporte")
        return False

    for u in data["universidades"]:
        if u["siglas"] == siglas:
            if fecha_nueva in u.get("fechas_examen", []):
                return False  # ya lo teníamos, nada que hacer
            u.setdefault("fechas_examen", []).append(fecha_nueva)
            u["fechas_examen"].sort()
            print(f"  ✏️  {siglas}: agregada fecha {fecha_nueva} a universidades.json")
            return True
    return False


def main():
    verificar_configuracion()

    if not NOVEDADES_PATH.exists():
        print(f"❌ No existe {NOVEDADES_PATH.relative_to(RAIZ)}. Corre primero detectar_rss.py")
        sys.exit(1)

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    novedades = json.loads(NOVEDADES_PATH.read_text(encoding="utf-8"))
    propuestas = {"generado": novedades.get("generado"), "universidades": {}}

    universidades = novedades.get("universidades", {})
    if not universidades:
        print("No hay novedades pendientes de procesar.")
        return

    hubo_cambios = False

    for siglas, info in universidades.items():
        print(f"Procesando {siglas}...")
        hallazgos = []
        for noticia in info["noticias_encontradas"]:
            fecha_pub = noticia["fecha_publicacion"][:10]  # YYYY-MM-DD desde el ISO completo
            prompt = PROMPT_BASE.format(
                fecha_publicacion=fecha_pub, titulo=noticia["titulo"], universidad=siglas
            )
            texto = llamar_ia(prompt)
            time.sleep(PAUSA_ENTRE_LLAMADAS)
            if texto is None:
                continue
            resultado = limpiar_json_de_texto(texto)
            if resultado is None:
                print(f"  ⚠️  No pude parsear la respuesta como JSON: {texto[:200]}")
                continue
            if resultado.get("hay_dato_nuevo"):
                resultado["fuente_titulo"] = noticia["titulo"]
                resultado["fuente_link"] = noticia["link"]
                hallazgos.append(resultado)

                if aplicar_cambio(data, siglas, resultado):
                    hubo_cambios = True

        if hallazgos:
            propuestas["universidades"][siglas] = hallazgos

    SALIDA_PATH.write_text(json.dumps(propuestas, ensure_ascii=False, indent=2), encoding="utf-8")

    if hubo_cambios:
        JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ universidades.json actualizado con las fechas confirmadas.")
        print("   Este cambio va a aparecer en el diff del Pull Request para tu aprobación.")
    else:
        print(f"\n— Ninguna fecha extraída fue lo bastante confiable para aplicarse automáticamente.")
        print(f"   Revisa {SALIDA_PATH.relative_to(RAIZ)} por si hay algo que valga la pena mirar a mano.")


if __name__ == "__main__":
    main()