"""
Importa a data/universidades.json las universidades del archivo
data/faltantes_por_completar.csv que YA tengan la columna url_oficial
rellenada (las que sigan vacías se ignoran hasta que las completes).

No pisa universidades existentes (usa el nombre normalizado para
detectar duplicados). Los campos que el CSV no trae (fechas_examen,
inscripcion, modalidad, logo, etc.) quedan vacíos/por defecto — el
scraper (scripts/scrapear_oficial.py) los completa en la siguiente
corrida automática al detectar la url_oficial nueva.

Uso:
    python scripts/importar_faltantes.py
"""

import csv
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JSON_PATH = RAIZ / "data" / "universidades.json"
CSV_PATH = RAIZ / "data" / "faltantes_por_completar.csv"


def norm(s: str) -> str:
    s = s.lower()
    for a, b in zip("áéíóúñ", "aeioun"):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    existentes = {norm(u["nombre"]) for u in data["universidades"]}
    ids_existentes = {u["id"] for u in data["universidades"]}

    agregadas = 0
    saltadas_sin_url = 0
    saltadas_duplicadas = 0

    with CSV_PATH.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            nombre = fila["nombre"].strip()
            url = fila["url_oficial"].strip()

            if norm(nombre) in existentes:
                saltadas_duplicadas += 1
                continue
            if not url:
                saltadas_sin_url += 1
                continue

            id_ = fila["id_sugerido"].strip()
            if id_ in ids_existentes:
                id_ = f"{id_}2"
            ids_existentes.add(id_)

            data["universidades"].append({
                "id": id_,
                "nombre": nombre,
                "siglas": fila["siglas_sugeridas"].strip(),
                "provincia": fila["provincia"].strip(),
                "logo": f"/logos/{id_}.png",
                "modalidad": "Por confirmar",
                "fechas_examen": [],
                "inscripcion": {"inicio": None, "fin": None},
                "url_oficial": url,
                "pagina_propia": f"/uni/{id_}",
                "estado_proceso": "por confirmar",
                "tipo": fila["tipo"].strip(),
            })
            agregadas += 1

    if agregadas:
        JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Agregadas: {agregadas}")
    print(f"⏭️  Sin url_oficial todavía (se ignoraron): {saltadas_sin_url}")
    print(f"⏭️  Ya existían (se ignoraron): {saltadas_duplicadas}")
    if agregadas:
        print("\nCorre scripts/scrapear_oficial.py para llenarles fechas/costos,")
        print("y agrega su logo en /logos/<id>.png (si no, sale sin logo).")


if __name__ == "__main__":
    main()
