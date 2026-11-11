// SPDX-License-Identifier: AGPL-3.0-only
// Diagnostico isolado #1: mostra em loop se o VL53L5CX responde no I2C.
// Nao e firmware de uso vestivel; sem medicao, camera, nuvem ou alerta tatil.
#include <Arduino.h>
#include <Wire.h>

constexpr int SDA_PIN = 41, SCL_PIN = 42, LPN_PIN = 40;
constexpr uint8_t TOF_ADDR = 0x29;
constexpr uint32_t I2C_HZ = 100000; // Ensaio isolado, nao perfil operacional.
constexpr uint32_t PERIOD_MS = 1000;
constexpr unsigned SCAN_EVERY = 10; // Varredura completa a cada 10 testes.

int lastState = -1;
uint32_t checks = 0, acks = 0;

unsigned scanBus() {
  unsigned found = 0;
  for (uint8_t addr = 0x08; addr < 0x78; ++addr) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  SCAN ACK 0x%02X\n", addr);
      ++found;
    }
  }
  return found;
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.printf("\nTOF_PRESENCE_LOOP SDA=%d SCL=%d LPn=%d addr=0x%02X I2C=%lu\n",
                SDA_PIN, SCL_PIN, LPN_PIN, TOF_ADDR, (unsigned long)I2C_HZ);
  pinMode(LPN_PIN, OUTPUT);
  digitalWrite(LPN_PIN, HIGH);
  delay(100);
  if (!Wire.begin(SDA_PIN, SCL_PIN, I2C_HZ)) {
    Serial.println("STOP Wire.begin failed");
    while (true) delay(1000);
  }
  Wire.setTimeOut(100);
}

void loop() {
  ++checks;
  Wire.beginTransmission(TOF_ADDR);
  uint8_t code = Wire.endTransmission();
  int state = (code == 0) ? 1 : 0;
  if (state) ++acks;

  if (state != lastState && lastState != -1) {
    Serial.printf(">>> MUDOU: %s\n", state ? "CONECTOU" : "DESCONECTOU");
  }
  lastState = state;

  Serial.printf("[%lu] ToF 0x%02X: %s (codigo=%u) acks=%lu/%lu\n",
                (unsigned long)checks, TOF_ADDR,
                state ? "CONECTADO" : "DESCONECTADO", unsigned(code),
                (unsigned long)acks, (unsigned long)checks);

  if (checks % SCAN_EVERY == 0) {
    Serial.println("  SCAN inicio");
    Serial.printf("  SCAN dispositivos=%u\n", scanBus());
  }
  delay(PERIOD_MS);
}
