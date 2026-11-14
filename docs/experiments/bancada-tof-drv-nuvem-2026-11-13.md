# Bancada ToF + DRV2605L + câmera → nuvem (10–13/11/2026)

Refs #1 (relacionado a #4, #17 e #19). Responsável humano: Bryan, com apoio de
IA. Firmware: `firmware/bench/bench_tof_drv` (#86) e diagnósticos de
`firmware/bench/` (#84). Evidências numéricas em
[`bancada-tof-drv-nuvem-2026-11-13.json`](bancada-tof-drv-nuvem-2026-11-13.json).
Registro exploratório de bancada, sem participantes; **não** valida segurança,
latência ou uso vestível.

## Montagem

ESP32-S3 N16R8 CAM, VL53L5CX (SDA 41, SCL 42, LPn 40), TCA9548A (0x70) e
DRV2605L com motor 1027 tratado como ERM (ADR 0022). DRVs ligados em SD1
(esquerdo) e SD2 (direito), **divergindo do ADR 0028** (SD0/SD1). OV2640 com o
caminho RGB565→JPEG de `docs/camera-usb.md`. Rede: hotspot de celular.

## O que funcionou

| Item | Resultado |
|---|---|
| ToF | Inicialização ~9,6 s; matriz 8×8 a 2 Hz; quadros contínuos com a fiação corrigida |
| DRV esquerdo | ERM/RTP sem sobrecorrente/temperatura; motor ligado 60 s contínuos; vibração por comando e por distância observada |
| Alerta local | < 50 cm, pulso 80 ms, período 800→200 ms, força constante; independente da rede |
| Câmera | Inicialização OK (QVGA, JPEG 80) no mesmo firmware |
| Nuvem (~60 s) | Imagens: 13 aceitas (200), 0 recusadas por atraso (503); distância: 9 aceitas (204); falhas de conexão em 5 de 28 envios; 1,4–3,7 s por envio |

Antes de priorizar a imagem, com alternância estrita, 40 s rendiam 6 imagens
aceitas e 2 recusadas (503), e a distância passava de 5 s sem atualizar,
sumindo do painel.

## Falhas encontradas e causas

- **ToF sem resposta / inicializa mas não mede:** SDA do ToF ligado ao fio de
  SCL; fios e emendas soltos; GND na protoboard. Resolvido ao corrigir a
  fiação; o GND ainda precisava ser soldado.
- **Ramal 2 do TCA trava o barramento:** linhas livres ao selecionar o ramal,
  travamento ao conversar com o DRV direito; o mesmo DRV vibrou sozinho após
  ligar. Provável fiação/solda ou módulo danificado. DRV direito desativado
  (`RIGHT_ENABLED=false`).
- **Motor parava sozinho no modo contínuo:** defeito de firmware; a rotina de
  reinício do ToF parava os motores. Corrigido.
- **HTTP 409 no painel:** sessão diferente e contadores reiniciados após RESET.
  Ajuste de bancada: contadores e deslocamento de tempo persistidos em NVS
  (diverge do guia da API, que pede sessão nova por boot).

## Não validado

Latência sensor→vibração, amplitude e conforto; DRV direito; orientação física
da matriz (esquerda/direita); distâncias contra referência medida; IMU e áudio;
desempenho em rede que não seja hotspot. Bit 5 da câmera (GPIO18) continua em
aberto.

## Decisões pendentes do grupo

1. Ramais dos DRVs: ajustar a montagem para SD0/SD1 ou atualizar o ADR 0028.
2. Contadores persistidos × sessão por boot do guia da API.
3. Força gradual opcional (`f`) × força constante do perfil háptico.
4. Limiar de 50 cm e cadência 800→200 ms são valores de bancada, não aprovados.
