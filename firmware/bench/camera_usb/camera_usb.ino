// SPDX-License-Identifier: AGPL-3.0-only
// Isolated #1/#17 camera bench. No tactile loop, sensors, audio or networking.
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
static unsigned requested_buffers = 1;
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

void setup() {
  Serial.begin(115200);
  Serial.setTxBufferSize(tx_buffer_bytes);
  delay(2000);
  configure_camera(0);
}

void loop() {
  if (!Serial.available()) { delay(1); return; }
  char command = Serial.read();
  if (command == '\r' || command == '\n') return;
  // Reinitialization is accepted even after failure so the host can recover.
  if (command >= '0' && command <= '4') {
    unsigned target = command - '0';
    esp_err_t result = configure_camera(target);
    if (result == ESP_OK) Serial.printf("SVOK width=%u height=%u\n",
        resolutions[target].width, resolutions[target].height);
    else Serial.printf("SVERROR configure=0x%x\n", result);
    return;
  }
  if (command == 'L' || command == 'F') {
    unsigned size = command == 'L' ? 256 : 32768;
    Serial.flush();
    size_t actual = Serial.setTxBufferSize(size);
    if (actual) { tx_buffer_bytes = actual; Serial.printf("SVOK tx_buffer=%u\n", tx_buffer_bytes); }
    else Serial.println("SVERROR tx_buffer_allocation");
    return;
  }
  if (command >= 'a' && command <= 'c') {
    jpeg_quality = command == 'a' ? 60 : command == 'b' ? 80 : 90;
    Serial.printf("SVOK quality=%u\n", jpeg_quality);
    return;
  }
  if (command == 'M' || command == 'N') {
    requested_buffers = command == 'M' ? 2 : 1;
    esp_err_t result = configure_camera(selected);
    if (result == ESP_OK) Serial.printf("SVOK fb_count=%u\n", selected <= 2 ? requested_buffers : 1);
    else Serial.printf("SVERROR configure=0x%x\n", result);
    return;
  }
  if ((command == 'E' || command == 'G') && initialized) {
    camera_error = esp_camera_set_psram_mode(command == 'E');
    initialized = camera_error == ESP_OK;
    if (initialized) Serial.printf("SVOK psram_dma=%u\n", esp_camera_get_psram_mode());
    else Serial.printf("SVERROR psram_dma=0x%x\n", camera_error);
    return;
  }
  if (camera_error != ESP_OK) {
    Serial.printf("SVERROR camera_init=0x%x\n", camera_error); return;
  }
  sensor_t *sensor = esp_camera_sensor_get();
  if (command == 'Z') {
    gpio_io_config_t state = {};
    if (gpio_get_io_config(GPIO_NUM_18, &state) != ESP_OK) {
      Serial.println("SVERROR gpio_config_query"); return;
    }
    gpio_pull_mode_t original = state.pu ? (state.pd ? GPIO_PULLUP_PULLDOWN : GPIO_PULLUP_ONLY)
                                         : (state.pd ? GPIO_PULLDOWN_ONLY : GPIO_FLOATING);
    const gpio_pull_mode_t modes[] = {original, GPIO_PULLUP_ONLY, GPIO_PULLDOWN_ONLY};
    unsigned highs[3] = {}, samples[3] = {}, reference[3] = {};
    for (int i = 0; i < 3; ++i) {
      gpio_set_pull_mode(GPIO_NUM_18, modes[i]); delay(2);
      uint32_t start = micros();
      while (micros() - start < 30000) {
        highs[i] += gpio_get_level(GPIO_NUM_18);
        reference[i] += gpio_get_level(GPIO_NUM_17);
        samples[i]++;
      }
    }
    gpio_set_pull_mode(GPIO_NUM_18, original);
    Serial.printf("SVSTATUS ie=%u oe=%u pu=%u pd=%u base_high=%u base_n=%u up_high=%u up_n=%u down_high=%u down_n=%u reference_high=%u reference_n=%u\n",
      state.ie, state.oe, state.pu, state.pd, highs[0], samples[0], highs[1], samples[1],
      highs[2], samples[2], reference[0], samples[0]); return;
  }
  if (command == 'Y') {
    gpio_io_config_t state = {};
    gpio_get_io_config(GPIO_NUM_18, &state);
    if (state.oe) { Serial.println("SVERROR gpio18_output_active"); return; }
    gpio_input_enable(GPIO_NUM_18); Serial.println("SVOK input_enabled"); return;
  }
  if (command == 'B' || command == 'I') {
    rgb565_big_endian = command == 'B';
    jpgSetRgb565BE(rgb565_big_endian);
    Serial.printf("SVOK rgb565_be=%u\n", rgb565_big_endian); return;
  }
  if (command == 'T' || command == 'U') {
    colorbar_enabled = command == 'T';
    int result = sensor->set_colorbar(sensor, colorbar_enabled);
    Serial.println(result == 0 ? "SVOK" : "SVERROR colorbar_setting"); return;
  }
  if (command == 'K') {
    if (selected != 0) { Serial.println("SVERROR raw_requires_qvga"); return; }
    camera_fb_t *frame = esp_camera_fb_get();
    if (!frame) { Serial.println("SVERROR capture_failed"); return; }
    Serial.printf("SVRAW %u %u %u %u\n", static_cast<unsigned>(frame->len),
      static_cast<unsigned>(frame->width), static_cast<unsigned>(frame->height),
      static_cast<unsigned>(frame->format));
    Serial.write(frame->buf, frame->len); Serial.flush();
    Serial.println("\nSVEND 0"); esp_camera_fb_return(frame); return;
  }
  if (command == 'P') {
    Serial.printf("SVSTATUS proto=2 pid=0x%x psram=%u flash=%u mode=rgb565_to_jpeg width=%u height=%u quality=%u tx_buffer=%u fb_count=%u psram_dma=%u\n",
      sensor->id.PID, static_cast<unsigned>(ESP.getPsramSize()),
      static_cast<unsigned>(ESP.getFlashChipSize()), resolutions[selected].width,
      resolutions[selected].height, jpeg_quality, tx_buffer_bytes,
      selected <= 2 ? requested_buffers : 1, esp_camera_get_psram_mode());
  } else if (command == 'C') {
    uint32_t start = micros();
    camera_fb_t *frame = esp_camera_fb_get();
    uint32_t captured = micros();
    if (!frame) { Serial.println("SVERROR capture_failed"); return; }
    uint8_t *jpeg = nullptr; size_t jpeg_size = 0;
    if (!encode_frame(frame, jpeg_quality, &jpeg, &jpeg_size)) {
      esp_camera_fb_return(frame); Serial.println("SVERROR jpeg_conversion_failed"); return;
    }
    uint32_t encoded = micros();
    Serial.printf("SVJPEG %u %u %u %u %u\n", static_cast<unsigned>(jpeg_size),
      static_cast<unsigned>(captured - start), static_cast<unsigned>(encoded - captured),
      static_cast<unsigned>(frame->width), static_cast<unsigned>(frame->height));
    Serial.write(jpeg, jpeg_size);
    Serial.flush();
    uint32_t transferred = micros();
    Serial.printf("\nSVEND %u\n", static_cast<unsigned>(transferred - encoded));
    free(jpeg); esp_camera_fb_return(frame);
  } else if (command == 'H' || command == 'V') {
    int result;
    if (command == 'H') { mirror_image = !mirror_image; result = sensor->set_hmirror(sensor, mirror_image); }
    else { flip_image = !flip_image; result = sensor->set_vflip(sensor, flip_image); }
    Serial.println(result == 0 ? "SVOK" : "SVERROR sensor_setting");
  } else Serial.println("SVERROR unknown_command");
}
