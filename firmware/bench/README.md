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
| `bench_tof_drv` | ToF + TCA9548A + DRV2605L: alerta por lado, tabela em cm, envio opcional | opcional |
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
- `sequence` e `captured_at_ms` recomeçam a cada boot do ESP. Depois de um
  RESET, o servidor responde HTTP 409 (`tof_order`) até a sessão ser reiniciada
  no servidor; não reiniciar o ESP numa sessão ativa sem coordenar.
- Leituras do ToF ainda não foram comparadas com distância de referência.
- Diagnóstico de 10/11/2026: o ToF não respondia por mau contato na fiação;
  após o reparo respondeu 18/18 e entregou quadros 8×8.

## `bench_tof_drv`: alerta de bancada (11–13/11/2026)

Valores escolhidos pelo grupo **só para este ensaio**; não são limiares
aprovados do projeto:

- Alerta abaixo de 50 cm, por lado: metade esquerda da matriz (c0–c3) → DRV
  esquerdo, metade direita (c4–c7) → DRV direito; frente aciona os dois.
  Orientação física não conferida; `x` inverte os lados.
- Cadência: pulso de 80 ms a cada 800 ms (50 cm) até 200 ms (≤10 cm).
- Força: **constante no máximo** (padrão, como em `docs/firmware-integration.md`).
  `f` liga uma força gradual opcional (~70% a 50 cm até 100% a ≤10 cm), só para
  comparação de bancada; ela diverge do documento e não é o padrão.
- DRVs em SD1 (esquerdo) e SD2 (direito), como montado. **Diverge do ADR 0028**
  (SD0/SD1). O ramal 2 travou o barramento em todos os testes: `RIGHT_ENABLED`
  está `false` até a fiação do DRV direito ser corrigida.
- Motores em ERM open-loop, RTP, `OD_CLAMP` de fábrica (~3 V). Abaixo de ~70%
  o motor 1027 pode não girar; amplitude/latência não foram medidas.
- Se o barramento I2C travar, o firmware não consegue parar o motor: cortar a
  alimentação. Um corte por hardware (pino EN) é pendência do firmware vestível.
- Sem leitura do ToF por 1 s, os motores param; após 3 s, tenta reiniciar o ToF.
- A nuvem só compila com `wifi_config.h` e `credentials_private.h` na pasta.
  Um pedido por vez: o JPEG QVGA da câmera (`/v1/inference`, mesmo caminho do
  `camera_wifi`) tem prioridade, porque o modelo depende dele; a distância
  (`/v1/demo/tof`) entra quando a última enviada tem ≥3,5 s, abaixo do limite de
  5 s do painel (sem câmera, 1/s). Sem
  quadro do ToF, publica `valid=false` 1/s. A resposta nunca aciona motor.
- `SESSION_ID` precisa ser o do painel (`GET /v1/demo/snapshot` → `source`);
  em 13/11 era `camera-20261109-reconnect3`.
- **Ajuste de bancada que diverge do guia da API:** `sequence`, `frame_id` e um
  deslocamento de `captured_at_ms` ficam na flash (NVS) e saltam a cada boot,
  para o painel de sessão fixa não recusar com 409 após RESET. O guia pede
  contadores desde o boot e sessão nova por boot; decidir com cloud.

Diagnóstico desta bancada: a maior parte das falhas foi mau contato (SDA do
ToF ligado no fio de SCL, fios soltos na protoboard, GND sem solda).
