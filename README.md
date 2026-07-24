[README.MD](https://github.com/user-attachments/files/30327906/README.MD)
#  Sistema de Monitoreo Hospitalario

Sistema de monitoreo ambiental desarrollado para supervisar las condiciones de diferentes habitaciones de un hospital mediante sensores físicos, generación de datos simulados, una interfaz web, gráficas en tiempo real y un cliente de escritorio desarrollado en Java.

El sistema permite visualizar:

* Temperatura.
* Humedad.
* Intensidad de luz.
* Calidad del aire.
* Alertas cuando alguna medición sale de los rangos establecidos.

---

##  Funcionamiento de las habitaciones

### Habitación 1

Utiliza sensores físicos conectados a una placa Arduino:

* Temperatura real mediante un sensor DHT11.
* Humedad real mediante el DHT11.
* Intensidad de luz real mediante un sensor LDR.
* Calidad del aire real mediante un sensor MQ-135.

### Habitación 2

* La temperatura se controla mediante un potenciómetro.
* La humedad, iluminación y calidad del aire se generan de manera simulada.

### Habitación 3 en adelante

Todas las mediciones se generan de manera aleatoria para simular habitaciones adicionales.

---

##  Tecnologías utilizadas

### Hardware

* Arduino Uno.
* Sensor DHT11.
* Sensor de luz LDR.
* Sensor de calidad del aire MQ-135.
* Potenciómetro.
* LED.
* Buzzer.
* Resistencias y cables de conexión.

### Software

* Python 3.
* Flask.
* SQLite.
* PySerial.
* Matplotlib.
* ReportLab.
* Java.
* HTML, CSS y JavaScript.
* Arduino IDE.
* Visual Studio Code.

---

## 🔌 Conexiones del Arduino

| Componente                       | Pin en Arduino Uno |
| -------------------------------- | -----------------: |
| LDR de la habitación 1           |                 A0 |
| DHT11 de la habitación 1         |                 D2 |
| MQ-135 de la habitación 1        |                 A4 |
| Potenciómetro de la habitación 2 |                 A5 |
| Buzzer                           |                 D8 |
| LED                              |                 D9 |

### Conexión del DHT11 de tres pines

| DHT11           | Arduino Uno |
| --------------- | ----------- |
| VCC o `+`       | 5V          |
| DATA, OUT o `S` | D2          |
| GND o `-`       | GND         |

### Conexión del DHT11 de cuatro patas

Observando la rejilla del sensor de frente:

| Pata | Conexión     |
| ---: | ------------ |
|    1 | 5V           |
|    2 | D2           |
|    3 | Sin conexión |
|    4 | GND          |

Para un DHT11 sin módulo se recomienda colocar una resistencia de **10 kΩ entre VCC y DATA**.

> Todos los sensores deben compartir el mismo GND del Arduino.

---

##  Estructura del proyecto

```text
monitoreo_hospitalario/
│
├── cliente_java/
│   └── ClienteMonitoreoHospitalario.java
│
├── firmware/
│   └── arduino_uno_dht11/
│       └── arduino_uno_dht11.ino
│
├── servidor/
│   ├── servidor_central.py
│   ├── grafica_tiempo_real.py
│   ├── asistente_hal.py
│   ├── reportes.py
│   └── requirements.txt
│
├── web/
│   ├── app.py
│   ├── templates/
│   └── static/
│
├── README.md
└── .gitignore
```

---

#  Instalación

## 1. Descargar el proyecto

```bash
git clone URL_DEL_REPOSITORIO
cd monitoreo_hospitalario
```

Reemplaza `URL_DEL_REPOSITORIO` por la dirección real del repositorio en GitHub.

---

## 2. Crear el entorno virtual

### Windows PowerShell

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS o Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Instalar las dependencias

### Windows

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\servidor\requirements.txt
```

### macOS o Linux

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r ./servidor/requirements.txt
```

Si el archivo de requisitos presenta algún problema, las dependencias principales pueden instalarse manualmente:

```bash
pip install flask flask-socketio python-socketio pyserial matplotlib reportlab
```

---

#  Configuración del Arduino

Abrir en Arduino IDE:

```text
firmware/arduino_uno_dht11/arduino_uno_dht11.ino
```

Instalar las siguientes librerías desde el administrador de librerías:

* DHT sensor library by Adafruit.
* Adafruit Unified Sensor.

Después:

1. Seleccionar la placa **Arduino Uno**.
2. Seleccionar el puerto correspondiente.
3. Compilar el programa.
4. Subirlo al Arduino.
5. Cerrar el Monitor Serial antes de ejecutar el servidor Python.

El firmware utiliza una velocidad serial de:

```text
115200 baudios
```

---

#  Ejecución en Windows

Cada componente debe ejecutarse en una terminal diferente de Visual Studio Code.

## Terminal 1: servidor central

Activar el entorno:

```powershell
.\.venv\Scripts\Activate.ps1
```

Consultar los puertos disponibles:

```powershell
python -m serial.tools.list_ports
```

Iniciar el servidor con el Arduino conectado:

```powershell
python .\servidor\servidor_central.py COM5
```

Reemplazar `COM5` por el puerto real del Arduino.

Para ejecutar el servidor sin Arduino y utilizar datos simulados:

```powershell
python .\servidor\servidor_central.py
```

Al iniciar, el programa solicitará la cantidad total de habitaciones:

```text
¿Cuántos cuartos tiene el hospital?
```

Por ejemplo:

```text
4
```

---

## Terminal 2: interfaz web

```powershell
.\.venv\Scripts\Activate.ps1
python .\web\app.py
```

Abrir en el navegador:

```text
http://127.0.0.1:5001
```

---

## Terminal 3: gráfica en tiempo real

```powershell
.\.venv\Scripts\Activate.ps1
python .\servidor\grafica_tiempo_real.py
```

---

## Terminal 4: cliente Java

Entrar a la carpeta:

```powershell
cd .\cliente_java
```

Compilar:

```powershell
javac -encoding UTF-8 ClienteMonitoreoHospitalario.java
```

Ejecutar:

```powershell
java ClienteMonitoreoHospitalario
```

El cliente no necesita Gson ni requiere compilarse específicamente para Java 8.

---

## Terminal 5: asistente HAL opcional

Desde la carpeta principal:

```powershell
.\.venv\Scripts\Activate.ps1
python .\servidor\asistente_hal.py
```

---

#  Ejecución en macOS

## Terminal 1: servidor central

Activar el entorno:

```bash
source .venv/bin/activate
```

Consultar los puertos disponibles:

```bash
python3 -m serial.tools.list_ports
```

También pueden consultarse con:

```bash
ls /dev/cu.*
```

El puerto puede aparecer de alguna de estas formas:

```text
/dev/cu.usbmodem1101
/dev/cu.usbserial-110
/dev/cu.wchusbserial110
```

Iniciar el servidor:

```bash
python3 ./servidor/servidor_central.py /dev/cu.usbmodem1101
```

Para utilizar únicamente datos simulados:

```bash
python3 ./servidor/servidor_central.py
```

---

## Terminal 2: interfaz web

```bash
source .venv/bin/activate
python3 ./web/app.py
```

Abrir:

```text
http://127.0.0.1:5001
```

---

## Terminal 3: gráfica en tiempo real

```bash
source .venv/bin/activate
python3 ./servidor/grafica_tiempo_real.py
```

---

## Terminal 4: cliente Java

```bash
cd ./cliente_java
javac -encoding UTF-8 ClienteMonitoreoHospitalario.java
java ClienteMonitoreoHospitalario
```

---

#  Formato de comunicación serial

El Arduino envía las mediciones al servidor utilizando JSON:

```json
{
  "lux": 420.0,
  "temp_cuarto1": 24.0,
  "humedad_cuarto1": 48.0,
  "co2_ppm": 610.0,
  "temp_cuarto2": 27.5
}
```

El servidor interpreta los datos y los asigna a las habitaciones correspondientes.

---

# Interfaz web

La página web permite:

* Visualizar las habitaciones registradas.
* Consultar temperatura, humedad, luz y calidad del aire.
* Identificar mediciones fuera del rango recomendado.
* Consultar datos almacenados en la base de datos.
* Generar reportes del monitoreo.

La página debe ejecutarse después de iniciar el servidor central, ya que utiliza las mediciones almacenadas por este.

---

#  Solución de problemas

## El puerto COM está ocupado

Cerrar el Monitor Serial de Arduino IDE y volver a ejecutar el servidor.

El Monitor Serial y Python no pueden utilizar el mismo puerto al mismo tiempo.

---

## No aparece ninguna medición en la página

Comprobar que:

1. `servidor_central.py` se encuentre ejecutándose.
2. La terminal del servidor muestre lecturas.
3. Se haya indicado correctamente el número de habitaciones.
4. El Arduino esté conectado al puerto correcto.
5. La base de datos esté siendo actualizada.
6. La página se haya abierto en `http://127.0.0.1:5001`.

---

## Falta ReportLab

```bash
python -m pip install reportlab
```

---

## No se encuentra el módulo serial

```bash
python -m pip install pyserial
```

---

## PowerShell no permite activar el entorno virtual

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

---

## Java no reconoce `javac`

Verificar la instalación:

```bash
java -version
javac -version
```

Es necesario tener instalado un **JDK**, no solamente el entorno de ejecución de Java.

---

#  Orden recomendado de ejecución

1. Conectar el Arduino.
2. Cerrar el Monitor Serial.
3. Ejecutar `servidor_central.py`.
4. Indicar la cantidad de habitaciones.
5. Confirmar que la terminal muestra mediciones.
6. Ejecutar `web/app.py`.
7. Abrir la página web.
8. Ejecutar `grafica_tiempo_real.py`.
9. Compilar y ejecutar el cliente Java.
10. Ejecutar el asistente HAL si se necesita.

---


#  Estado del proyecto

El sistema permite integrar sensores físicos y datos simulados dentro de una misma plataforma de monitoreo.

Actualmente incluye:

* Lecturas reales para la habitación 1.
* Temperatura controlada físicamente para la habitación 2.
* Generación automática de habitaciones simuladas.
* Interfaz web.
* Gráficas en tiempo real.
* Cliente Java.
* Base de datos.
* Generación de reportes.
* Sistema de alertas.

---

#  Autores

Proyecto académico desarrollado para la implementación de un sistema de monitoreo hospitalario mediante sensores, comunicación serial y herramientas de software.

Agregar aquí los nombres de los integrantes:

```text
- Farid Garcia
- Nicole Lewis
- 
```

---

#  Licencia

Este proyecto fue desarrollado con fines académicos y educativos.
