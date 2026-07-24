"""
simulador_sensores.py
----------------------
Genera lecturas de sensores simuladas (LDR, DHT11, MQ-135) para los
cuartos que NO tienen hardware real conectado. También sirve como
"base" para los cuartos que sí tienen hardware parcial (ej. Cuarto 1
con LDR+MQ135 real: la humedad de ese cuarto sigue siendo simulada,
mientras que la luz y el CO2 se sobrescriben con datos reales).

Simula variación realista a lo largo del día, con picos OCASIONALES
(poco frecuentes a propósito, para que las alertas de HAL no se disparen
todo el tiempo y sí te deje preguntarle cosas).
"""

import random
import math
from datetime import datetime

_tick = 0

# Probabilidad de que en una lectura cualquiera aparezca un pico fuera de
# rango. Números bajos a propósito: con varios cuartos generando datos
# cada 2s, incluso un 8% dispara alertas casi todo el tiempo.
PROB_PICO_TEMP = 0.015   # ~1.5%
PROB_PICO_CO2 = 0.01     # ~1%


def generar_lectura():
    """Devuelve un dict con la misma forma que enviaría el Arduino real."""
    global _tick
    _tick += 1

    hora_actual = datetime.now().hour + datetime.now().minute / 60.0

    # --- Luz: sigue un patrón tipo curva de día (más luz al mediodía) ---
    luz_base = max(0, 800 * math.sin((hora_actual - 6) / 12 * math.pi))
    lux = round(luz_base + random.uniform(-30, 30), 1)
    lux = max(0, lux)

    # --- Temperatura: ronda 22-27°C, con picos ocasionales que cruzan 28°C ---
    temp_base = 24.5 + 2 * math.sin(_tick / 20)
    if random.random() < PROB_PICO_TEMP:
        temp_base += random.uniform(3, 5)
    temp = round(temp_base + random.uniform(-0.5, 0.5), 1)

    # --- Humedad: ronda 40-60% ---
    humedad = round(50 + 8 * math.sin(_tick / 15) + random.uniform(-3, 3), 1)
    humedad = min(100, max(0, humedad))

    # --- CO2 / calidad de aire (ppm): normalmente 400-800, picos ocasionales ---
    co2_base = 550 + 100 * math.sin(_tick / 25)
    if random.random() < PROB_PICO_CO2:
        co2_base += random.uniform(400, 700)
    co2_ppm = round(max(350, co2_base + random.uniform(-40, 40)), 1)

    return {
        "lux": lux,
        "temp": temp,
        "humedad": humedad,
        "co2_ppm": co2_ppm,
    }


if __name__ == "__main__":
    import time
    print("Simulando lecturas de sensores (Ctrl+C para detener)...")
    while True:
        print(generar_lectura())
        time.sleep(2)
