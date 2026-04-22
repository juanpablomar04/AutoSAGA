"""
historial.py — Módulo de persistencia local con SQLite.

Gestiona el historial de reclamos ejecutados por AutoSAGA.
La base de datos se crea automáticamente en la misma carpeta del ejecutable.
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

# Ruta de la base de datos junto al ejecutable / script
DB_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "autosaga_historial.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # acceso por nombre de columna
    return conn


def inicializar():
    """Crea la tabla si no existe. Llamar una vez al arrancar la app."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reclamos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha      TEXT    NOT NULL,
                orden      TEXT    NOT NULL,
                chasis     TEXT    NOT NULL,
                codigo     TEXT    NOT NULL,
                kilometraje TEXT   NOT NULL,
                recepcion  TEXT    NOT NULL,
                reparacion TEXT    NOT NULL,
                resultado  TEXT    NOT NULL,  -- 'ok' | 'error'
                detalle    TEXT                -- mensaje de error si aplica
            )
        """)
        conn.commit()


def guardar_reclamo(
    orden: str,
    chasis: str,
    codigo: str,
    kilometraje: str,
    recepcion: str,
    reparacion: str,
    resultado: str = "ok",
    detalle: str = "",
):
    """Inserta un registro en el historial."""
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reclamos
                (fecha, orden, chasis, codigo, kilometraje, recepcion, reparacion, resultado, detalle)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fecha, orden, chasis, codigo, kilometraje, recepcion, reparacion, resultado, detalle),
        )
        conn.commit()


def obtener_historial(limite: int = 200) -> list[sqlite3.Row]:
    """Devuelve los últimos `limite` reclamos, del más reciente al más antiguo."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM reclamos ORDER BY id DESC LIMIT ?", (limite,)
        )
        return cursor.fetchall()


def eliminar_registro(record_id: int):
    """Elimina un registro por su id."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM reclamos WHERE id = ?", (record_id,))
        conn.commit()


def limpiar_historial():
    """Borra todos los registros."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM reclamos")
        conn.commit()
