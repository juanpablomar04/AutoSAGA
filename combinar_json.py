"""
combinar_json.py — Combina múltiples archivos JSON individuales en un único
archivo con formato de array para la carga múltiple de AutoSAGA.

Uso:
    python combinar_json.py archivo1.json archivo2.json archivo3.json
    python combinar_json.py                          # abre selector de archivos
    python combinar_json.py --carpeta C:/reclamos    # procesa todos los .json de una carpeta
"""

import json
import sys
import os
from pathlib import Path
from tkinter import filedialog, Tk


# ─── Campos esperados en cada JSON ───────────────────────────────────────────
CAMPOS_REQUERIDOS = {"orden", "chasis", "apertura", "cierre", "kilometraje", "codigo"}
CAMPOS_SALIDA = ["orden", "chasis", "apertura", "cierre", "kilometraje", "codigo"]


def leer_json(path: Path) -> dict | None:
    """Lee un archivo JSON y devuelve el objeto. Retorna None si hay error."""
    try:
        with open(path, encoding="utf-8") as f:
            datos = json.load(f)

        # Si viene como lista de un solo elemento, desenvuelve
        if isinstance(datos, list):
            if len(datos) == 1:
                datos = datos[0]
            else:
                print(f"  ⚠  {path.name}: contiene más de un objeto, se tomará el primero.")
                datos = datos[0]

        return datos

    except json.JSONDecodeError as e:
        print(f"  ✘  {path.name}: JSON inválido — {e}")
        return None
    except OSError as e:
        print(f"  ✘  {path.name}: no se pudo leer — {e}")
        return None


def validar(datos: dict, nombre: str) -> bool:
    """Verifica que el objeto tenga todos los campos requeridos."""
    faltantes = CAMPOS_REQUERIDOS - datos.keys()
    if faltantes:
        print(f"  ⚠  {nombre}: faltan campos {faltantes} — se incluye igual.")
    return True


def transformar_orden(orden: str) -> str:
    """
    Aplica el prefijo/infijo correspondiente según el primer dígito de la orden.
      2... -> 0 adelante        ej: 214103  -> 0214103
      3... -> 0 después del 3   ej: 312456  -> 3012456
      4... -> 0 después del 4   ej: 498765  -> 4098765
      5... -> 1 antes del 5     ej: 567890  -> 1567890
      6... -> 2 antes del 6     ej: 623001  -> 2623001
    """
    if not orden:
        return orden
    primer = orden[0]
    resto  = orden[1:]
    if primer == "2":
        return "0" + orden
    elif primer == "3":
        return "3" + "0" + resto
    elif primer == "4":
        return "4" + "0" + resto
    elif primer == "5":
        return "1" + orden
    elif primer == "6":
        return "2" + orden
    return orden


def normalizar(datos: dict) -> dict:
    """Devuelve solo los campos relevantes, en orden estándar."""
    resultado = {}
    for campo in CAMPOS_SALIDA:
        resultado[campo] = str(datos.get(campo, ""))
    # Transformar número de orden según regla de prefijos
    resultado["orden"] = transformar_orden(resultado["orden"])
    # Preservar campos extra que pudiera tener el JSON original
    for clave, valor in datos.items():
        if clave not in resultado:
            resultado[clave] = valor
    return resultado


def seleccionar_archivos_gui() -> list[Path]:
    """Abre un selector de archivos múltiple."""
    root = Tk()
    root.withdraw()
    rutas = filedialog.askopenfilenames(
        title="Seleccionar archivos JSON",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
    )
    root.destroy()
    return [Path(r) for r in rutas]


def obtener_archivos_carpeta(carpeta: str) -> list[Path]:
    """Devuelve todos los .json de una carpeta."""
    p = Path(carpeta)
    if not p.is_dir():
        print(f"✘  '{carpeta}' no es una carpeta válida.")
        sys.exit(1)
    archivos = sorted(p.glob("*.json"))
    if not archivos:
        print(f"✘  No se encontraron archivos .json en '{carpeta}'.")
        sys.exit(1)
    return archivos


def combinar(archivos: list[Path]) -> list[dict]:
    """Lee y combina los archivos en una lista."""
    resultado = []
    for archivo in archivos:
        print(f"  ✔  Leyendo {archivo.name}...")
        datos = leer_json(archivo)
        if datos is None:
            continue
        validar(datos, archivo.name)
        resultado.append(normalizar(datos))
    return resultado


def guardar(lista: list[dict], ruta_salida: Path):
    """Guarda la lista combinada como JSON."""
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)
    print(f"\n✅  {len(lista)} orden(es) combinadas → {ruta_salida}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  AutoSAGA — Combinador de JSON")
    print("=" * 50)

    archivos: list[Path] = []

    # Modo --carpeta
    if "--carpeta" in sys.argv:
        idx = sys.argv.index("--carpeta")
        try:
            carpeta = sys.argv[idx + 1]
        except IndexError:
            print("✘  Especificá la carpeta después de --carpeta.")
            sys.exit(1)
        archivos = obtener_archivos_carpeta(carpeta)

    # Modo argumentos directos
    elif len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            p = Path(arg)
            if not p.exists():
                print(f"  ⚠  '{arg}' no existe, se omite.")
            elif p.suffix.lower() != ".json":
                print(f"  ⚠  '{arg}' no es un .json, se omite.")
            else:
                archivos.append(p)

    # Modo GUI (sin argumentos)
    else:
        print("  Sin argumentos detectados — abriendo selector de archivos...")
        archivos = seleccionar_archivos_gui()

    if not archivos:
        print("✘  No se seleccionaron archivos.")
        sys.exit(1)

    print(f"\n  Archivos a procesar: {len(archivos)}\n")

    lista = combinar(archivos)

    if not lista:
        print("✘  No se pudo procesar ningún archivo.")
        sys.exit(1)

    # Ruta de salida: misma carpeta que el primer archivo
    carpeta_salida = archivos[0].parent
    ruta_salida = carpeta_salida / "reclamos_combinados.json"

    guardar(lista, ruta_salida)


if __name__ == "__main__":
    main()
