# Sketches de bancada (#1)

Programas isolados para testar cada peça do hardware. **Não são o firmware
final**: não têm alerta tátil, não integram sensores entre si e não seguem a
organização `core/`, `drivers/` e `tasks/` prevista no `AGENTS.md`. Servem como
referência de pinagem e configuração validadas na bancada.

| Sketch | O que faz | Rede |
|---|---|---|
| `tof_diag` | inicializa o VL53L5CX e imprime a matriz 8×8 (`zona:mm:status:alvos`) a 1 Hz | não |
| `tof_presence_loop` | testa a cada 1 s se o ToF responde em 0x29 e faz scan I2C a cada 10 s | não |
| `tof_pin_toggle` | alterna SDA/SCL em fases de 5 s para medir com multímetro no módulo | não |
| `tof_wifi` | menor distância válida da matriz → `POST /v1/demo/tof` (`demo-tof-1`) | sim |
| `camera_usb` + `bridge.py` | câmera OV2640 em RGB565 → JPEG no ESP → USB → página local | não |
| `camera_wifi` | câmera → JPEG → `POST /v1/inference` (contrato 0.1) | sim |
| `tools/read_serial.py` | lê o serial por N segundos e salva em `serial.log` | — |

## Pinagem usada

- ToF VL53L5CX: SDA GPIO41, SCL GPIO42, LPn GPIO40, VIN 3,3 V, GND comum.
- Câmera OV2640: ver `docs/camera-usb.md`. O bit 5 (D5/Y7 → GPIO18) segue em
  investigação; não usar essas imagens como validação de detecção.

## Compilar e gravar

Arduino-ESP32 3.3.12 e SparkFun VL53L5CX 1.0.3 (MIT, avisos ST preservados),
via `arduino-cli` do Arduino IDE:

```sh
FQBN='esp32:esp32:esp32s3:USBMode=hwcdc,CDCOnBoot=cdc,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=opi'
arduino-cli compile --fqbn "$FQBN" firmware/bench/tof_diag
arduino-cli upload  --fqbn "$FQBN" -p /dev/cu.usbmodem101 firmware/bench/tof_diag
```

Se o upload falhar com `No serial data received`: segure BOOT, aperte e solte
RESET, solte BOOT, grave e depois aperte RESET. Feche o Serial Monitor antes de
gravar. Serial a 115200 baud.

## Credenciais (sketches com rede)

`camera_wifi` e `tof_wifi` precisam de `wifi_config.h` e
`credentials_private.h` na pasta do sketch. Copie os `*.example.h` e preencha.
Os arquivos reais são ignorados pelo Git; nunca os versione.

`SESSION_ID` no sketch precisa ser igual ao `SONAR_DEMO_SESSION_ID` do
servidor; senão a resposta é HTTP 409. O token precisa ser do dispositivo
configurado em `SONAR_DEMO_DEVICE_ID` (senão 403).

## Limites

- HTTP 200/204 confirma transporte, não qualidade da medição nem segurança.
- `tof_wifi` bloqueia durante Wi-Fi/NTP/TLS (até alguns segundos); isso só é
  aceitável em bancada e não pode ser copiado para o laço do alerta tátil.
- Leituras do ToF ainda não foram comparadas com distância de referência.
- Diagnóstico de 10/11/2026: o ToF não respondia por mau contato na fiação;
  após o reparo respondeu 18/18 e entregou quadros 8×8.
