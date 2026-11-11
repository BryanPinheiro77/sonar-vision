// SPDX-License-Identifier: AGPL-3.0-only
// Isolated #17 camera-to-AWS bench. No tactile loop, ToF, or audio playback.
// Same validated WROOM CAM GPIOs as docs/camera-usb.md. No external pin changes.
#include <Arduino.h>
#include "esp_camera.h"
#include "img_converters.h"
#include "esp_heap_caps.h"
#include "driver/gpio.h"

struct JpegSink { uint8_t *data; size_t length; bool overflow; };
static constexpr size_t jpeg_capacity = 512 * 1024;
static size_t collect_jpeg(void *context, size_t index, const void *data, size_t length) {
  JpegSink *sink = static_cast<JpegSink *>(context);
  if (!data || !length) return 0;
  if (index > jpeg_capacity || length > jpeg_capacity - index) {
    sink->overflow = true; return 0;
  }
  memcpy(sink->data + index, data, length);
  sink->length = index + length;
  return length;
}
static bool jpeg_complete(const uint8_t *data, size_t size) {
  return data && size >= 4 && data[0] == 0xff && data[1] == 0xd8
         && data[size-2] == 0xff && data[size-1] == 0xd9;
}
static bool encode_frame(camera_fb_t *frame, unsigned quality, uint8_t **data, size_t *length) {
  // Preserve the validated small-frame path. frame2jpg has a fixed 128 KiB
  // output in this driver; large frames use its callback API with bounded PSRAM.
  if (frame->width <= 800) {
    if (frame2jpg(frame, quality, data, length) && jpeg_complete(*data, *length)) return true;
    free(*data); *data = nullptr; *length = 0;
  }
  JpegSink sink = {static_cast<uint8_t *>(heap_caps_malloc(jpeg_capacity,
      MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)), 0, false};
  if (!sink.data) return false;
  bool ok = frame2jpg_cb(frame, quality, collect_jpeg, &sink);
  if (!ok || sink.overflow || !jpeg_complete(sink.data, sink.length)) {
    free(sink.data); return false;
  }
  *data = sink.data; *length = sink.length; return true;
}

struct Resolution { framesize_t mode; unsigned width; unsigned height; };
static const Resolution resolutions[] = {
  {FRAMESIZE_QVGA, 320, 240}, {FRAMESIZE_VGA, 640, 480},
  {FRAMESIZE_SVGA, 800, 600}, {FRAMESIZE_XGA, 1024, 768},
  {FRAMESIZE_UXGA, 1600, 1200}
};
static esp_err_t camera_error = ESP_FAIL;
static bool initialized = false, mirror_image = false, flip_image = false;
static unsigned selected = 0, jpeg_quality = 80, tx_buffer_bytes = 256;
static unsigned requested_buffers = 2;
static bool rgb565_big_endian = true, colorbar_enabled = false;

static esp_err_t configure_camera(unsigned index) {
  if (initialized) { esp_camera_deinit(); initialized = false; }
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = 11; c.pin_d1 = 9; c.pin_d2 = 8; c.pin_d3 = 10;
  c.pin_d4 = 12; c.pin_d5 = 18; c.pin_d6 = 17; c.pin_d7 = 16;
  c.pin_xclk = 15; c.pin_pclk = 13; c.pin_vsync = 6; c.pin_href = 7;
  c.pin_sccb_sda = 4; c.pin_sccb_scl = 5; c.pin_pwdn = -1; c.pin_reset = -1;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_RGB565;
  c.frame_size = resolutions[index].mode;
  c.jpeg_quality = 12; // Native JPEG setting; software encoder uses jpeg_quality.
  c.fb_count = index <= 2 ? requested_buffers : 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = c.fb_count > 1 ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;
  camera_error = psramFound() ? esp_camera_init(&c) : ESP_ERR_NO_MEM;
  if (camera_error == ESP_OK) {
    initialized = true; selected = index;
    sensor_t *sensor = esp_camera_sensor_get();
    sensor->set_hmirror(sensor, mirror_image);
    sensor->set_vflip(sensor, flip_image);
    sensor->set_colorbar(sensor, colorbar_enabled);
    delay(150);
  }
  return camera_error;
}


#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <time.h>
#include <esp_timer.h>
#include "wifi_config.h"
#include "credentials_private.h"

static const char ENDPOINT[] = "https://sonar-vision.bryandev.com.br/v1/inference";
static uint32_t frame_id = 0;
static const char SESSION_ID[] = "camera-20261109-reconnect3";

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(1);
  delay(2000);
  Serial.println("CAMERA_WIFI_AWS bancada #17; sem ToF ou alerta tatil");
  if (!strcmp(WIFI_SSID, "PREENCHA_NOME_DA_REDE")) {
    Serial.println("CONFIGURE wifi_config.h antes de gravar; nenhuma imagem enviada");
    return;
  }
  WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
    if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED)
      Serial.printf("WIFI desconectou reason=%u\n", unsigned(info.wifi_sta_disconnected.reason));
    if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) Serial.println("WIFI IP obtido");
  });
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false); // Bench: prioritize uplink latency over power saving.
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.println("WIFI conectando ao hotspot 2,4 GHz; senha omitida");
  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 30000) delay(200);
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WIFI timeout; confira rede/senha/compatibilidade e RESET");
    return;
  }
  initialize_capture();
}

void initialize_capture() {
  Serial.println("WIFI conectado; sincronizando relogio para TLS");
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  const uint32_t clock_start = millis();
  while (time(nullptr) < 1790000000 && millis() - clock_start < 20000) delay(200);
  if (time(nullptr) < 1790000000) {
    Serial.println("NTP sem hora valida; envio TLS bloqueado, pressione RESET apos conferir internet");
    return;
  }
  // Preserve RGB565 -> software JPEG, validated GPIOs, VGA and PSRAM buffers.
  esp_err_t result = configure_camera(0);
  if (result == ESP_OK) {
    result = esp_camera_set_psram_mode(true);
    initialized = result == ESP_OK;
  }
  Serial.printf("CAMERA init=0x%x psram=%u\n", unsigned(result), unsigned(psramFound()));
  if (result == ESP_OK) Serial.println("PRONTO: JPEGs reais para AWS, um pedido por vez; nenhuma fila");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    static uint32_t last_attempt = 0;
    if (last_attempt == 0 || millis() - last_attempt >= 15000) {
      last_attempt = millis();
      Serial.printf("WIFI offline status=%u; nova tentativa ao hotspot\n", unsigned(WiFi.status()));
      WiFi.disconnect(false, false);
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
    delay(200); return;
  }
  if (!initialized) {
    initialize_capture();
    if (!initialized) delay(3000);
    return;
  }
  WiFiClientSecure tls;
  tls.setCACert(ROOT_CA);
  tls.setHandshakeTimeout(3);
  tls.setTimeout(2000);
  // Establish TLS before acquiring a frame, avoiding handshake aging the capture.
  if (!tls.connect("sonar-vision.bryandev.com.br", 443, 3000)) {
    Serial.println("TLS falhou: confira internet/hora/servidor; verificacao de certificado permanece ativa");
    delay(2000); return;
  }
  camera_fb_t *frame = esp_camera_fb_get();
  if (!frame) { Serial.println("CAMERA captura falhou"); tls.stop(); delay(500); return; }
  const uint64_t captured_ms = uint64_t(frame->timestamp.tv_sec) * 1000 + frame->timestamp.tv_usec / 1000;
  uint8_t *jpeg = nullptr;
  size_t length = 0;
  bool ok = encode_frame(frame, 80, &jpeg, &length);
  esp_camera_fb_return(frame);
  const uint64_t now_ms = esp_timer_get_time() / 1000;
  if (!ok || captured_ms > now_ms || now_ms - captured_ms >= 1000) {
    Serial.println("CAMERA JPEG falhou ou captura vencida; descartada sem reenvio");
    free(jpeg); tls.stop(); delay(200); return;
  }
  const uint32_t current_frame = ++frame_id;
  const String boundary = "SonarCameraBench20261109";
  String prefix = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"metadata\"\r\nContent-Type: application/json\r\n\r\n";
  prefix += "{\"version\":\"0.1\",\"session_id\":\"" + String(SESSION_ID) + "\",\"frame_id\":\"" + String(current_frame);
  prefix += "\",\"captured_at_ms\":" + String((unsigned long long)captured_ms) + "}\r\n";
  prefix += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"camera.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
  const String suffix = "\r\n--" + boundary + "--\r\n";
  const size_t total = prefix.length() + length + suffix.length();
  if (total > 524288) { free(jpeg); tls.stop(); return; }
  uint8_t *body = static_cast<uint8_t *>(heap_caps_malloc(total, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!body) { Serial.println("MEM sem buffer de envio"); free(jpeg); tls.stop(); delay(1000); return; }
  memcpy(body, prefix.c_str(), prefix.length());
  memcpy(body + prefix.length(), jpeg, length);
  memcpy(body + prefix.length() + length, suffix.c_str(), suffix.length());
  free(jpeg);
  HTTPClient http;
  http.setConnectTimeout(2000);
  http.setTimeout(2000);
  http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
  int status = -1;
  const uint32_t sent = millis();
  if (http.begin(tls, ENDPOINT)) {
    http.addHeader("Authorization", String("Bearer ") + DEVICE_TOKEN);
    http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
    status = http.POST(body, total);
  }
  const uint64_t age = uint64_t(esp_timer_get_time() / 1000) - captured_ms;
  Serial.printf("FRAME=%lu jpeg=%u HTTP=%d envio_ms=%lu idade_ms=%llu %s\n",
    (unsigned long)current_frame, unsigned(length), status, (unsigned long)(millis()-sent),
    (unsigned long long)age, age >= 1000 ? "resposta_vencida_nao_usar_localmente" : "conferir_imagem_no_painel");
  // Transport-only bench: response is never used as audio, motor or risk command.
  // Close without reading an unbounded response; no queue, redirect, retry or upload replay.
  http.end(); tls.stop(); free(body);
  delay(status == 200 ? 700 : 2000);
}
