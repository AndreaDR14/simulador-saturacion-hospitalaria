"""
database.py
------------
Persistencia en SQLite para el Simulador de Saturación Hospitalaria.

Esquema (3 tablas normalizadas):

    escenarios(id, nombre, ocupacion_inicial, tasa_admisiones,
               estancia_promedio, capacidad_actual, capacidad_futura,
               dias, variabilidad, semilla, creado_en)

    resultados(id, escenario_id -> escenarios.id,
               dia_saturacion, ocupacion_final, creado_en)

    ocupacion_diaria(id, resultado_id -> resultados.id, dia, ocupacion)

No se usa ningún ORM a propósito: el objetivo es que se note con claridad
el SQL detrás de cada operación, algo valioso en un contexto académico.

SQLite no requiere ningún servidor ni instalación: el archivo de la base
de datos (instance/simulador.db) se crea solo la primera vez que se
ejecuta la app.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from model import ParametrosSimulacion, ResultadoSimulacion

DB_PATH = "instance/simulador.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS escenarios (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    ocupacion_inicial   REAL NOT NULL,
    tasa_admisiones     REAL NOT NULL,
    estancia_promedio   REAL NOT NULL,
    capacidad_actual    REAL NOT NULL,
    capacidad_futura    REAL NOT NULL,
    dias                INTEGER NOT NULL,
    variabilidad        REAL NOT NULL,
    semilla             INTEGER,
    politica_activa     INTEGER NOT NULL DEFAULT 0,
    umbral_politica     REAL NOT NULL DEFAULT 0.9,
    creado_en           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resultados (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    escenario_id        INTEGER NOT NULL REFERENCES escenarios(id) ON DELETE CASCADE,
    dia_saturacion      INTEGER,
    ocupacion_final     REAL NOT NULL,
    creado_en           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ocupacion_diaria (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    resultado_id        INTEGER NOT NULL REFERENCES resultados(id) ON DELETE CASCADE,
    dia                 INTEGER NOT NULL,
    ocupacion           REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_resultados_escenario ON resultados(escenario_id);
CREATE INDEX IF NOT EXISTS idx_ocupacion_resultado ON ocupacion_diaria(resultado_id);
"""


@contextmanager
def get_conn():
    """Provee una conexión con claves foráneas activas y la cierra al salir."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Crea las tablas si no existen. Se llama una vez al iniciar la app."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def guardar_escenario(nombre: str, params: ParametrosSimulacion, resultado: ResultadoSimulacion) -> int:
    """Guarda un escenario completo (parámetros + resultado + serie diaria).

    Retorna el id del escenario insertado.
    """
    ahora = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO escenarios
               (nombre, ocupacion_inicial, tasa_admisiones, estancia_promedio,
                capacidad_actual, capacidad_futura, dias, variabilidad, semilla,
                politica_activa, umbral_politica, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (nombre, params.ocupacion_inicial, params.tasa_admisiones, params.estancia_promedio,
             params.capacidad_actual, params.capacidad_futura, params.dias,
             params.variabilidad, params.semilla,
             int(params.politica_activa), params.umbral_politica, ahora),
        )
        escenario_id = cur.lastrowid

        cur = conn.execute(
            """INSERT INTO resultados (escenario_id, dia_saturacion, ocupacion_final, creado_en)
               VALUES (?, ?, ?, ?)""",
            (escenario_id, resultado.dia_saturacion, resultado.ocupacion_final, ahora),
        )
        resultado_id = cur.lastrowid

        conn.executemany(
            "INSERT INTO ocupacion_diaria (resultado_id, dia, ocupacion) VALUES (?, ?, ?)",
            [(resultado_id, dia, ocup) for dia, ocup in enumerate(resultado.ocupacion_por_dia)],
        )
    return escenario_id


def listar_escenarios() -> List[sqlite3.Row]:
    """Lista todos los escenarios guardados, con su resultado resumido, más recientes primero."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT e.id, e.nombre, e.capacidad_actual, e.capacidad_futura, e.creado_en,
                      e.politica_activa, e.umbral_politica,
                      r.dia_saturacion, r.ocupacion_final
               FROM escenarios e
               JOIN resultados r ON r.escenario_id = e.id
               ORDER BY e.id DESC"""
        ).fetchall()


def obtener_escenario(escenario_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM escenarios WHERE id = ?", (escenario_id,)
        ).fetchone()


def obtener_resultado_completo(escenario_id: int) -> Optional[dict]:
    """Reconstruye escenario + resultado + serie diaria en un solo diccionario."""
    with get_conn() as conn:
        escenario = conn.execute(
            "SELECT * FROM escenarios WHERE id = ?", (escenario_id,)
        ).fetchone()
        if escenario is None:
            return None

        resultado = conn.execute(
            "SELECT * FROM resultados WHERE escenario_id = ?", (escenario_id,)
        ).fetchone()

        serie = conn.execute(
            """SELECT dia, ocupacion FROM ocupacion_diaria
               WHERE resultado_id = ? ORDER BY dia""",
            (resultado["id"],),
        ).fetchall()

        return {
            "escenario": dict(escenario),
            "resultado": dict(resultado),
            "ocupacion_por_dia": [row["ocupacion"] for row in serie],
        }


def eliminar_escenario(escenario_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM escenarios WHERE id = ?", (escenario_id,))
