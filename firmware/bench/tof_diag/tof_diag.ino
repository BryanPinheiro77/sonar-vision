// SPDX-License-Identifier: AGPL-3.0-only
// Diagnostico isolado #1: nao e firmware de uso vestivel.
#include <Wire.h>
#include <SparkFun_VL53L5CX_Library.h>
#include <esp_system.h>
#include <driver/gpio.h>
int rawLevel(int pin) { return gpio_get_level(static_cast<gpio_num_t>(pin)); }

constexpr int SDA_PIN = 41, SCL_PIN = 42, LPN_PIN = 40;
constexpr uint32_t I2C_HZ = 100000; // Ensaio isolado, nao perfil operacional.
SparkFun_VL53L5CX sensor;
VL53L5CX_ResultsData results;
bool running = false;
uint32_t lastFrame = 0, frames = 0;

void errorCallback(SF_VL53L5CX_ERROR_TYPE code, uint32_t value) {
  Serial.printf("LIB_ERROR code=%u value=%lu hex=0x%08lX\n",
                unsigned(code), (unsigned long)value, (unsigned long)value);
}
bool checked(bool ok, const char *stage) {
  Serial.printf("STAGE %s ok=%u code=%u value=%lu\n", stage, ok,
                unsigned(sensor.lastError.lastErrorCode),
                (unsigned long)sensor.lastError.lastErrorValue);
  return ok;
}
void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.printf("\nTOF_DIAG reset_reason=%d SDA=%d SCL=%d LPn=%d I2C=%lu\n",
                int(esp_reset_reason()), SDA_PIN, SCL_PIN, LPN_PIN,
                (unsigned long)I2C_HZ);
  // LPn ligado ao GPIO40, confirmado por Bryan para este teste.
  pinMode(LPN_PIN, OUTPUT);
  digitalWrite(LPN_PIN, HIGH);
  delay(100);
  pinMode(SDA_PIN, INPUT);
  pinMode(SCL_PIN, INPUT);
  Serial.printf("LINES before Wire SDA=%d SCL=%d LPn=%d\n", rawLevel(SDA_PIN), rawLevel(SCL_PIN), rawLevel(LPN_PIN));
  if (!Wire.begin(SDA_PIN, SCL_PIN, I2C_HZ)) {
    Serial.println("STOP Wire.begin failed"); return;
  }
  Wire.setTimeOut(100);
  delay(500);
  Serial.printf("LINES after Wire SDA=%d SCL=%d LPn=%d\n", rawLevel(SDA_PIN), rawLevel(SCL_PIN), rawLevel(LPN_PIN));
  Wire.beginTransmission(0x29);
  uint8_t ack = Wire.endTransmission();
  Serial.printf("ACK address=0x29 result=%u SDA=%d SCL=%d\n", ack, rawLevel(SDA_PIN), rawLevel(SCL_PIN));
  if (ack != 0) {
    unsigned found = 0;
    for (uint8_t addr = 0x08; addr < 0x78; ++addr) {
      Wire.beginTransmission(addr);
      uint8_t code = Wire.endTransmission();
      if (code == 0) { Serial.printf("SCAN ACK 0x%02X\n", addr); ++found; }
      if (code == 5) { Serial.printf("SCAN timeout 0x%02X; abort\n", addr); break; }
    }
    Serial.printf("SCAN devices=%u SDA=%d SCL=%d\n", found, rawLevel(SDA_PIN), rawLevel(SCL_PIN));
    Serial.println("STOP no ACK at 0x29"); return;
  }
  sensor.setErrorCallback(errorCallback);
  Serial.println("STAGE begin: firmware upload; aguardando retorno da biblioteca");
  uint32_t start = millis();
  bool initialized = sensor.begin(0x29, Wire);
  Serial.printf("INIT elapsed_ms=%lu\n", (unsigned long)(millis() - start));
  if (!checked(initialized, "begin")) return;
  if (!checked(sensor.setResolution(64), "resolution_8x8")) return;
  if (!checked(sensor.setRangingFrequency(1), "frequency_1Hz")) return;
  if (!checked(sensor.startRanging(), "start_ranging")) return;
  lastFrame = millis();
  running = true;
  Serial.println("RUN raw zones; sem orientacao E/D ou classificacao de risco");
}
void loop() {
  if (!running) { delay(100); return; }
  if (sensor.isDataReady()) {
    if (!checked(sensor.getRangingData(&results), "get_data")) {
      running = false; return;
    }
    lastFrame = millis();
    Serial.printf("FRAME %lu raw_zone:distance_mm:status:targets\n", (unsigned long)++frames);
    for (unsigned i = 0; i < 64; ++i) {
      Serial.printf("%u:%d:%u:%u%s", i, int(results.distance_mm[i]),
                    unsigned(results.target_status[i]),
                    unsigned(results.nb_target_detected[i]),
                    (i % 8 == 7) ? "\n" : " ");
    }
  }
  if (millis() - lastFrame > 10000) {
    Serial.println("STOP sem frame por 10s; diagnostico, nao limiar de seguranca");
    checked(sensor.stopRanging(), "stop_ranging");
    running = false;
  }
  delay(10);
}
