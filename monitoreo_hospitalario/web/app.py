"""
app.py
------
Dashboard web del sistema de Monitoreo Ambiental Hospitalario.

NOVEDAD (multi-cuarto): ahora muestra TODOS los cuartos del hospital al
mismo tiempo, cada uno en su propia tarjeta, con gráfica de todos los
cuartos juntos (una línea de color por cuarto) y una tabla de historial
con columna de cuarto.

Se conecta como CLIENTE al servidor_central.py (TCP:5050), recibe las
lecturas en tiempo real (ya vienen con cuarto_id y cuarto_nombre) y las
retransmite al navegador vía Flask-SocketIO.

Además expone endpoints para:
  - Ver la lista de cuartos configurados
  - Ver el historial reciente (de un cuarto o de todos)
  - Generar y descargar el reporte PDF del día

Uso:
    pip install flask flask-socketio python-socketio eventlet
    python app.py
    Abrir http://localhost:5001
"""

import sys
import os
import json
import socket
import threading
import tempfile

from flask import Flask, render_template, jsonify, send_file, request
from flask_socketio import SocketIO

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "servidor"))
import database as db          # noqa: E402
import reportes                 # noqa: E402

TCP_HOST = "127.0.0.1"
TCP_PUERTO = 5050   # 5000 choca con AirPlay Receiver en macOS

app = Flask(__name__)
app.config["SECRET_KEY"] = "monitoreo-hospitalario-secret"
socketio = SocketIO(app, cors_allowed_origins="*")


def escuchar_servidor_tcp():
    """Hilo en segundo plano: se conecta al servidor central y reenvía cada
    lectura recibida (de cualquier cuarto) a todos los navegadores conectados
    vía Socket.IO."""
    while True:
        try:
            with socket.create_connection((TCP_HOST, TCP_PUERTO), timeout=5) as sock:
                print(f"[Web] Conectado al servidor central en {TCP_HOST}:{TCP_PUERTO}")
                buffer = ""
                while True:
                    datos = sock.recv(1024).decode("utf-8", errors="ignore")
                    if not datos:
                        break
                    buffer += datos
                    while "\n" in buffer:
                        linea, buffer = buffer.split("\n", 1)
                        if not linea.strip():
                            continue
                        try:
                            payload = json.loads(linea)
                            socketio.emit("nueva_lectura", payload)
                        except json.JSONDecodeError:
                            pass
        except (ConnectionRefusedError, OSError):
            print("[Web] Servidor central no disponible, reintentando en 3s...")
            socketio.sleep(3)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cuartos")
def cuartos():
    """Lista de cuartos configurados (id, nombre, si es el real)."""
    return jsonify(db.obtener_cuartos())


@app.route("/api/historial")
def historial():
    """?cuarto=2&n=50  -> historial de un cuarto. Sin 'cuarto' -> todos juntos."""
    n = int(request.args.get("n", 50))
    cuarto_param = request.args.get("cuarto")
    cuarto_id = int(cuarto_param) if cuarto_param else None

    filas = db.obtener_ultimas_lecturas(cuarto_id=cuarto_id, n=n)
    resultado = [
        {"cuarto_id": f[0], "timestamp": f[1], "lux": f[2], "temp": f[3],
         "humedad": f[4], "co2_ppm": f[5], "buzzer": bool(f[6])}
        for f in filas
    ]
    return jsonify(resultado)


@app.route("/api/reporte/<fecha>")
def reporte(fecha):
    """Genera y descarga el reporte PDF de una fecha (YYYY-MM-DD), de todo el hospital."""
    ruta_salida = os.path.join(tempfile.gettempdir(), f"reporte_{fecha}.pdf")
    ruta = reportes.generar_reporte_pdf(fecha, ruta_salida=ruta_salida)
    return send_file(ruta, as_attachment=True, download_name=f"reporte_{fecha}.pdf")


if __name__ == "__main__":
    db.inicializar_db()
    hilo = threading.Thread(target=escuchar_servidor_tcp, daemon=True)
    hilo.start()
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, allow_unsafe_werkzeug=True)
