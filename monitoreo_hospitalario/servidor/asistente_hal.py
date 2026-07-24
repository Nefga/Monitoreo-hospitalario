"""
asistente_hal.py
------------------
Asistente de voz HAL para el Monitoreo Ambiental Hospitalario.
Adaptado del asistente "ELI" de la Práctica 5 (speech_recognition +
Google Speech API + pyttsx3), pero en vez de controlar LEDs, HAL:

  1. Se conecta al servidor_central.py (TCP:5000) y mantiene en memoria
     el último estado de cada cuarto.
  2. AVISA SOLO en voz, sin que le preguntes, en cuanto algún cuarto se
     pase de los rangos normales (usa el mismo campo "buzzer" que ya
     calcula el servidor).
  3. Te responde si le preguntas por un cuarto: di "HAL" para activarlo,
     luego "cuarto 3" (o "cómo está el cuarto 3") y te dice sus valores.

Requiere las mismas librerías que ELI:
    pip install speech_recognition pyaudio pyttsx3

Uso:
    Primero corre servidor_central.py en otra terminal.
    Luego, en una terminal nueva:
        python asistente_hal.py
"""

import json
import os
import platform
import re
import signal
import socket
import subprocess
import threading
import time

import speech_recognition as sr
import pyttsx3

HOST = "127.0.0.1"
PUERTO = 5050

PALABRA_ACTIVACION = "HAL"


def _manejar_ctrl_c(signum, frame):
    """Cierra el programa DE INMEDIATO al presionar Ctrl+C, sin dejar que
    ningún hilo (el de voz o el de alertas) alcance a terminar de hablar
    o a repetir algo con la voz por defecto del sistema."""
    print("\n[HAL] Cerrando...")
    os._exit(0)


signal.signal(signal.SIGINT, _manejar_ctrl_c)

# ---------- Estado compartido ----------
lock_estado = threading.Lock()
estado_cuartos = {}          # cuarto_id -> dict con la última lectura completa
alerta_previa = {}           # cuarto_id -> bool (para no repetir el mismo aviso)

lock_voz = threading.Lock()  # para que dos hilos no hablen al mismo tiempo
evento_hablando = threading.Event()  # indica si HAL está hablando ahorita mismo


def hablar(texto: str):
    """Sintetiza voz.

    En macOS usa el comando nativo `say` (viene integrado en el sistema,
    la misma voz de "Contenido hablado"), porque pyttsx3 tiene un bug de
    compatibilidad conocido con las versiones nuevas de pyobjc/macOS y
    truena con NameError: name 'objc' is not defined.

    En otros sistemas (Windows/Linux) usa pyttsx3 normalmente, como ELI.

    Mientras habla, activa evento_hablando para que bucle_voz() NO escuche
    por el micrófono (si no, el micrófono capta la propia voz de HAL por
    las bocinas y la interpreta como si tú hubieras hablado)."""
    with lock_voz:
        evento_hablando.set()
        print(f"HAL: {texto}")
        try:
            if platform.system() == "Darwin":
                _hablar_macos(texto)
            else:
                _hablar_pyttsx3(texto)
        finally:
            time.sleep(0.4)  # margen para que se disipe el eco de las bocinas
            evento_hablando.clear()


def _hablar_macos(texto: str):
    # Prueba varias voces en español instaladas comúnmente en macOS;
    # si ninguna está disponible, usa la voz por defecto del sistema.
    voces_espanol = ["Mónica", "Paulina"]
    for voz in voces_espanol:
        try:
            resultado = subprocess.run(
                ["say", "-v", voz, texto], capture_output=True, timeout=20
            )
            if resultado.returncode == 0:
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    subprocess.run(["say", texto])  # voz por defecto del sistema


def _hablar_pyttsx3(texto: str):
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 0.9)
    engine.say(texto)
    engine.runAndWait()


# ============================================================
# HILO 1: conexión al servidor central (recibe datos de todos los cuartos)
# ============================================================

def escuchar_servidor():
    while True:
        try:
            with socket.create_connection((HOST, PUERTO), timeout=5) as sock:
                print(f"[HAL] Conectado al servidor central en {HOST}:{PUERTO}")
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
                        procesar_payload(payload)
        except (ConnectionRefusedError, OSError):
            print("[HAL] Servidor central no disponible, reintentando en 3s...")
            time.sleep(3)


def procesar_payload(payload: dict):
    cuarto_id = payload.get("cuarto_id")
    if cuarto_id is None:
        return

    with lock_estado:
        estado_cuartos[cuarto_id] = payload
        buzzer_ahora = bool(payload.get("buzzer"))
        buzzer_antes = alerta_previa.get(cuarto_id, False)
        alerta_previa[cuarto_id] = buzzer_ahora

    # Avisar SOLO cuando la alerta ACABA de activarse (transición False -> True),
    # para no repetir el mismo aviso cada 2 segundos mientras siga en alerta.
    if buzzer_ahora and not buzzer_antes:
        motivo = describir_motivo_alerta(payload)
        hablar(f"Atención, el cuarto {cuarto_id} está fuera de rango. {motivo}")


def describir_motivo_alerta(payload: dict) -> str:
    partes = []
    if payload.get("temp", 0) > 28.0:
        partes.append(f"temperatura en {payload['temp']} grados")
    if payload.get("humedad", 0) > 70.0:
        partes.append(f"humedad en {payload['humedad']} por ciento")
    if payload.get("co2_ppm", 0) > 1000:
        partes.append(f"calidad de aire en {payload['co2_ppm']} partes por millón")
    return "Motivo: " + ", ".join(partes) + "." if partes else ""


# ============================================================
# INTERPRETACIÓN DE COMANDOS (función pura, fácil de probar)
# ============================================================

def interpretar_comando(texto: str):
    """
    Devuelve una tupla (tipo, cuarto_id):
      ("salir", None)   -> desactivar HAL
      ("todos", None)    -> reporte de todos los cuartos
      ("cuarto", N)       -> reporte del cuarto N
      (None, None)         -> no se entendió el comando
    """
    texto = texto.upper()

    if "SALIR" in texto:
        return ("salir", None)

    if "TODOS" in texto or "GENERAL" in texto:
        return ("todos", None)

    coincidencia = re.search(r"CUARTO\s*(\d+)", texto)
    if coincidencia:
        return ("cuarto", int(coincidencia.group(1)))

    return (None, None)


def describir_cuarto(cuarto_id: int) -> str:
    with lock_estado:
        datos = estado_cuartos.get(cuarto_id)

    if datos is None:
        return f"No tengo datos todavía del cuarto {cuarto_id}."

    estado = "en alerta" if datos.get("buzzer") else "en rango normal"
    return (
        f"Cuarto {cuarto_id}: temperatura {datos.get('temp')} grados, "
        f"humedad {datos.get('humedad')} por ciento, "
        f"luz {datos.get('lux')} lux, "
        f"calidad de aire {datos.get('co2_ppm')} partes por millón. "
        f"Estado {estado}."
    )


def describir_todos_los_cuartos() -> str:
    with lock_estado:
        ids = sorted(estado_cuartos.keys())

    if not ids:
        return "Todavía no tengo datos de ningún cuarto."

    en_alerta = [cid for cid in ids if estado_cuartos[cid].get("buzzer")]
    if en_alerta:
        lista = ", ".join(str(c) for c in en_alerta)
        return f"De {len(ids)} cuartos, los cuartos {lista} están en alerta. Los demás están normales."
    return f"Los {len(ids)} cuartos están dentro de rangos normales."


# ============================================================
# HILO 2: reconocimiento de voz (igual estructura que ELI)
# ============================================================

def bucle_voz():
    r = sr.Recognizer()
    mic = sr.Microphone()

    activado = False
    print("=" * 50)
    print(f"Asistente de voz: {PALABRA_ACTIVACION}")
    print(f"Di '{PALABRA_ACTIVACION}' para activar la escucha")
    print("Luego pregunta, por ejemplo: 'cuarto 3', 'todos los cuartos'")
    print("Di 'salir' para desactivar (sin cerrar el programa)")
    print("=" * 50)
    hablar(f"Hola, soy {PALABRA_ACTIVACION}. Di {PALABRA_ACTIVACION} para activarme.")

    while True:
        if evento_hablando.is_set():
            time.sleep(0.2)
            continue

        with mic as source:
            print("\nEscuchando...")
            r.adjust_for_ambient_noise(source, duration=1)
            r.energy_threshold = 100
            try:
                audio = r.listen(source, timeout=3, phrase_time_limit=4)
            except sr.WaitTimeoutError:
                continue

        if evento_hablando.is_set():
            # HAL empezó a hablar (una alerta) justo mientras escuchábamos;
            # descartamos este audio para no procesar su propio eco.
            continue

        try:
            texto = r.recognize_google(audio, language="es-MX").upper()
            print("Dijiste:", texto)
        except sr.UnknownValueError:
            print("No entendí")
            continue
        except sr.RequestError as e:
            print("Error de conexión con Google Speech:", e)
            continue

        if not activado:
            if PALABRA_ACTIVACION in texto:
                activado = True
                hablar(f"Hola, soy {PALABRA_ACTIVACION}. ¿Qué cuarto quieres consultar?")
            continue

        tipo, cuarto_id = interpretar_comando(texto)

        if tipo == "salir":
            activado = False
            hablar(f"{PALABRA_ACTIVACION} desactivado. Di {PALABRA_ACTIVACION} para volver a activarme.")
        elif tipo == "cuarto":
            hablar(describir_cuarto(cuarto_id))
        elif tipo == "todos":
            hablar(describir_todos_los_cuartos())
        else:
            hablar("No reconocí ese comando. Puedes decir, por ejemplo, cuarto 2, o todos los cuartos.")


def main():
    hilo_servidor = threading.Thread(target=escuchar_servidor, daemon=True)
    hilo_servidor.start()

    time.sleep(1)  # dar tiempo a conectar antes de empezar a escuchar
    bucle_voz()


if __name__ == "__main__":
    main()
