"""
grafica_tiempo_real.py
------------------------
Ventana de gráfica en tiempo real (como la Práctica 3 de la bitácora, pero
con TODOS los cuartos del hospital a la vez, cada uno con su propio color).

NOVEDAD: ya no hay que editar el código para cambiar de variable. La
ventana tiene botones a la izquierda (Luz / Temperatura / Humedad / Aire)
para cambiar qué se está graficando SIN cerrar el programa. Solo se
muestra UNA variable a la vez -> gráfica limpia, no "puras rayas".

Se conecta como CLIENTE al servidor_central.py (TCP:5050) y va guardando
las 4 variables de cada cuarto según van llegando las lecturas; la
gráfica solo dibuja la variable seleccionada en ese momento.

Uso:
    Primero corre servidor_central.py en otra terminal.
    Luego, en una terminal nueva:
        python grafica_tiempo_real.py
"""

import json
import socket
import threading
import time
from collections import defaultdict, deque

import matplotlib.pyplot as plt
from matplotlib.widgets import RadioButtons

HOST = "127.0.0.1"
PUERTO = 5050

VARIABLES = ["lux", "temp", "humedad", "co2_ppm"]
ETIQUETAS_VARIABLE = {
    "lux": "Luz (lux)",
    "temp": "Temperatura (°C)",
    "humedad": "Humedad (%)",
    "co2_ppm": "CO2 (ppm)",
}
ETIQUETAS_BOTON = {
    "lux": "Luz",
    "temp": "Temperatura",
    "humedad": "Humedad",
    "co2_ppm": "Calidad de aire",
}

MAX_PUNTOS = 60   # cuántos puntos recientes se muestran por cuarto

# ---------- Estado compartido entre el hilo de red y el hilo de gráfica ----------
lock = threading.Lock()
tiempos_por_cuarto = defaultdict(lambda: deque(maxlen=MAX_PUNTOS))
# datos_por_cuarto[variable][cuarto_id] = deque de valores
datos_por_cuarto = {v: defaultdict(lambda: deque(maxlen=MAX_PUNTOS)) for v in VARIABLES}
contador_por_cuarto = defaultdict(int)

variable_actual = "lux"   # se cambia con los botones de la izquierda


def escuchar_servidor():
    """Hilo en segundo plano: recibe lecturas del servidor central y guarda
    las 4 variables de cada cuarto (no solo la que se está mostrando)."""
    while True:
        try:
            with socket.create_connection((HOST, PUERTO), timeout=5) as sock:
                print(f"Conectado al servidor central en {HOST}:{PUERTO}")
                buffer = ""
                while True:
                    datos = sock.recv(2048).decode("utf-8", errors="ignore")
                    if not datos:
                        break
                    buffer += datos
                    while "\n" in buffer:
                        linea, buffer = buffer.split("\n", 1)
                        if not linea.strip():
                            continue
                        try:
                            payload = json.loads(linea)
                        except json.JSONDecodeError:
                            continue

                        cuarto_id = payload.get("cuarto_id")
                        if cuarto_id is None:
                            continue

                        with lock:
                            contador_por_cuarto[cuarto_id] += 1
                            tiempos_por_cuarto[cuarto_id].append(contador_por_cuarto[cuarto_id])
                            for var in VARIABLES:
                                valor = payload.get(var)
                                if valor is not None:
                                    datos_por_cuarto[var][cuarto_id].append(valor)
        except (ConnectionRefusedError, OSError):
            print("Servidor central no disponible, reintentando en 3s...")
            time.sleep(3)


def main():
    hilo = threading.Thread(target=escuchar_servidor, daemon=True)
    hilo.start()

    plt.ion()
    fig = plt.figure(figsize=(10, 5.5))
    fig.canvas.manager.set_window_title("Monitoreo Ambiental Hospitalario - Gráfica en tiempo real")

    # Panel de botones a la izquierda, la gráfica ocupa el resto
    ax_botones = fig.add_axes([0.02, 0.55, 0.16, 0.30])
    ax = fig.add_axes([0.26, 0.12, 0.70, 0.78])

    botones = RadioButtons(ax_botones, [ETIQUETAS_BOTON[v] for v in VARIABLES], active=0)
    etiqueta_a_variable = {ETIQUETAS_BOTON[v]: v for v in VARIABLES}

    def al_elegir_variable(etiqueta):
        global variable_actual
        variable_actual = etiqueta_a_variable[etiqueta]

    botones.on_clicked(al_elegir_variable)

    paleta = plt.get_cmap("tab10")  # 10 colores bien diferenciados
    lineas = {}  # cuarto_id -> Line2D (se recrean si cambia la variable)
    variable_dibujada = None

    print("Ventana de gráfica iniciada. Usa los botones de la izquierda para "
          "cambiar de variable. Cierra la ventana o Ctrl+C para salir.")

    while True:
        # Si el usuario cambió de variable, empezamos las líneas desde cero
        if variable_actual != variable_dibujada:
            ax.clear()
            lineas = {}
            variable_dibujada = variable_actual

        with lock:
            cuartos_activos = sorted(tiempos_por_cuarto.keys())
            for cuarto_id in cuartos_activos:
                if cuarto_id not in lineas:
                    color = paleta((cuarto_id - 1) % 10)
                    (linea,) = ax.plot([], [], color=color, linewidth=2, label=f"{cuarto_id}")
                    lineas[cuarto_id] = linea

                lineas[cuarto_id].set_data(
                    list(tiempos_por_cuarto[cuarto_id]),
                    list(datos_por_cuarto[variable_dibujada][cuarto_id])
                )

        if lineas:
            ax.relim()
            ax.autoscale_view()

        etiqueta_var = ETIQUETAS_VARIABLE.get(variable_dibujada, variable_dibujada)
        ax.set_xlabel("Lectura #")
        ax.set_ylabel(etiqueta_var)
        ax.set_title(f"{etiqueta_var} por cuarto — tiempo real")
        ax.grid(True, alpha=0.3)
        if lineas:
            ax.legend(loc="upper left", ncol=min(len(lineas), 5), title="Cuarto")

        plt.pause(0.5)


if __name__ == "__main__":
    main()
