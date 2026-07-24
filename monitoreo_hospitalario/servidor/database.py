"""
database.py
-----------
Maneja la base de datos SQLite del sistema de Monitoreo Ambiental Hospitalario.

NOVEDAD (multi-cuarto): ahora el sistema puede simular varios cuartos de
hospital a la vez. Cada lectura queda asociada a un cuarto (cuarto_id).
Un solo cuarto puede ser el "real" (conectado al ESP32 de tu compañero);
el resto son simulados.

Guarda cada lectura de sensores y cada evento de alerta, y ofrece consultas
agrupadas por turno (6am-2pm, 2pm-10pm, 10pm-6am) para el generador de reportes.
"""

import os
import sqlite3
from datetime import datetime, time
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitoreo.db")


def inicializar_db(ruta=DB_PATH):
    con = sqlite3.connect(ruta)
    cur = con.cursor()

    # Catálogo de cuartos del hospital
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cuartos (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            es_real INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cuarto_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            lux REAL,
            temperatura REAL,
            humedad REAL,
            co2_ppm REAL,
            buzzer_activo INTEGER,
            modo_automatico INTEGER,
            FOREIGN KEY (cuarto_id) REFERENCES cuartos(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cuarto_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            tipo TEXT NOT NULL,        -- 'temperatura', 'humedad', 'co2'
            valor REAL,
            umbral REAL,
            mensaje TEXT,
            FOREIGN KEY (cuarto_id) REFERENCES cuartos(id)
        )
    """)

    con.commit()
    con.close()


@contextmanager
def conexion(ruta=DB_PATH):
    con = sqlite3.connect(ruta)
    try:
        yield con
    finally:
        con.close()


# ---------- Cuartos ----------

def configurar_cuartos(n_cuartos: int, cuarto_real_id: int = None, ruta=DB_PATH):
    """
    Crea (o actualiza) el catálogo de cuartos: Cuarto 1, Cuarto 2, ..., Cuarto N.
    Si cuarto_real_id se especifica (ej. 1), ese cuarto se marca como real
    (conectado al ESP32); el resto quedan marcados como simulados.
    Se puede volver a llamar para cambiar cuántos cuartos hay.
    """
    with conexion(ruta) as con:
        cur = con.cursor()
        cur.execute("DELETE FROM cuartos")
        for i in range(1, n_cuartos + 1):
            es_real = 1 if (cuarto_real_id is not None and i == cuarto_real_id) else 0
            cur.execute(
                "INSERT INTO cuartos (id, nombre, es_real) VALUES (?, ?, ?)",
                (i, f"Cuarto {i}", es_real)
            )
        con.commit()


def obtener_cuartos(ruta=DB_PATH):
    """Devuelve lista de dicts: [{'id':1,'nombre':'Cuarto 1','es_real':True}, ...]"""
    with conexion(ruta) as con:
        cur = con.cursor()
        cur.execute("SELECT id, nombre, es_real FROM cuartos ORDER BY id")
        filas = cur.fetchall()
    return [{"id": f[0], "nombre": f[1], "es_real": bool(f[2])} for f in filas]


# ---------- Lecturas ----------

def guardar_lectura(cuarto_id: int, lectura: dict, ruta=DB_PATH):
    """lectura: dict con lux, temp, humedad, co2_ppm, buzzer, modo_auto"""
    with conexion(ruta) as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO lecturas (cuarto_id, timestamp, lux, temperatura, humedad, co2_ppm, buzzer_activo, modo_automatico)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cuarto_id,
            datetime.now().isoformat(timespec="seconds"),
            lectura.get("lux"),
            lectura.get("temp"),
            lectura.get("humedad"),
            lectura.get("co2_ppm"),
            1 if lectura.get("buzzer") else 0,
            1 if lectura.get("modo_auto") else 0,
        ))
        con.commit()


def guardar_alerta(cuarto_id: int, tipo: str, valor: float, umbral: float, mensaje: str, ruta=DB_PATH):
    with conexion(ruta) as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO alertas (cuarto_id, timestamp, tipo, valor, umbral, mensaje)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cuarto_id, datetime.now().isoformat(timespec="seconds"), tipo, valor, umbral, mensaje))
        con.commit()


def obtener_ultimas_lecturas(cuarto_id: int = None, n=50, ruta=DB_PATH):
    """Si cuarto_id es None, devuelve las últimas n lecturas de TODOS los cuartos combinados."""
    with conexion(ruta) as con:
        cur = con.cursor()
        if cuarto_id is None:
            cur.execute("""
                SELECT cuarto_id, timestamp, lux, temperatura, humedad, co2_ppm, buzzer_activo
                FROM lecturas ORDER BY id DESC LIMIT ?
            """, (n,))
        else:
            cur.execute("""
                SELECT cuarto_id, timestamp, lux, temperatura, humedad, co2_ppm, buzzer_activo
                FROM lecturas WHERE cuarto_id = ? ORDER BY id DESC LIMIT ?
            """, (cuarto_id, n))
        filas = cur.fetchall()
    return list(reversed(filas))


def obtener_ultima_lectura_por_cuarto(ruta=DB_PATH):
    """Devuelve un dict {cuarto_id: (timestamp, lux, temp, humedad, co2, buzzer)}
    con la lectura más reciente de cada cuarto. Útil para el dashboard/gráfica."""
    with conexion(ruta) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT l.cuarto_id, l.timestamp, l.lux, l.temperatura, l.humedad, l.co2_ppm, l.buzzer_activo
            FROM lecturas l
            INNER JOIN (
                SELECT cuarto_id, MAX(id) AS max_id FROM lecturas GROUP BY cuarto_id
            ) ultimo ON l.cuarto_id = ultimo.cuarto_id AND l.id = ultimo.max_id
        """)
        filas = cur.fetchall()
    return {f[0]: f[1:] for f in filas}


# ---------- Turnos ----------
# Turno 1: 06:00 - 14:00   Turno 2: 14:00 - 22:00   Turno 3: 22:00 - 06:00
TURNOS = {
    "Turno 1 (6am-2pm)": (time(6, 0), time(14, 0)),
    "Turno 2 (2pm-10pm)": (time(14, 0), time(22, 0)),
    "Turno 3 (10pm-6am)": (time(22, 0), time(6, 0)),  # cruza medianoche
}


def _hora_en_turno(hora: time, inicio: time, fin: time) -> bool:
    if inicio < fin:
        return inicio <= hora < fin
    # turno que cruza medianoche (ej. 22:00 - 06:00)
    return hora >= inicio or hora < fin


def obtener_lecturas_por_fecha(fecha_iso: str, cuarto_id: int = None, ruta=DB_PATH):
    """fecha_iso: 'YYYY-MM-DD'. Si cuarto_id es None, trae todos los cuartos."""
    with conexion(ruta) as con:
        cur = con.cursor()
        if cuarto_id is None:
            cur.execute("""
                SELECT cuarto_id, timestamp, lux, temperatura, humedad, co2_ppm, buzzer_activo
                FROM lecturas WHERE timestamp LIKE ?
                ORDER BY timestamp ASC
            """, (f"{fecha_iso}%",))
        else:
            cur.execute("""
                SELECT cuarto_id, timestamp, lux, temperatura, humedad, co2_ppm, buzzer_activo
                FROM lecturas WHERE timestamp LIKE ? AND cuarto_id = ?
                ORDER BY timestamp ASC
            """, (f"{fecha_iso}%", cuarto_id))
        return cur.fetchall()


def estadisticas_por_turno(fecha_iso: str, cuarto_id: int = None, ruta=DB_PATH):
    """Calcula min/max/promedio de temp, humedad y co2 por turno, y cuenta alertas.
    Si cuarto_id es None, agrega TODOS los cuartos juntos (reporte general del hospital)."""
    filas = obtener_lecturas_por_fecha(fecha_iso, cuarto_id, ruta)
    resultado = {nombre: {"lecturas": [], } for nombre in TURNOS}

    for cid, ts, lux, temp, hum, co2, buzzer in filas:
        hora = datetime.fromisoformat(ts).time()
        for nombre, (inicio, fin) in TURNOS.items():
            if _hora_en_turno(hora, inicio, fin):
                resultado[nombre]["lecturas"].append({
                    "cuarto_id": cid, "timestamp": ts, "lux": lux, "temp": temp,
                    "humedad": hum, "co2": co2, "buzzer": buzzer
                })
                break

    resumen = {}
    for nombre, datos in resultado.items():
        lecturas = datos["lecturas"]
        if not lecturas:
            resumen[nombre] = None
            continue
        temps = [l["temp"] for l in lecturas if l["temp"] is not None]
        hums = [l["humedad"] for l in lecturas if l["humedad"] is not None]
        co2s = [l["co2"] for l in lecturas if l["co2"] is not None]
        alertas = sum(1 for l in lecturas if l["buzzer"])

        resumen[nombre] = {
            "n_lecturas": len(lecturas),
            "temp_min": min(temps) if temps else None,
            "temp_max": max(temps) if temps else None,
            "temp_prom": round(sum(temps) / len(temps), 1) if temps else None,
            "humedad_min": min(hums) if hums else None,
            "humedad_max": max(hums) if hums else None,
            "humedad_prom": round(sum(hums) / len(hums), 1) if hums else None,
            "co2_min": min(co2s) if co2s else None,
            "co2_max": max(co2s) if co2s else None,
            "co2_prom": round(sum(co2s) / len(co2s), 1) if co2s else None,
            "alertas": alertas,
        }
    return resumen


if __name__ == "__main__":
    inicializar_db()
    print(f"Base de datos inicializada en '{DB_PATH}'")
