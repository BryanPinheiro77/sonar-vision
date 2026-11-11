// SPDX-License-Identifier: AGPL-3.0-only
// Diagnostico isolado #1: alterna SDA/SCL para medir com multimetro no modulo.
// Nao e firmware de uso vestivel; sem I2C, camera, nuvem ou alerta tatil.
#include <Arduino.h>

constexpr int SDA_PIN = 41, SCL_PIN = 42, LPN_PIN = 40;
constexpr uint32_t HOLD_MS = 5000;

struct Phase { const char *name; int sda; int scl; };
constexpr Phase PHASES[] = {
  {"A SDA=ALTO  SCL=BAIXO", HIGH, LOW},
  {"B SDA=BAIXO SCL=ALTO ", LOW, HIGH},
  {"C SDA=BAIXO SCL=BAIXO", LOW, LOW},
};

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.printf("\nTOF_PIN_TOGGLE SDA=%d SCL=%d LPn=%d hold_ms=%lu\n",
                SDA_PIN, SCL_PIN, LPN_PIN, (unsigned long)HOLD_MS);
  pinMode(LPN_PIN, OUTPUT);
  digitalWrite(LPN_PIN, HIGH);
  pinMode(SDA_PIN, OUTPUT);
  pinMode(SCL_PIN, OUTPUT);
}

void loop() {
  static unsigned cycle = 0;
  ++cycle;
  for (const Phase &p : PHASES) {
    digitalWrite(SDA_PIN, p.sda);
    digitalWrite(SCL_PIN, p.scl);
    Serial.printf("CICLO %u FASE %s (%lus)\n", cycle, p.name,
                  (unsigned long)(HOLD_MS / 1000));
    delay(HOLD_MS);
  }
}
