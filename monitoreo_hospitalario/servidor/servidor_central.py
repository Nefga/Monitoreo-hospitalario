"""
servidor_central.py
--------------------
Servidor central del sistema de Monitoreo Ambiental Hospitalario.

NOVEDAD (un solo Arduino, dos cuartos con datos reales): un Arduino Uno
(firmware/arduino_uno_dht11/arduino_uno_dht11.ino) manda por Serial:
    {"lux": ..., "temp_cuarto1": ..., "humedad_cuarto1": ...,
     "co2_ppm": ..., "temp_cuarto2": ...}

- Cuarto 1: luz, temperatura, humedad y calidad de aire REALES.
- Cuarto 2: solo temperatura REAL/MANUAL mediante potenciómetro.
- Cuarto 2 (luz, humedad y aire) y cuartos 3 en adelante: simulados.

- MODO_SIMULACION = True  -> todo se simula (sin Arduino conectado).
- MODO_SIMULACION = False -> se leen los sensores reales del Arduino.

Uso:
    python servidor_central.py                # modo simulación (default)
    python servidor_central.py /dev/tty.usbmodemXXXX   # con Arduino real
"""

import sys
import json
import socket
import threading
import time
from datetime import datetime

import database as db
import simulador_sensores

HOST = "0.0.0.0"
PUERTO_TCP = 5050   # 5000 choca con AirPlay Receiver en macOS
INTERVALO_SEGUNDOS = 2

# ---------- Umbrales de alerta (deben coincidir con el firmware) ----------
TEMP_MAX_C = 28.0
HUMEDAD_MAX = 70.0
CO2_MAX_PPM = 1000

CUARTO_LUZ_AIRE_REAL = 1   # Cuarto con LDR + MQ-135 reales
CUARTO_TEMP_REAL = 2       # Cuarto con potenciómetro (temperatura real)

MODO_SIMULACION = True   # cambia solo/automáticamente si se pasa un puerto serial

clientes_conectados = []
lock_clientes = threading.Lock()

# Último dato real recibido del Arduino (se conserva entre ciclos por si
# todavía no llega una línea nueva; así el cuarto no "parpadea" a valores
# simulados cada vez que el Arduino tarda un poquito más en mandar datos).
ultimo_dato_arduino = {
    "lux": None,
    "temp_cuarto1": None,
    "humedad_cuarto1": None,
    "co2_ppm": None,
    "temp_cuarto2": None,
}


def evaluar_alertas(cuarto_id: int, lectura: dict) -> bool:
    """Revisa umbrales, registra alertas en BD y devuelve si el buzzer debe sonar."""
    disparo = False

    if lectura["temp"] > TEMP_MAX_C:
        disparo = True
        db.guardar_alerta(cuarto_id, "temperatura", lectura["temp"], TEMP_MAX_C,
                           f"Temperatura crítica: {lectura['temp']}°C (umbral {TEMP_MAX_C}°C)")

    if lectura["humedad"] > HUMEDAD_MAX:
        disparo = True
        db.guardar_alerta(cuarto_id, "humedad", lectura["humedad"], HUMEDAD_MAX,
                           f"Humedad crítica: {lectura['humedad']}% (umbral {HUMEDAD_MAX}%)")

    if lectura["co2_ppm"] > CO2_MAX_PPM:
        disparo = True
        db.guardar_alerta(cuarto_id, "co2", lectura["co2_ppm"], CO2_MAX_PPM,
                           f"Calidad de aire crítica: {lectura['co2_ppm']} ppm (umbral {CO2_MAX_PPM} ppm)")

    return disparo


def difundir_a_clientes(payload: dict):
    linea = (json.dumps(payload) + "\n").encode("utf-8")
    with lock_clientes:
        muertos = []
        for conn in clientes_conectados:
            try:
                conn.sendall(linea)
            except OSError:
                muertos.append(conn)
        for c in muertos:
            clientes_conectados.remove(c)


def manejar_cliente(conn, addr):
    print(f"[TCP] Cliente conectado: {addr}")
    with lock_clientes:
        clientes_conectados.append(conn)
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
    except OSError:
        pass
    finally:
        with lock_clientes:
            if conn in clientes_conectados:
                clientes_conectados.remove(conn)
        conn.close()
        print(f"[TCP] Cliente desconectado: {addr}")


def servidor_tcp():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PUERTO_TCP))
    s.listen()
    print(f"[TCP] Servidor escuchando en {HOST}:{PUERTO_TCP}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=manejar_cliente, args=(conn, addr), daemon=True).start()


def leer_arduino_no_bloqueante(ser):
    """Lee una línea del Arduino SOLO si ya hay datos esperando (no bloquea
    el ciclo si el Arduino todavía no manda nada nuevo). Actualiza y
    devuelve el último dato conocido (con lo nuevo fusionado encima)."""
    global ultimo_dato_arduino
    try:
        if ser.in_waiting > 0:
            linea = ser.readline().decode("utf-8", errors="ignore").strip()
            if linea:
                try:
                    nuevo = json.loads(linea)
                    ultimo_dato_arduino.update(nuevo)
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return ultimo_dato_arduino


def construir_lectura(cuarto_id: int, datos_arduino: dict) -> dict:
    """Empieza con una lectura simulada "base" y, si el cuarto tiene
    sensores reales, sobreescribe SOLO los campos que sí mide el Arduino."""
    lectura = simulador_sensores.generar_lectura()

    if MODO_SIMULACION or datos_arduino is None:
        return lectura

    if cuarto_id == CUARTO_LUZ_AIRE_REAL:
        if datos_arduino.get("lux") is not None:
            lectura["lux"] = datos_arduino["lux"]
        if datos_arduino.get("temp_cuarto1") is not None:
            lectura["temp"] = datos_arduino["temp_cuarto1"]
        if datos_arduino.get("humedad_cuarto1") is not None:
            lectura["humedad"] = datos_arduino["humedad_cuarto1"]
        if datos_arduino.get("co2_ppm") is not None:
            lectura["co2_ppm"] = datos_arduino["co2_ppm"]

    if cuarto_id == CUARTO_TEMP_REAL:
        if datos_arduino.get("temp_cuarto2") is not None:
            lectura["temp"] = datos_arduino["temp_cuarto2"]

    return lectura


def procesar_lectura(cuarto_id: int, cuarto_nombre: str, lectura: dict):
    buzzer = evaluar_alertas(cuarto_id, lectura)
    lectura["buzzer"] = buzzer
    lectura["modo_auto"] = True

    db.guardar_lectura(cuarto_id, lectura)

    payload = {
        "cuarto_id": cuarto_id,
        "cuarto_nombre": cuarto_nombre,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **lectura,
    }
    difundir_a_clientes(payload)

    estado = "🔴 ALERTA" if buzzer else "🟢 normal"
    etiqueta_real = ""
    if not MODO_SIMULACION:
        if cuarto_id == CUARTO_LUZ_AIRE_REAL:
            etiqueta_real = " [luz+temp+hum+aire REAL]"
        elif cuarto_id == CUARTO_TEMP_REAL:
            etiqueta_real = " [temp REAL]"
    print(f"[{cuarto_nombre}{etiqueta_real}] luz={lectura['lux']} temp={lectura['temp']}°C "
          f"hum={lectura['humedad']}% co2={lectura['co2_ppm']}ppm -> {estado}")


def bucle_lecturas(n_cuartos: int, puerto_serial=None):
    ser = None
    if not MODO_SIMULACION:
        import serial
        ser = serial.Serial(puerto_serial, 115200, timeout=1)
        print(f"[Serial] Arduino conectado en {puerto_serial} "
              f"(Cuarto {CUARTO_LUZ_AIRE_REAL} = luz+temperatura+humedad+aire reales, "
              f"Cuarto {CUARTO_TEMP_REAL} = temperatura por potenciómetro)")
        time.sleep(2)  # dar tiempo a que el Arduino reinicie tras abrir el puerto

    cuartos = db.obtener_cuartos()
    nombres = {c["id"]: c["nombre"] for c in cuartos}

    while True:
        datos_arduino = None
        if not MODO_SIMULACION:
            datos_arduino = leer_arduino_no_bloqueante(ser)

        for cuarto_id in range(1, n_cuartos + 1):
            lectura = construir_lectura(cuarto_id, datos_arduino)
            procesar_lectura(cuarto_id, nombres.get(cuarto_id, f"Cuarto {cuarto_id}"), lectura)

        time.sleep(INTERVALO_SEGUNDOS)


def preguntar_n_cuartos() -> int:
    while True:
        try:
            respuesta = input("¿Cuántos cuartos tiene el hospital? ").strip()
            n = int(respuesta)
            if n < 1:
                print("Debe ser al menos 1 cuarto.")
                continue
            return n
        except ValueError:
            print("Por favor ingresa un número entero, ej. 5")


def main():
    db.inicializar_db()

    puerto_serial = sys.argv[1] if len(sys.argv) > 1 else None
    global MODO_SIMULACION
    if puerto_serial:
        MODO_SIMULACION = False

    n_cuartos = preguntar_n_cuartos()
    db.configurar_cuartos(n_cuartos, cuarto_real_id=CUARTO_LUZ_AIRE_REAL)

    if MODO_SIMULACION:
        print(f"\nCuartos configurados: {n_cuartos} (todos simulados, sin Arduino conectado)\n")
    else:
        print(f"\nCuartos configurados: {n_cuartos} "
              f"(Cuarto {CUARTO_LUZ_AIRE_REAL}: luz+aire reales | "
              f"Cuarto {CUARTO_TEMP_REAL}: temperatura real | resto simulado)\n")

    threading.Thread(target=servidor_tcp, daemon=True).start()
    bucle_lecturas(n_cuartos, puerto_serial)


if __name__ == "__main__":
    main()
