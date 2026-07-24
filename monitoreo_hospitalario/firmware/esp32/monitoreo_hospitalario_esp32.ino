/*
 * MONITOREO AMBIENTAL HOSPITALARIO - Firmware ESP32
 * ---------------------------------------------------
 * Lee: LDR (luz), DHT11 (temperatura/humedad), MQ-135 (calidad de aire)
 * Controla: Buzzer (alerta sonora), LED (indicador visual)
 * Envía las lecturas por Serial en formato JSON, una línea por lectura,
 * para que servidor_central.py las lea y las distribuya a los clientes.
 *
 * Instituto Tecnologico de Tijuana
 * Por: Nicole Lewis, Farid Garcia
 */

#include <DHT.h>

// ---------- Pines ----------
#define PIN_LDR      34   // Entrada analógica (ADC1)
#define PIN_DHT      15   // Pin digital del DHT11
#define PIN_MQ135    35   // Entrada analógica (ADC1)
#define PIN_BUZZER   25   // Salida digital
#define PIN_LED      2    // LED integrado / indicador

#define DHTTYPE DHT11
DHT dht(PIN_DHT, DHTTYPE);

// ---------- Calibración LDR (ajustar según su sensor) ----------
const int   ADC_OSCURO     = 4095;   // Lectura ADC en oscuridad total
const int   ADC_BRILLANTE  = 200;    // Lectura ADC con luz directa
const float LUX_OSCURO     = 0.0;
const float LUX_BRILLANTE  = 1000.0;

// ---------- Calibración MQ-135 ----------
// Valor de referencia en aire limpio (ajustar tras precalentar el sensor 24-48h)
const float MQ135_RZERO = 76.63;

// ---------- Umbrales de alerta ----------
const float TEMP_MAX_C   = 28.0;   // Buzzer si temp > 28°C
const float HUMEDAD_MAX  = 70.0;   // Alerta de humedad alta (%)
const int   CO2_MAX_PPM  = 1000;   // Alerta de calidad de aire

// ---------- Estado ----------
bool modoAutomatico = true;   // true = ESP32 decide el buzzer; false = control manual desde un cliente
bool buzzerManual    = false;
unsigned long ultimaLectura = 0;
const unsigned long INTERVALO_LECTURA = 2000; // ms

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  dht.begin();
  digitalWrite(PIN_BUZZER, LOW);
  digitalWrite(PIN_LED, LOW);
}

float leerLux() {
  int adc = analogRead(PIN_LDR);
  float lux = map(adc, ADC_OSCURO, ADC_BRILLANTE, LUX_OSCURO, LUX_BRILLANTE);
  if (lux < 0) lux = 0;
  return lux;
}

float leerPPM_MQ135() {
  int adc = analogRead(PIN_MQ135);
  float voltaje = adc * (3.3 / 4095.0);
  // Conversión simplificada; para valores de precisión de laboratorio
  // se recomienda usar la curva logarítmica del datasheet del MQ-135.
  float ppm = (voltaje / 3.3) * 2000.0;
  return ppm;
}

void evaluarAlertas(float temp, float humedad, float ppm) {
  bool umbralCritico = (temp > TEMP_MAX_C) || (humedad > HUMEDAD_MAX) || (ppm > CO2_MAX_PPM);

  bool activarBuzzer;
  if (modoAutomatico) {
    activarBuzzer = umbralCritico;
  } else {
    activarBuzzer = buzzerManual;
  }

  digitalWrite(PIN_BUZZER, activarBuzzer ? HIGH : LOW);
  digitalWrite(PIN_LED, activarBuzzer ? HIGH : LOW);
}

void leerComandosSerial() {
  // Permite que el servidor central envíe comandos, ej:
  //   {"cmd":"buzzer_on"}  {"cmd":"buzzer_off"}  {"cmd":"modo_auto"}
  if (Serial.available()) {
    String linea = Serial.readStringUntil('\n');
    linea.trim();
    if (linea == "{\"cmd\":\"buzzer_on\"}") {
      modoAutomatico = false;
      buzzerManual = true;
    } else if (linea == "{\"cmd\":\"buzzer_off\"}") {
      modoAutomatico = false;
      buzzerManual = false;
    } else if (linea == "{\"cmd\":\"modo_auto\"}") {
      modoAutomatico = true;
    }
  }
}

void loop() {
  leerComandosSerial();

  unsigned long ahora = millis();
  if (ahora - ultimaLectura >= INTERVALO_LECTURA) {
    ultimaLectura = ahora;

    float lux     = leerLux();
    float temp    = dht.readTemperature();
    float humedad = dht.readHumidity();
    float ppm     = leerPPM_MQ135();

    if (isnan(temp) || isnan(humedad)) {
      // Lectura fallida del DHT11, se reintenta en el siguiente ciclo
      return;
    }

    evaluarAlertas(temp, humedad, ppm);

    // JSON por línea, leído por servidor_central.py
    Serial.print("{");
    Serial.print("\"lux\":");     Serial.print(lux, 1);     Serial.print(",");
    Serial.print("\"temp\":");    Serial.print(temp, 1);    Serial.print(",");
    Serial.print("\"humedad\":"); Serial.print(humedad, 1); Serial.print(",");
    Serial.print("\"co2_ppm\":"); Serial.print(ppm, 1);     Serial.print(",");
    Serial.print("\"buzzer\":");  Serial.print(digitalRead(PIN_BUZZER) == HIGH ? "true" : "false"); Serial.print(",");
    Serial.print("\"modo_auto\":"); Serial.print(modoAutomatico ? "true" : "false");
    Serial.println("}");
  }
}
