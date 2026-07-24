/*
 * MONITOREO AMBIENTAL HOSPITALARIO - Arduino Uno + DHT11
 * -------------------------------------------------------
 * CUARTO 1 (sensores reales):
 *   - LDR: luz
 *   - DHT11: temperatura y humedad
 *   - MQ-135: calidad de aire
 *
 * CUARTO 2:
 *   - Potenciómetro: temperatura simulada manualmente
 *
 * CUARTOS 3 EN ADELANTE:
 *   - Todos los datos son simulados por servidor_central.py
 *
 * JSON enviado por Serial cada 2 segundos:
 * {"lux":...,"temp_cuarto1":...,"humedad_cuarto1":...,
 *  "co2_ppm":...,"temp_cuarto2":...}
 */

#include <DHT.h>

// ---------- Pines Arduino Uno ----------
#define PIN_LDR      A0
#define PIN_MQ135    A4
#define PIN_POT      A5
#define PIN_DHT      2
#define PIN_LED      9
#define PIN_BUZZER   8

#define DHTTYPE DHT11
DHT dht(PIN_DHT, DHTTYPE);

// ---------- Calibración LDR ----------
const int   ADC_OSCURO    = 1023;
const int   ADC_BRILLANTE = 50;
const float LUX_OSCURO    = 0.0;
const float LUX_BRILLANTE = 1000.0;
const int   UMBRAL_OSCURIDAD_ADC = 700;

// ---------- Potenciómetro -> temperatura del Cuarto 2 ----------
const float TEMP_MIN = 15.0;
const float TEMP_MAX = 40.0;

const unsigned long INTERVALO_ENVIO = 2000;
unsigned long ultimoEnvio = 0;

// Conservan la última lectura válida del DHT11.
// Si al arrancar todavía no hay una lectura válida se envía null.
float ultimaTempCuarto1 = NAN;
float ultimaHumedadCuarto1 = NAN;

void setup() {
  Serial.begin(115200);
  dht.begin();

  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_BUZZER, LOW);
}

int leerAdcLDR() {
  return analogRead(PIN_LDR);
}

float leerLux(int adcLDR) {
  float lux = map(
    adcLDR,
    ADC_OSCURO,
    ADC_BRILLANTE,
    (long)LUX_OSCURO,
    (long)LUX_BRILLANTE
  );

  if (lux < LUX_OSCURO) lux = LUX_OSCURO;
  if (lux > LUX_BRILLANTE) lux = LUX_BRILLANTE;
  return lux;
}

float leerCO2() {
  int adc = analogRead(PIN_MQ135);
  float voltaje = adc * (5.0 / 1023.0);

  // Conversión aproximada para la demostración.
  // Para medición calibrada se necesita la curva del sensor y R0.
  return (voltaje / 5.0) * 2000.0;
}

float leerTemperaturaPotenciometro() {
  int adc = analogRead(PIN_POT);
  return TEMP_MIN + (adc / 1023.0) * (TEMP_MAX - TEMP_MIN);
}

void actualizarDHT11() {
  float temperatura = dht.readTemperature();
  float humedad = dht.readHumidity();

  if (!isnan(temperatura) && !isnan(humedad)) {
    ultimaTempCuarto1 = temperatura;
    ultimaHumedadCuarto1 = humedad;
  }
}

void actualizarAlarmaLocal(int adcLDR) {
  bool oscuro = adcLDR > UMBRAL_OSCURIDAD_ADC;
  digitalWrite(PIN_LED, oscuro ? HIGH : LOW);
  digitalWrite(PIN_BUZZER, oscuro ? HIGH : LOW);
}

void imprimirNumeroONull(float valor) {
  if (isnan(valor)) {
    Serial.print("null");
  } else {
    Serial.print(valor, 1);
  }
}

void loop() {
  int adcLDR = leerAdcLDR();
  actualizarAlarmaLocal(adcLDR);

  unsigned long ahora = millis();
  if (ahora - ultimoEnvio >= INTERVALO_ENVIO) {
    ultimoEnvio = ahora;

    actualizarDHT11();

    float lux = leerLux(adcLDR);
    float co2 = leerCO2();
    float tempCuarto2 = leerTemperaturaPotenciometro();

    Serial.print("{");
    Serial.print("\"lux\":");
    Serial.print(lux, 1);
    Serial.print(",");

    Serial.print("\"temp_cuarto1\":");
    imprimirNumeroONull(ultimaTempCuarto1);
    Serial.print(",");

    Serial.print("\"humedad_cuarto1\":");
    imprimirNumeroONull(ultimaHumedadCuarto1);
    Serial.print(",");

    Serial.print("\"co2_ppm\":");
    Serial.print(co2, 1);
    Serial.print(",");

    Serial.print("\"temp_cuarto2\":");
    Serial.print(tempCuarto2, 1);
    Serial.println("}");
  }
}
