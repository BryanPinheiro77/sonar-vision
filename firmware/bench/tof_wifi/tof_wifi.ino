// SPDX-License-Identifier: AGPL-3.0-only
// Bancada isolada #1: VL53L5CX -> Wi-Fi -> AWS (/v1/demo/tof, contrato demo-tof-1).
// Nao e firmware de uso vestivel: sem alerta tatil, camera ou audio. A leitura
// local continua no serial mesmo sem rede; nenhuma resposta da nuvem e usada.
#include <Arduino.h>
#include <Wire.h>
#include <SparkFun_VL53L5CX_Library.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include <esp_timer.h>
#include "wifi_config.h"
#include "credentials_private.h"

constexpr int SDA_PIN = 41, SCL_PIN = 42, LPN_PIN = 40;
constexpr uint32_t I2C_HZ = 400000;
constexpr uint8_t RANGING_HZ = 2;
static const char HOST[] = "sonar-vision.bryandev.com.br";
static const char ENDPOINT[] = "https://sonar-vision.bryandev.com.br/v1/demo/tof";
// Deve ser igual a SONAR_DEMO_SESSION_ID do deploy; caso contrario HTTP 409.
static const char SESSION_ID[] = "camera-20261109-reconnect3";

SparkFun_VL53L5CX sensor;
VL53L5CX_ResultsData results;
bool sensorReady = false, clockReady = false;
uint32_t sequence = 0, lastWifiAttempt = 0;

struct Reading { bool valid; int distance_mm; const char *quality; uint64_t captured_ms; };

// Menor distancia entre zonas com status 5 (valido); 6/9 so como "degraded".
Reading summarize(uint64_t captured_ms) {
  int good = -1, degraded = -1;
  for (int i = 0; i < 64; ++i) {
    if (results.nb_target_detected[i] == 0) continue;
    const int d = results.distance_mm[i];
    const uint8_t s = results.target_status[i];
    if (d < 0) continue;
    if (s == 5 && (good < 0 || d < good)) good = d;
    if ((s == 6 || s == 9) && (degraded < 0 || d < degraded)) degraded = d;
  }
  if (good >= 0) return {true, good, "good", captured_ms};
  if (degraded >= 0) return {true, degraded, "degraded", captured_ms};
  return {false, 0, "invalid", captured_ms};
}

bool initSensor() {
  pinMode(LPN_PIN, OUTPUT);
  digitalWrite(LPN_PIN, HIGH);
  delay(100);
  Wire.begin(SDA_PIN, SCL_PIN, I2C_HZ);
  Wire.setTimeOut(100);
  Wire.beginTransmission(0x29);
  if (Wire.endTransmission() != 0) {
    Serial.println("TOF sem ACK em 0x29; confira fios com tudo desligado e RESET");
    return false;
  }
  Serial.println("TOF inicializando (pode levar ~10 s)");
  if (!sensor.begin(0x29, Wire) || !sensor.setResolution(64) ||
      !sensor.setRangingFrequency(RANGING_HZ) || !sensor.startRanging()) {
    Serial.printf("TOF falhou code=%u\n", unsigned(sensor.lastError.lastErrorCode));
    return false;
  }
  Serial.printf("TOF pronto 8x8 a %u Hz\n", RANGING_HZ);
  return true;
}

void maintainWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!clockReady) {
      configTime(0, 0, "pool.ntp.org", "time.google.com");
      const uint32_t start = millis();
      while (time(nullptr) < 1790000000 && millis() - start < 10000) delay(200);
      clockReady = time(nullptr) >= 1790000000;
      Serial.println(clockReady ? "NTP ok; envio TLS liberado" : "NTP sem hora; envio bloqueado");
    }
    return;
  }
  if (lastWifiAttempt == 0 || millis() - lastWifiAttempt >= 15000) {
    lastWifiAttempt = millis();
    Serial.println("WIFI conectando; senha omitida");
    WiFi.disconnect(false, false);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}

int send(const Reading &r) {
  WiFiClientSecure tls;
  tls.setCACert(ROOT_CA);
  tls.setHandshakeTimeout(3);
  tls.setTimeout(2000);
  if (!tls.connect(HOST, 443, 3000)) return -2;
  char body[320];
  char distance[16];
  if (r.valid) snprintf(distance, sizeof distance, "%d", r.distance_mm);
  else snprintf(distance, sizeof distance, "null");
  snprintf(body, sizeof body,
           "{\"version\":\"demo-tof-1\",\"session_id\":\"%s\",\"sequence\":\"%lu\","
           "\"captured_at_ms\":%llu,\"distance_mm\":%s,\"valid\":%s,\"quality\":\"%s\","
           "\"sector\":\"all\",\"zone\":null,\"aggregation\":\"min_valid_8x8\"}",
           SESSION_ID, (unsigned long)++sequence, (unsigned long long)r.captured_ms,
           distance, r.valid ? "true" : "false", r.quality);
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2000);
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  int status = -1;
  if (http.begin(tls, ENDPOINT)) {
    http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
    http.addHeader("Content-Type", "application/json");
    status = http.POST(reinterpret_cast<uint8_t *>(body), strlen(body));
  }
  http.end();
  tls.stop();
  return status;
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(1);
  delay(2000);
  Serial.println("\nTOF_WIFI bancada #1; sem alerta tatil, camera ou audio");
  sensorReady = initSensor();
  if (!strcmp(WIFI_SSID, "PREENCHA_NOME_DA_REDE")) {
    Serial.println("CONFIGURE wifi_config.h; seguindo so com leitura local");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  maintainWifi();
}

void loop() {
  if (strcmp(WIFI_SSID, "PREENCHA_NOME_DA_REDE")) maintainWifi();
  if (!sensorReady || !sensor.isDataReady()) { delay(5); return; }
  if (!sensor.getRangingData(&results)) { Serial.println("TOF get_data falhou"); return; }
  const Reading r = summarize(esp_timer_get_time() / 1000);
  if (r.valid) Serial.printf("TOF min=%d mm (%s)", r.distance_mm, r.quality);
  else Serial.print("TOF sem zona valida");

  if (WiFi.status() != WL_CONNECTED || !clockReady) { Serial.println(" | nuvem: offline"); return; }
  const uint32_t start = millis();
  const int status = send(r);
  // 204 confirma transporte, nao seguranca; leitura vencida nao e reenviada.
  Serial.printf(" | nuvem: HTTP %d seq=%lu %lums\n", status, (unsigned long)sequence,
                (unsigned long)(millis() - start));
}
