// SPDX-License-Identifier: AGPL-3.0-only
// Bancada isolada #1/#4/#17: ToF VL53L5CX + TCA9548A + 2x DRV2605L + envio ToF e JPEG.
// Nao e firmware vestivel nem perfil aprovado. Limiar e cadencias abaixo foram
// escolhidos pelo grupo so para este ensaio (11/11/2026); ver README.
// Envio a nuvem roda em tarefa propria e nunca bloqueia leitura ou motores.
#include <Arduino.h>
#include <Wire.h>
#include <SparkFun_VL53L5CX_Library.h>
#include <esp_timer.h>
#include <driver/gpio.h>

#if __has_include("wifi_config.h") && __has_include("credentials_private.h")
#define CLOUD_ENABLED 1
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include <Preferences.h>
#include "esp_camera.h"
#include "img_converters.h"
#include "esp_heap_caps.h"
#include "wifi_config.h"
#include "credentials_private.h"
#else
#define CLOUD_ENABLED 0
#endif

// GPIOs do ADR 0028. Ramais dos DRVs conforme montagem informada em 11/11/2026
// (SD1 = esquerdo, SD2 = direito); diverge do ADR 0028 (SD0/SD1), pendente do grupo.
constexpr int SDA_PIN = 41, SCL_PIN = 42, LPN_PIN = 40;
constexpr uint32_t I2C_HZ = 100000; // Unica frequencia validada com medicao do ToF.
constexpr uint8_t TOF_ADDR = 0x29, TCA_ADDR = 0x70, DRV_ADDR = 0x5A;
constexpr uint8_t LEFT_CH = 1, RIGHT_CH = 2;
// Ramal 2 travou o barramento inteiro em 11/11 (DRV direito com mau contato).
// Mantenha false ate consertar a fiacao; selecionar o ramal derruba o ToF.
constexpr bool RIGHT_ENABLED = false;
constexpr uint8_t RANGING_HZ = 2;

// Valores de bancada, nao limiares aprovados.
constexpr int ALERT_MM = 500;          // Vibra somente abaixo de 50 cm.
constexpr int NEAR_MM = 100;           // A partir daqui, cadencia maxima.
constexpr uint32_t PULSE_MS = 80;      // Pulso fixo; forca constante.
constexpr uint32_t SLOW_PERIOD_MS = 800, FAST_PERIOD_MS = 200;
// Padrao: forca constante maxima; cadencia comunica urgencia (docs/firmware-integration.md).
// 'f' liga a forca gradual opcional de bancada (diverge do documento; nao e padrao).
constexpr uint8_t MAX_LEVEL = 0x7F;    // 100% (OD_CLAMP de fabrica, ~3 V).
constexpr uint8_t FAR_LEVEL = 0x59;    // ~70% a 50 cm; abaixo disso o ERM pode nao girar.
constexpr uint32_t STALE_MS = 1000;    // Quadro mais velho que isso para os motores.
constexpr uint32_t TOF_RETRY_MS = 3000;

#if CLOUD_ENABLED
static const char HOST[] = "sonar-vision.bryandev.com.br";
static const char ENDPOINT[] = "https://sonar-vision.bryandev.com.br/v1/demo/tof";
static const char INFERENCE_ENDPOINT[] = "https://sonar-vision.bryandev.com.br/v1/inference";
// Precisa ser igual a SONAR_DEMO_SESSION_ID no servidor (docs/esp-api-guide.md).
static const char SESSION_ID[] = "camera-20261109-reconnect3";
constexpr uint32_t SEND_PERIOD_MS = 1000; // Sugestao de bancada do guia: 1 leitura/s.
// Imagem tem prioridade (o modelo precisa dela); a distancia so entra quando a ultima
// enviada passa deste limite, abaixo do stale_ms=5000 do painel. Sem camera: 1/s.
constexpr uint32_t TOF_WITH_CAMERA_MS = 3500;
#endif

SparkFun_VL53L5CX sensor;
VL53L5CX_ResultsData results;
bool tofReady = false, showGrid = true, alertOn = true, swapSides = false, gradual = false;
uint32_t frames = 0, lastFrameAt = 0, lastTofAttempt = 0;
uint32_t continuousUntil = 0; // Teste manual: motor esquerdo ligado direto.
constexpr uint32_t CONTINUOUS_MAX_MS = 60000;

struct Reading { bool valid; int distance_mm; const char *quality; uint64_t captured_ms; };
#if CLOUD_ENABLED
QueueHandle_t latest;
Preferences counters;
uint32_t savedSeq = 0, savedFrame = 0;
uint64_t timeOffsetMs = 0;
int lastTofHttp = 0, lastImageHttp = 0;
#endif

// ---------- TCA9548A + DRV2605L ----------
struct Motor {
  const char *name;
  uint8_t channel;
  bool ready;
  bool running;
  int distance_mm;      // Menor distancia valida do lado; -1 = nada.
  uint32_t nextPulseAt; // Inicio do proximo pulso.
  uint32_t stopAt;      // Fim do pulso atual.
};
Motor motors[2] = {{"esquerdo", LEFT_CH, false, false, -1, 0, 0},
                   {"direito", RIGHT_CH, false, false, -1, 0, 0}};

bool tcaSelect(uint8_t mask) {
  Wire.beginTransmission(TCA_ADDR);
  Wire.write(mask);
  return Wire.endTransmission() == 0;
}

bool drvWrite(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(DRV_ADDR);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

int drvRead(uint8_t reg) {
  Wire.beginTransmission(DRV_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(DRV_ADDR, (uint8_t)1) != 1) return -1;
  return Wire.read();
}

// Seleciona o ramal, escreve o RTP e desmarca: trocar de ramal nao para o motor.
bool drvSetOutput(Motor &m, uint8_t level) {
  if (!m.ready || !tcaSelect(1 << m.channel)) return false;
  const bool ok = drvWrite(0x02, level);
  tcaSelect(0);
  return ok;
}

bool drvInit(Motor &m) {
  if (!tcaSelect(1 << m.channel)) return false;
  bool ok = false;
  const int status = drvRead(0x00);
  if (status >= 0) {
    const int feedback = drvRead(0x1A);
    // ERM (bit7=0): ADR 0022 trata os motores 1027 como candidatos ERM. Sem modo LRA.
    // Mantem OD_CLAMP/rated voltage de fabrica (~3 V); nao usa maximo do anuncio.
    ok = feedback >= 0 && drvWrite(0x1A, feedback & 0x7F) && drvWrite(0x1D, 0xA0) &&
         drvWrite(0x02, 0x00) && drvWrite(0x01, 0x05); // RTP, saida zero.
  }
  tcaSelect(0);
  Serial.printf("DRV %s (SD%u): %s\n", m.name, m.channel,
                ok ? "pronto (ERM, RTP)" : "nao encontrado");
  return ok;
}

void stopMotor(Motor &m) {
  if (m.running && !drvSetOutput(m, 0x00))
    Serial.printf("DRV %s: FALHA AO PARAR; desligue a alimentacao do motor\n", m.name);
  m.running = false;
  m.stopAt = 0;
}

void stopAll() { for (Motor &m : motors) { stopMotor(m); m.distance_mm = -1; } }

void startPulse(Motor &m, uint32_t ms, uint8_t level = MAX_LEVEL) {
  if (!m.ready) return;
  m.running = drvSetOutput(m, level);
  m.stopAt = millis() + ms;
}

// Mais perto => mais forte (se gradual), de FAR_LEVEL a 50 cm ate MAX_LEVEL em NEAR_MM.
uint8_t levelFor(int mm) {
  if (!gradual || mm <= NEAR_MM) return MAX_LEVEL;
  if (mm >= ALERT_MM) return FAR_LEVEL;
  return MAX_LEVEL - (uint8_t)((uint32_t)(mm - NEAR_MM) * (MAX_LEVEL - FAR_LEVEL) /
                               (ALERT_MM - NEAR_MM));
}

// Mais perto => pulsos mais frequentes. Forca e duracao do pulso nao mudam.
uint32_t periodFor(int mm) {
  if (mm <= NEAR_MM) return FAST_PERIOD_MS;
  return FAST_PERIOD_MS + (uint32_t)(mm - NEAR_MM) * (SLOW_PERIOD_MS - FAST_PERIOD_MS) /
                              (ALERT_MM - NEAR_MM);
}

void updateMotors() {
  const uint32_t now = millis();
  if (continuousUntil) {
    if ((int32_t)(now - continuousUntil) >= 0) {
      continuousUntil = 0; stopMotor(motors[0]); Serial.println("CONTINUO desligado (60 s)");
    }
    return; // Durante o teste manual, o alerta automatico fica suspenso.
  }
  for (Motor &m : motors) {
    if (m.running && (int32_t)(now - m.stopAt) >= 0) stopMotor(m);
    const bool near = alertOn && m.distance_mm >= 0 && m.distance_mm < ALERT_MM;
    if (!near) { m.nextPulseAt = 0; continue; }
    if (!m.running && (m.nextPulseAt == 0 || (int32_t)(now - m.nextPulseAt) >= 0)) {
      startPulse(m, PULSE_MS, levelFor(m.distance_mm));
      m.nextPulseAt = now + periodFor(m.distance_mm);
    }
  }
}

// ---------- I2C ----------
void scanBus() {
  tcaSelect(0);
  Serial.print("I2C principal:");
  for (uint8_t a = 0x08; a < 0x78; ++a) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) Serial.printf(" 0x%02X", a);
  }
  Serial.println();
  for (uint8_t ch = 0; ch < 8; ++ch) {
    if (ch == RIGHT_CH && !RIGHT_ENABLED) { Serial.printf("TCA ramal %u: ignorado (desativado no codigo)\n", ch); continue; }
    if (!tcaSelect(1 << ch)) { Serial.println("TCA 0x70 sem resposta"); return; }
    if (ch == RIGHT_CH) {
      delay(2);
      // 1 = linha livre; 0 = algo no ramal segura a linha em GND e trava o barramento.
      Serial.printf("TCA ramal %u selecionado: SDA=%d SCL=%d\n", ch,
                    gpio_get_level((gpio_num_t)SDA_PIN), gpio_get_level((gpio_num_t)SCL_PIN));
    }
    Wire.beginTransmission(DRV_ADDR);
    if (Wire.endTransmission() == 0) Serial.printf("TCA ramal %u (SD%u/SC%u): DRV 0x5A\n", ch, ch, ch);
  }
  tcaSelect(0);
}

// ---------- ToF ----------
bool tofInit() {
  stopAll(); // Inicializacao bloqueia ~10 s; nenhum motor fica ligado nesse tempo.
  lastTofAttempt = millis();
  pinMode(LPN_PIN, OUTPUT);
  digitalWrite(LPN_PIN, HIGH);
  delay(100);
  tcaSelect(0);
  Wire.beginTransmission(TOF_ADDR);
  if (Wire.endTransmission() != 0) { Serial.println("TOF sem resposta em 0x29"); return false; }
  Serial.println("TOF inicializando (~10 s)...");
  const uint32_t start = millis();
  const char *stage = "begin";
  bool ok = sensor.begin(TOF_ADDR, Wire);
  if (ok) { stage = "resolution"; ok = sensor.setResolution(64); }
  if (ok) { stage = "frequency"; ok = sensor.setRangingFrequency(RANGING_HZ); }
  if (ok) { stage = "start"; ok = sensor.startRanging(); }
  Serial.printf("TOF %s etapa=%s code=%u tempo=%lums\n", ok ? "ok" : "FALHOU", stage,
                unsigned(sensor.lastError.lastErrorCode), (unsigned long)(millis() - start));
  lastFrameAt = millis();
  return ok;
}

// Status 5 = valido; 6 e 9 = parcialmente valido (degraded). Demais descartados.
int zoneQuality(int i) {
  if (results.nb_target_detected[i] == 0 || results.distance_mm[i] < 0) return 0;
  const uint8_t s = results.target_status[i];
  return s == 5 ? 2 : (s == 6 || s == 9) ? 1 : 0;
}

// Metade das colunas para cada lado; orientacao real conferida com a mao ('x' inverte).
void sideDistances() {
  for (Motor &m : motors) m.distance_mm = -1;
  for (int i = 0; i < 64; ++i) {
    if (!zoneQuality(i)) continue;
    const bool leftHalf = (i % 8) < 4;
    Motor &m = motors[(leftHalf != swapSides) ? 0 : 1];
    const int d = results.distance_mm[i];
    if (m.distance_mm < 0 || d < m.distance_mm) m.distance_mm = d;
  }
}

Reading summarize(uint64_t captured_ms, int *validCount) {
  int good = -1, degraded = -1;
  *validCount = 0;
  for (int i = 0; i < 64; ++i) {
    const int q = zoneQuality(i), d = results.distance_mm[i];
    if (q) ++*validCount;
    if (q == 2 && (good < 0 || d < good)) good = d;
    if (q == 1 && (degraded < 0 || d < degraded)) degraded = d;
  }
  if (good >= 0) return {true, good, "good", captured_ms};
  if (degraded >= 0) return {true, degraded, "degraded", captured_ms};
  return {false, 0, "invalid", captured_ms};
}

void printSide(const Motor &m) {
  if (!m.ready) Serial.printf("%s: sem DRV", m.name);
  else if (m.distance_mm < 0) Serial.printf("%s: --", m.name);
  else if (alertOn && m.distance_mm < ALERT_MM)
    Serial.printf("%s: %d cm VIBRANDO %d%%", m.name, (m.distance_mm + 5) / 10,
                  levelFor(m.distance_mm) * 100 / MAX_LEVEL);
  else Serial.printf("%s: %d cm", m.name, (m.distance_mm + 5) / 10);
}

void printFrame(const Reading &r, int validCount) {
  Serial.printf("\n=== quadro %lu | ", (unsigned long)frames);
  if (r.valid) Serial.printf("MAIS PERTO %d cm", (r.distance_mm + 5) / 10);
  else Serial.print("sem leitura valida");
  Serial.print(" | ");
  printSide(motors[0]);
  Serial.print(" | ");
  printSide(motors[1]);
  Serial.printf(" | validas %d/64 ===\n", validCount);
  if (!showGrid) return;
  Serial.println("cm     c0   c1   c2   c3 |  c4   c5   c6   c7");
  for (int row = 0; row < 8; ++row) {
    Serial.printf("l%d ", row);
    for (int col = 0; col < 8; ++col) {
      const int i = row * 8 + col, q = zoneQuality(i);
      if (col == 4) Serial.print(" |");
      if (q) Serial.printf(" %4d%c", (results.distance_mm[i] + 5) / 10, q == 2 ? ' ' : '?');
      else Serial.print("    --");
    }
    Serial.println();
  }
}

// ---------- Nuvem (tarefa separada) ----------
#if CLOUD_ENABLED
int postReading(const Reading &r, uint32_t sequence) {
  WiFiClientSecure tls;
  tls.setCACert(ROOT_CA);
  tls.setHandshakeTimeout(3);
  tls.setTimeout(2000);
  if (!tls.connect(HOST, 443, 3000)) return -2;
  char distance[16], body[320];
  if (r.valid) snprintf(distance, sizeof distance, "%d", r.distance_mm);
  else snprintf(distance, sizeof distance, "null");
  snprintf(body, sizeof body,
           "{\"version\":\"demo-tof-1\",\"session_id\":\"%s\",\"sequence\":\"%lu\","
           "\"captured_at_ms\":%llu,\"distance_mm\":%s,\"valid\":%s,\"quality\":\"%s\","
           "\"sector\":\"all\",\"zone\":null,\"aggregation\":\"min_valid_8x8\"}",
           SESSION_ID, (unsigned long)sequence, (unsigned long long)(r.captured_ms + timeOffsetMs),
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

// ---------- Camera (mesmo caminho validado de firmware/bench/camera_wifi) ----------
// RGB565 -> JPEG 80 no ESP, QVGA, 2 buffers em PSRAM. Bit 5 (GPIO18) segue em
// investigacao (docs/camera-usb.md): imagem nao valida fidelidade de pixels.
bool cameraReady = false;

bool cameraInit() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = 11; c.pin_d1 = 9; c.pin_d2 = 8; c.pin_d3 = 10;
  c.pin_d4 = 12; c.pin_d5 = 18; c.pin_d6 = 17; c.pin_d7 = 16;
  c.pin_xclk = 15; c.pin_pclk = 13; c.pin_vsync = 6; c.pin_href = 7;
  c.pin_sccb_sda = 4; c.pin_sccb_scl = 5; c.pin_pwdn = -1; c.pin_reset = -1;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_RGB565;
  c.frame_size = FRAMESIZE_QVGA;
  c.jpeg_quality = 12;
  c.fb_count = 2;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;
  esp_err_t err = psramFound() ? esp_camera_init(&c) : ESP_ERR_NO_MEM;
  if (err == ESP_OK) err = esp_camera_set_psram_mode(true);
  Serial.printf("CAMERA init=0x%x (QVGA, RGB565->JPEG80)\n", unsigned(err));
  return err == ESP_OK;
}

int postImage(uint32_t frameId) {
  WiFiClientSecure tls;
  tls.setCACert(ROOT_CA);
  tls.setHandshakeTimeout(3);
  tls.setTimeout(2000);
  // Conecta antes de capturar, para o handshake nao envelhecer a imagem.
  if (!tls.connect(HOST, 443, 3000)) return -2;
  camera_fb_t *frame = esp_camera_fb_get();
  if (!frame) return -3;
  const uint64_t captured_ms = uint64_t(frame->timestamp.tv_sec) * 1000 + frame->timestamp.tv_usec / 1000;
  uint8_t *jpeg = nullptr;
  size_t length = 0;
  const bool ok = frame2jpg(frame, 80, &jpeg, &length) && length >= 4 &&
                  jpeg[0] == 0xff && jpeg[1] == 0xd8 && jpeg[length - 2] == 0xff && jpeg[length - 1] == 0xd9;
  esp_camera_fb_return(frame);
  const uint64_t now_ms = esp_timer_get_time() / 1000;
  if (!ok || captured_ms > now_ms || now_ms - captured_ms >= 1000) { free(jpeg); return -4; }
  const String boundary = "SonarBenchTofCam";
  String prefix = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n";
  prefix += "{\"version\":\"0.1\",\"session_id\":\"" + String(SESSION_ID) + "\",\"frame_id\":\"" + String(frameId);
  prefix += "\",\"captured_at_ms\":" + String((unsigned long long)(captured_ms + timeOffsetMs)) + "}\r\n";
  prefix += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"camera.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
  const String suffix = "\r\n--" + boundary + "--\r\n";
  const size_t total = prefix.length() + length + suffix.length();
  uint8_t *body = static_cast<uint8_t *>(heap_caps_malloc(total, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!body) { free(jpeg); return -5; }
  memcpy(body, prefix.c_str(), prefix.length());
  memcpy(body + prefix.length(), jpeg, length);
  memcpy(body + prefix.length() + length, suffix.c_str(), suffix.length());
  free(jpeg);
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2000);
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  int status = -1;
  if (http.begin(tls, INFERENCE_ENDPOINT)) {
    http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
    http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
    status = http.POST(body, total);
  }
  // Resposta nunca vira comando de motor ou audio; nao le corpo, sem fila/reenvio.
  http.end();
  tls.stop();
  free(body);
  return status;
}

// Ajuste de bancada (diverge do guia, que pede contadores desde o boot e sessao nova
// por boot): o painel tem sessao fixa e recusa contadores que regridem (HTTP 409).
// Persistimos sequence/frame_id e um deslocamento de tempo na flash, com folga, para
// que sigam crescendo apos RESET. captured_at_ms = ms desde o boot + deslocamento.
constexpr uint32_t COUNTER_MARGIN = 1000;        // Saltos por boot (lacunas sao aceitas).
constexpr uint64_t TIME_MARGIN_MS = 3600000ULL;  // 1 h por boot; tempo nunca regride.

void loadCounters() {
  counters.begin("bench", false);
  savedSeq = counters.getUInt("seq", 0) + COUNTER_MARGIN;
  savedFrame = counters.getUInt("frame", 0) + COUNTER_MARGIN;
  timeOffsetMs = counters.getULong64("toff", 0) + TIME_MARGIN_MS;
  // Grava ja o novo ponto de partida: um RESET logo depois tambem avanca.
  counters.putUInt("seq", savedSeq);
  counters.putUInt("frame", savedFrame);
  counters.putULong64("toff", timeOffsetMs + esp_timer_get_time() / 1000);
  Serial.printf("NUVEM: contadores a partir de seq=%lu frame=%lu\n",
                (unsigned long)savedSeq, (unsigned long)savedFrame);
}

void saveCounters(uint32_t seq, uint32_t frame) {
  counters.putUInt("seq", seq);
  counters.putUInt("frame", frame);
  counters.putULong64("toff", timeOffsetMs + esp_timer_get_time() / 1000);
}

void cloudTask(void *) {
  loadCounters();
  uint32_t sequence = savedSeq, lastAttempt = 0, frameId = savedFrame, lastTofSent = 0, sends = 0;
  bool clockReady = false, ntpStarted = false;
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      if (lastAttempt == 0 || millis() - lastAttempt >= 15000) {
        if (lastAttempt) {
          // Mostra redes visiveis (so 2,4 GHz aparecem no ESP32) e se a configurada esta entre elas.
          Serial.printf("NUVEM: falhou status=%d; redes visiveis:\n", int(WiFi.status()));
          const int n = WiFi.scanNetworks();
          for (int i = 0; i < n && i < 12; ++i)
            Serial.printf("  '%s' sinal=%d canal=%d%s\n", WiFi.SSID(i).c_str(), WiFi.RSSI(i),
                          WiFi.channel(i), WiFi.SSID(i) == WIFI_SSID ? "  <= configurada" : "");
          WiFi.scanDelete();
        }
        lastAttempt = millis();
        Serial.printf("NUVEM: conectando a '%s' (senha omitida)\n", WIFI_SSID);
        WiFi.disconnect(false, false);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      }
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }
    if (!clockReady) {
      if (!ntpStarted) { configTime(0, 0, "pool.ntp.org", "time.google.com"); ntpStarted = true; }
      clockReady = time(nullptr) >= 1790000000;
      if (clockReady) Serial.println("NUVEM: Wi-Fi e hora ok; enviando imagem e distancia");
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }
    // Um pedido por vez. Prioridade da imagem; distancia so quando a ultima enviada
    // envelhece (ver TOF_WITH_CAMERA_MS).
    Reading r;
    const uint32_t tofPeriod = cameraReady ? TOF_WITH_CAMERA_MS : SEND_PERIOD_MS;
    if (millis() - lastTofSent >= tofPeriod && xQueueReceive(latest, &r, 0) == pdTRUE) {
      const uint64_t now = esp_timer_get_time() / 1000;
      ++sequence; // Lacunas sao aceitas; leitura velha nao e reenviada.
      if (now - r.captured_ms >= 1000) continue;
      lastTofSent = millis();
      const int status = postReading(r, sequence);
      lastTofHttp = status;
      if (++sends % 10 == 0) saveCounters(sequence, frameId);
      Serial.printf("NUVEM: distancia HTTP %d seq=%lu %lums%s\n", status, (unsigned long)sequence,
                    (unsigned long)(millis() - lastTofSent),
                    status == 409 ? " (sessao/ordem: confira SESSION_ID com cloud)" : "");
    } else if (cameraReady) {
      const uint32_t start = millis();
      const int status = postImage(++frameId);
      lastImageHttp = status;
      if (++sends % 10 == 0) saveCounters(sequence, frameId);
      Serial.printf("NUVEM: imagem HTTP %d frame=%lu %lums%s\n", status, (unsigned long)frameId,
                    (unsigned long)(millis() - start),
                    status == -4 ? " (captura vencida/JPEG falhou)" : "");
      if (status != 200) vTaskDelay(pdMS_TO_TICKS(500));
    } else {
      vTaskDelay(pdMS_TO_TICKS(100));
    }
  }
}
#endif

// ---------- Programa ----------
void help() {
  Serial.printf("Alerta abaixo de %d cm: mais perto = pulsos mais rapidos (forca constante).\n", ALERT_MM / 10);
  Serial.println("Comandos: a=liga/desliga alerta | x=inverte esquerda/direita | "
                 "e=testa esquerdo | r=testa direito | c=esquerdo continuo | k=diag DRV | f=forca gradual/constante | g=tabela | s=scan | t=reinicia ToF | "
                 "d=status | ?=ajuda");
}

void setup() {
  Serial.begin(115200);
  const uint32_t waitStart = millis();
  while (!Serial && millis() - waitStart < 15000) delay(50); // Nao perder mensagens do boot.
  delay(500);
  Serial.printf("\nBENCH_TOF_DRV | nuvem %s | alerta de bancada < %d cm\n",
                CLOUD_ENABLED ? "habilitada" : "desligada (sem credenciais)", ALERT_MM / 10);
  Wire.begin(SDA_PIN, SCL_PIN, I2C_HZ);
  Wire.setTimeOut(100);
  scanBus();
  motors[0].ready = drvInit(motors[0]);
  if (RIGHT_ENABLED) motors[1].ready = drvInit(motors[1]);
  else Serial.println("DRV direito (SD2): desativado ate consertar a fiacao");
  tofReady = tofInit();
#if CLOUD_ENABLED
  cameraReady = cameraInit();
  latest = xQueueCreate(1, sizeof(Reading));
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  xTaskCreatePinnedToCore(cloudTask, "cloud", 8192, nullptr, 1, nullptr, 0);
#endif
  help();
  // Depois do boot, saida serial nunca bloqueia o laco dos motores (sem leitor = descarta).
  Serial.setTxTimeoutMs(0);
}

// Liga a saida do DRV esquerdo por 500 ms e mostra os registradores relevantes.
void drvDiag(Motor &m) {
  if (!m.ready) { Serial.printf("DRV %s indisponivel\n", m.name); return; }
  auto dump = [&](const char *when) {
    tcaSelect(1 << m.channel);
    const int st = drvRead(0x00), mode = drvRead(0x01), rtp = drvRead(0x02);
    const int fb = drvRead(0x1A), c3 = drvRead(0x1D), od = drvRead(0x17), go = drvRead(0x0C);
    tcaSelect(0);
    Serial.printf("DRV %s %s: status=0x%02X (OC=%d OT=%d) mode=0x%02X (standby=%d) rtp=0x%02X "
                  "feedback=0x%02X (LRA=%d) ctrl3=0x%02X od_clamp=0x%02X go=0x%02X\n",
                  m.name, when, st, st & 1, (st >> 1) & 1, mode, (mode >> 6) & 1, rtp, fb,
                  (fb >> 7) & 1, c3, od, go);
  };
  dump("parado");
  drvSetOutput(m, 0x7F);
  m.running = true;
  delay(200);
  dump("ligado");
  delay(300);
  stopMotor(m);
  dump("depois");
}

void handleCommand(char c) {
  if (c == 'a') { alertOn = !alertOn; if (!alertOn) stopAll(); Serial.printf("Alerta %s\n", alertOn ? "LIGADO" : "DESLIGADO"); }
  else if (c == 'x') { swapSides = !swapSides; stopAll(); Serial.printf("Lados %s\n", swapSides ? "INVERTIDOS" : "normais"); }
  else if (c == 'e') { startPulse(motors[0], 300); Serial.println("Teste motor esquerdo 300 ms"); }
  else if (c == 'r') { startPulse(motors[1], 300); Serial.println("Teste motor direito 300 ms"); }
  else if (c == 'k') drvDiag(motors[0]);
  else if (c == 'f') { gradual = !gradual; Serial.printf("Forca %s\n", gradual ? "GRADUAL (70%->100%)" : "CONSTANTE 100%"); }
  else if (c == 'c') {
    if (continuousUntil) { continuousUntil = 0; stopMotor(motors[0]); Serial.println("CONTINUO desligado"); }
    else if (motors[0].ready) {
      motors[0].running = drvSetOutput(motors[0], 0x7F);
      continuousUntil = millis() + CONTINUOUS_MAX_MS;
      Serial.printf("CONTINUO ligado no esquerdo (comando=%s); 'c' desliga, maximo 60 s\n",
                    motors[0].running ? "ok" : "FALHOU");
    }
  }
  else if (c == 'g') { showGrid = !showGrid; }
  else if (c == 's') scanBus();
  else if (c == 't') { if (tofReady) sensor.stopRanging(); tofReady = tofInit(); }
  else if (c == 'd') {
    Serial.printf("STATUS tof=%u esq=%u dir=%u quadros=%lu alerta=%u lados=%s forca=%s\n",
                  tofReady, motors[0].ready, motors[1].ready, (unsigned long)frames,
                  alertOn, swapSides ? "invertidos" : "normais", gradual ? "gradual" : "constante");
#if CLOUD_ENABLED
    Serial.printf("STATUS camera=%u wifi=%d http_distancia=%d http_imagem=%d\n",
                  cameraReady, int(WiFi.status()), lastTofHttp, lastImageHttp);
#endif
  }
  else if (c == '?') help();
}

void loop() {
  while (Serial.available()) handleCommand(Serial.read());

  // Sem quadro recente: para os motores e tenta recuperar o ToF.
  if (!continuousUntil && millis() - lastFrameAt > STALE_MS &&
      (motors[0].distance_mm >= 0 || motors[1].distance_mm >= 0)) {
    stopAll();
    Serial.println("TOF sem quadro recente: motores parados");
  }
  // Durante o teste manual continuo, nao reinicia o ToF (tofInit para todos os motores).
  if (!continuousUntil && millis() - lastFrameAt > TOF_RETRY_MS &&
      millis() - lastTofAttempt > TOF_RETRY_MS) {
    Serial.println("TOF parado; tentando reiniciar");
    if (tofReady) sensor.stopRanging();
    tofReady = tofInit();
  }

  if (tofReady && sensor.isDataReady()) {
    if (sensor.getRangingData(&results)) {
      ++frames;
      lastFrameAt = millis();
      sideDistances();
      int validCount;
      const Reading r = summarize(esp_timer_get_time() / 1000, &validCount);
      printFrame(r, validCount);
#if CLOUD_ENABLED
      xQueueOverwrite(latest, &r);
#endif
    } else {
      Serial.println("TOF leitura falhou");
    }
  }
#if CLOUD_ENABLED
  // Sem quadro recente: publica leitura invalida (valid=false) 1x/s, como pede o guia;
  // nunca zero ou caminho livre.
  static uint32_t lastInvalidAt = 0;
  if (millis() - lastFrameAt > STALE_MS && millis() - lastInvalidAt >= SEND_PERIOD_MS) {
    lastInvalidAt = millis();
    const Reading invalid = {false, 0, "invalid", (uint64_t)(esp_timer_get_time() / 1000)};
    xQueueOverwrite(latest, &invalid);
  }
#endif
  updateMotors();
  delay(2);
}
