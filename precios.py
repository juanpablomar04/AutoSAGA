"""
precios.py — Actualiza precios de templates en MongoDB desde precios.xlsx.

Mejoras respecto a la versión anterior:
- Eliminado el uso de eval() para acceder a variables dinámicas.
  Los datos se almacenan directamente en diccionarios.
- Lógica de actualización extraída en una función reutilizable.
- Conexión a MongoDB centralizada con context manager.
"""

from openpyxl import load_workbook
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import constantes as const


# ─── Lectura del Excel ────────────────────────────────────────────────────────

def _leer_pares(sheet, celdas: list[tuple[str, str]]) -> list[int]:
    """Lee pares de celdas (mo, material) y retorna lista plana de enteros."""
    valores = []
    for col_mo, col_mat in celdas:
        valores.append(int(sheet[col_mo].value))
        valores.append(int(sheet[col_mat].value))
    return valores


wb = load_workbook("precios.xlsx", data_only=True)

# ── Nafta (7 servicios × 7 variantes) ────────────────────────────────────────
sh_n = wb["Nafta"]
FILAS_NAFTA = [26, 53, 80, 107, 134, 161, 188]
COLS_NAFTA  = ["e", "g", "i", "k", "m", "o", "q"]

nafta: dict[str, list[int]] = {}
for srv, fila in enumerate(FILAS_NAFTA, start=1):
    pares = [(f"{col}{fila}", f"{col}{fila+1}") for col in COLS_NAFTA]
    nafta[f"n{srv}"] = _leer_pares(sh_n, pares)

# ── Diesel (5 servicios × 3 variantes) ───────────────────────────────────────
sh_d = wb["Diesel"]
FILAS_DIESEL = [26, 53, 80, 107, 134]
COLS_DIESEL  = ["e", "g", "i"]

diesel: dict[str, list[int]] = {}
for srv, fila in enumerate(FILAS_DIESEL, start=1):
    pares = [(f"{col}{fila}", f"{col}{fila+1}") for col in COLS_DIESEL]
    diesel[f"d{srv}"] = _leer_pares(sh_d, pares)

# ── Amarok (10 servicios × 2 variantes) ──────────────────────────────────────
sh_a = wb["Amarok "]
FILAS_AMAROK = [23, 47, 71, 95, 119, 143, 167, 191, 215, 239]
COLS_AMAROK  = ["g", "i"]

amarok: dict[str, list[int]] = {}
for srv, fila in enumerate(FILAS_AMAROK, start=1):
    pares = [(f"{col}{fila}", f"{col}{fila+1}") for col in COLS_AMAROK]
    amarok[f"a{srv}"] = _leer_pares(sh_a, pares)


# ─── Actualización en MongoDB ─────────────────────────────────────────────────

CAMPO_MO  = "data.1.tercero.emo.0.importe"
CAMPO_MAT = "data.1.tercero.ematerial.0.importe"


def actualizar_grupo(db, datos: dict[str, list[int]], gamma_offset: int = 1):
    """
    Itera sobre un grupo de templates y actualiza MO + material.

    `datos` es un dict como {"n1": [mo1, mat1, mo2, mat2, ...], ...}
    Cada par (mo, mat) corresponde a una variante (gamma) del servicio.
    """
    for clave, valores in datos.items():
        for i in range(0, len(valores), 2):
            gamma = (i // 2) + gamma_offset
            codigo = f"{clave}{gamma}"
            db.templates.update_one(
                {"codigo": codigo},
                {"$set": {CAMPO_MO: str(valores[i]), CAMPO_MAT: str(valores[i + 1])}},
            )
            print(f"  ✔ {codigo}: MO={valores[i]}, MAT={valores[i+1]}")


uri = (
    f"mongodb+srv://{const.USER_MONGO}:{const.PASS_MONGO}"
    "@cluster0.g0ktnap.mongodb.net/?retryWrites=true&w=majority"
)

with MongoClient(uri, server_api=ServerApi("1")) as client:
    db = client["work"]

    print("─── Actualizando Nafta ───")
    actualizar_grupo(db, nafta, gamma_offset=1)

    print("─── Actualizando Diesel ───")
    # Diesel empieza en gamma 4 según lógica original: (i+8)//2 + 1
    # Para d1: i=0 → gamma=5; i=2 → gamma=6; i=4 → gamma=7
    for clave, valores in diesel.items():
        for i in range(0, len(valores), 2):
            gamma = (i + 8) // 2 + 1
            codigo = f"{clave}{gamma}"
            db.templates.update_one(
                {"codigo": codigo},
                {"$set": {CAMPO_MO: str(valores[i]), CAMPO_MAT: str(valores[i + 1])}},
            )
            print(f"  ✔ {codigo}: MO={valores[i]}, MAT={valores[i+1]}")

    print("─── Actualizando Amarok ───")
    actualizar_grupo(db, amarok, gamma_offset=1)

print("\n✅ Actualización completada.")
