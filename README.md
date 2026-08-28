<p align="center">
  <img src="docs/assets/logo-sonar-vision.jpeg" alt="Sonar Vision — Tecnologia de Auxilio e Navegacao Sonora" width="720">
</p>

# Sonar Vision

> **Tecnologia de Auxílio e Navegação Sonora**

Sistema vestível de navegação assistiva para pessoas com deficiência
visual, combinando sensores de profundidade, orientação espacial, visão
computacional, feedback tátil e processamento remoto em nuvem.

> **Status:** projeto em desenvolvimento. A arquitetura, componentes e
> parâmetros descritos aqui representam a versão inicial e poderão ser
> alterados conforme os testes e benchmarks.

------------------------------------------------------------------------

## Sobre o projeto

O **Sonar Vision** tem como objetivo desenvolver óculos inteligentes
capazes de auxiliar pessoas com deficiência visual na percepção de
obstáculos e situações dinâmicas durante a navegação.

A proposta não é apenas detectar que existe um objeto à frente. O
sistema busca combinar **distância, movimento, orientação e visão
computacional** para compreender melhor o ambiente e identificar
situações de risco.

Exemplos:

-   detectar obstáculos próximos;
-   identificar a direção do obstáculo;
-   detectar obstáculos na altura da cabeça;
-   detectar possíveis desníveis;
-   identificar pessoas e objetos;
-   perceber quando algo está se aproximando;
-   estimar tempo até uma possível colisão (TTC);
-   diferenciar um alvo que se aproxima de outro que apenas passa ao
    lado;
-   fornecer alertas táteis;
-   fornecer informações por áudio.

------------------------------------------------------------------------

## Princípio de segurança

A camada responsável pelo alerta imediato de proximidade funciona
**localmente no ESP32-S3**.

Nenhuma função crítica de segurança deve depender exclusivamente de:

-   conexão com a internet;
-   disponibilidade da VM;
-   visão computacional;
-   inferência probabilística.

A visão computacional acrescenta **semântica e contexto**, mas não
substitui a percepção geométrica realizada pelos sensores locais.

Em caso de perda de conexão com a nuvem, o Sonar Vision deve continuar
funcionando em modo tátil.

------------------------------------------------------------------------

# Arquitetura

Nesta primeira versão, o sistema possui **duas camadas principais**:

``` text
┌──────────────────────────────────────┐
│            SONAR VISION              │
│              ÓCULOS                  │
│                                      │
│  ESP32-S3                            │
│  ├── VL53L5CX (ToF)                  │
│  ├── BNO085 (IMU)                    │
│  ├── OV2640 (câmera)                 │
│  ├── feedback háptico                │
│  └── áudio                           │
│                                      │
│  Reflexo local / segurança           │
└──────────────────┬───────────────────┘
                   │
                   │ Wi-Fi
                   │ frames + estado
                   ▼
┌──────────────────────────────────────┐
│              NUVEM / VM              │
│                                      │
│  Visão computacional                 │
│  ├── detecção                        │
│  ├── tracking                        │
│  ├── trajetória                      │
│  ├── classificação semântica         │
│  └── refinamento de risco            │
│                                      │
│  Serviços                            │
│  ├── API                             │
│  ├── MQTT                            │
│  ├── eventos                         │
│  └── telemetria                      │
└──────────────────┬───────────────────┘
                   │
                   │ resultado
                   ▼
┌──────────────────────────────────────┐
│             ESP32-S3                 │
│                                      │
│  vibração + informação por áudio     │
└──────────────────────────────────────┘
```

Nesta etapa **não será utilizado um dispositivo Edge físico**. O
processamento de visão computacional será executado em uma **VM na
nuvem**.

A arquitetura foi organizada para permitir que, futuramente, a
inferência possa ser movida para Edge sem exigir uma reescrita completa
do firmware ou do protocolo.

------------------------------------------------------------------------

# Camada local --- ESP32-S3

O ESP32-S3 funciona como hub dos sensores e executa o caminho crítico de
segurança.

## Responsabilidades

-   leitura do VL53L5CX;
-   leitura da IMU;
-   captura da câmera;
-   fusão ToF + IMU;
-   projeção espacial da matriz ToF;
-   classificação de proximidade;
-   detecção de obstáculos na altura da cabeça;
-   detecção inicial de desníveis;
-   cálculo de aproximação e TTC;
-   controle do feedback háptico;
-   controle da captura da câmera;
-   comunicação Wi-Fi com a VM;
-   reprodução dos alertas de áudio.

## Hardware previsto

  Componente                     Função
  ------------------------------ ---------------------------------
  ESP32-S3-WROOM-1 N16R8         Microcontrolador principal
  VL53L5CX                       Sensor ToF 8×8
  BNO085                         IMU 9-DOF
  OV2640                         Câmera
  DRV2605L                       Driver háptico
  2× LRA                         Feedback tátil esquerdo/direito
  MAX98357A                      Amplificação de áudio
  Transdutor de condução óssea   Saída de áudio

------------------------------------------------------------------------

# Camada de nuvem --- VM

A VM executará as tarefas de visão computacional que não são adequadas
ao microcontrolador.

## Responsabilidades

-   receber frames enviados pelo ESP32;
-   executar detecção de objetos;
-   rastrear objetos entre frames;
-   manter IDs persistentes;
-   estimar direção e movimento;
-   analisar trajetória;
-   identificar alvos convergentes;
-   retornar informações semânticas ao wearable;
-   receber telemetria e eventos;
-   registrar métricas para os experimentos.

## Stack inicial prevista

-   Python
-   OpenCV
-   YOLO
-   ByteTrack
-   MQTT
-   HTTP/TCP

A stack poderá mudar conforme os benchmarks do projeto.

------------------------------------------------------------------------

# Percepção do ambiente

O Sonar Vision combina três fontes principais de informação:

``` text
VL53L5CX
   │
   ├── distância
   ├── setores
   ├── aproximação
   └── TTC
        │
        ▼
      RISCO
        ▲
        │
OV2640 ─────► YOLO ─────► ByteTrack
                         │
                         ├── identidade
                         ├── direção
                         └── trajetória

BNO085
   │
   └── compensação do movimento
       e inclinação da cabeça
```

### ToF

O VL53L5CX fornece uma matriz de profundidade 8×8. Essa informação é
utilizada para detectar obstáculos e estimar distância sem depender da
câmera.

### IMU

A BNO085 permite compensar a inclinação e o movimento da cabeça.

Isso evita, por exemplo, que o chão seja interpretado como um obstáculo
frontal quando o usuário olha para baixo.

### Câmera

A câmera fornece informação visual para a VM, permitindo adicionar
semântica à percepção:

> O sensor local sabe que **algo** está se aproximando.\
> A visão computacional pode determinar que esse algo é **uma pessoa**.

------------------------------------------------------------------------

# Detecção de risco

O sistema divide o campo de visão em setores:

``` text
┌──────────┬──────────┬──────────┐
│ ESQUERDA │  CENTRO  │  DIREITA │
└──────────┴──────────┴──────────┘
```

Cada setor pode possuir diferentes níveis de proximidade.

O feedback tátil utiliza os dois lados dos óculos para indicar
espacialmente a origem do risco.

Exemplo:

``` text
Risco à esquerda
      ↓
LRA esquerdo vibra

Risco à direita
      ↓
LRA direito vibra

Risco frontal
      ↓
ambos vibram
```

------------------------------------------------------------------------

# Tempo até colisão --- TTC

Além da distância absoluta, o sistema deverá considerar a velocidade de
aproximação.

Uma aproximação inicial pode ser representada por:

``` text
TTC = distância / velocidade de aproximação
```

Isso permite distinguir situações como:

``` text
Objeto a 2 m parado
        ≠
Objeto a 2 m vindo rapidamente
```

O segundo caso possui prioridade maior mesmo que a distância instantânea
seja igual.

------------------------------------------------------------------------

# Trajetória

Um dos principais objetivos técnicos do Sonar Vision é diferenciar um
alvo convergente de um alvo passante.

### Alvo convergente

``` text
        pessoa
          ↓
          ↓
          ↓

       usuário
```

### Alvo passante

``` text
pessoa ───────────────►

          usuário
```

A intenção é reduzir falsos alertas em ambientes movimentados.

O rastreamento temporal será utilizado para estimar:

-   posição;
-   direção;
-   velocidade;
-   estabilidade do rumo;
-   convergência da trajetória.

------------------------------------------------------------------------

# Captura adaptativa

A câmera não precisa transmitir continuamente na maior resolução e taxa
de quadros.

O ESP32 poderá alterar o modo de captura de acordo com o estado dos
sensores.

## Normal

Monitoramento com menor custo:

``` text
QVGA
3–5 FPS
```

## Atenção

Quando houver aproximação, movimento relevante ou mudança rápida de
orientação:

``` text
VGA
10–15 FPS
```

## Identificação

Frames pontuais com maior qualidade poderão ser enviados quando houver
necessidade de análise adicional.

O objetivo é reduzir:

-   largura de banda;
-   consumo energético;
-   processamento desnecessário;
-   quantidade de frames irrelevantes enviados à VM.

------------------------------------------------------------------------

# Feedback ao usuário

## Feedback tátil

É o primeiro nível de alerta e pertence à camada local.

O padrão poderá representar:

-   lado;
-   proximidade;
-   urgência.

Alertas críticos, como obstáculo na altura da cabeça ou possível
desnível, poderão possuir padrões exclusivos.

## Feedback por áudio

A camada semântica poderá complementar o alerta com mensagens como:

``` text
"Pessoa se aproximando pela esquerda."
```

A fala não deverá ser emitida a cada frame.

A política prevista inclui:

-   anunciar mudanças de estado;
-   evitar repetição do mesmo alvo;
-   aplicar cooldown entre mensagens;
-   limitar a quantidade de falas;
-   priorizar eventos críticos;
-   nunca atrasar o alerta tátil esperando a resposta da VM.

------------------------------------------------------------------------

# Modos de operação

O projeto prevê degradação graciosa.

``` text
MODO COMPLETO
ToF + IMU + câmera + VM + tátil + áudio
                │
                │ perda da VM / conexão
                ▼
MODO TÁTIL
ToF + IMU + alertas locais
```

A indisponibilidade da camada semântica não deve impedir o funcionamento
da camada reflexa.

------------------------------------------------------------------------

# Firmware

O firmware utiliza:

-   ESP32-S3;
-   Arduino-ESP32;
-   PlatformIO;
-   FreeRTOS;
-   C++17.

A organização inicial segue três responsabilidades:

``` text
drivers/
    comunicação direta com hardware

core/
    políticas e algoritmos independentes do hardware

tasks/
    orquestração das tarefas FreeRTOS
```

A lógica central deverá permanecer testável sem depender do hardware
físico.

------------------------------------------------------------------------

# Estrutura inicial do repositório

``` text
sonar-vision/
│
├── firmware/
│   ├── platformio.ini
│   ├── include/
│   │   ├── config.h
│   │   ├── types.h
│   │   ├── bus.h
│   │   └── protocol.h
│   │
│   └── src/
│       ├── main.cpp
│       │
│       ├── core/
│       │   ├── geometry/
│       │   ├── risk/
│       │   ├── ttc/
│       │   ├── speech/
│       │   └── mode/
│       │
│       ├── drivers/
│       │   ├── tof/
│       │   ├── imu/
│       │   ├── camera/
│       │   ├── haptic/
│       │   └── audio/
│       │
│       ├── tasks/
│       │   ├── imu/
│       │   ├── tof/
│       │   ├── fusion/
│       │   ├── haptic/
│       │   ├── camera/
│       │   ├── uplink/
│       │   └── speech/
│       │
│       └── bench/
│
├── cloud/
│   ├── vision/
│   │   ├── detection/
│   │   ├── tracking/
│   │   └── trajectory/
│   │
│   ├── api/
│   ├── mqtt/
│   └── telemetry/
│
├── ml/
│   ├── datasets/
│   ├── training/
│   ├── evaluation/
│   └── models/
│
├── hardware/
│   ├── schematics/
│   └── enclosure/
│
├── docs/
│
├── tests/
│
└── README.md
```

Essa estrutura é inicial e poderá ser simplificada ou reorganizada
durante o desenvolvimento.

------------------------------------------------------------------------

# Protocolo ESP32 ↔ VM

O ESP32 será o cliente e a VM será o servidor.

O enlace inicial será realizado através de Wi-Fi.

Entre as mensagens previstas estão:

``` text
ESP32 → VM

HELLO
FRAME
RISK
COMMAND
HEARTBEAT
```

``` text
VM → ESP32

TRACKS
SPEAK
SET_MODE
CONFIG
```

Frames antigos não deverão formar uma fila crescente.

Para percepção dinâmica:

> **informação atrasada pode ser pior do que informação descartada.**

Se a VM estiver processando um frame antigo quando novos frames já
representam melhor o estado atual, o sistema deverá priorizar os dados
recentes.

------------------------------------------------------------------------

# Concorrência no ESP32

As tarefas críticas e as tarefas de comunicação/mídia serão isoladas.

``` text
CORE 1 — REFLEXO

IMU
 ↓
ToF
 ↓
Fusion
 ↓
Risk
 ↓
Haptic
```

``` text
CORE 0 — COMUNICAÇÃO / MÍDIA

Camera
 ↓
Uplink Wi-Fi
 ↓
VM

Speech
Telemetry
```

O objetivo é impedir que problemas de rede ou transmissão causem jitter
no laço de segurança.

------------------------------------------------------------------------

# Roadmap inicial

## Fase 1 --- Bring-up de hardware

-   [ ] Configurar PlatformIO
-   [ ] Validar ESP32-S3 + PSRAM
-   [ ] Testar VL53L5CX isoladamente
-   [ ] Ler matriz ToF 8×8
-   [ ] Testar BNO085
-   [ ] Testar os atuadores LRA
-   [ ] Testar câmera OV2640

## Fase 2 --- Camada reflexa

-   [ ] Implementar projeção da matriz ToF
-   [ ] Integrar ToF + IMU
-   [ ] Criar setores esquerda/centro/direita
-   [ ] Implementar política de proximidade
-   [ ] Implementar feedback háptico
-   [ ] Detectar obstáculo na altura da cabeça
-   [ ] Investigar detecção de desníveis
-   [ ] Garantir laço crítico abaixo do orçamento definido

## Fase 3 --- Aproximação e TTC

-   [ ] Calcular variação temporal da distância
-   [ ] Filtrar ruído
-   [ ] Estimar velocidade de aproximação
-   [ ] Implementar TTC
-   [ ] Definir níveis de risco
-   [ ] Validar com medições reais

## Fase 4 --- Câmera

-   [ ] Captura JPEG
-   [ ] QVGA em modo normal
-   [ ] VGA em modo atenção
-   [ ] Implementar captura adaptativa
-   [ ] Integrar estado de risco com captura

## Fase 5 --- Comunicação com VM

-   [ ] Definir protocolo
-   [ ] Implementar cliente Wi-Fi
-   [ ] Implementar serviço na VM
-   [ ] Enviar frames
-   [ ] Enviar estado de risco
-   [ ] Implementar heartbeat
-   [ ] Implementar timeout e fallback
-   [ ] Instrumentar latência

## Fase 6 --- Visão computacional

-   [ ] Criar pipeline de inferência
-   [ ] Integrar YOLO
-   [ ] Definir classes iniciais
-   [ ] Integrar ByteTrack
-   [ ] Manter IDs entre frames
-   [ ] Retornar detecções ao ESP32

## Fase 7 --- Trajetória

-   [ ] Criar histórico por `track_id`
-   [ ] Estimar velocidade
-   [ ] Estimar direção
-   [ ] Compensar movimento da cabeça
-   [ ] Detectar trajetória convergente
-   [ ] Diferenciar alvo convergente de alvo passante

## Fase 8 --- Áudio

-   [ ] Implementar saída de áudio
-   [ ] Criar política de fala
-   [ ] Cooldown por alvo
-   [ ] Limitar mensagens repetidas
-   [ ] Priorizar alertas críticos
-   [ ] Integrar mensagens da VM

## Fase 9 --- Validação

-   [ ] Testar latência local
-   [ ] Testar latência ESP32 → VM → ESP32
-   [ ] Medir FPS
-   [ ] Medir largura de banda
-   [ ] Medir falsos positivos
-   [ ] Medir falsos negativos
-   [ ] Testar alvos convergentes
-   [ ] Testar alvos passantes
-   [ ] Testar perda de conexão
-   [ ] Validar funcionamento em modo tátil

------------------------------------------------------------------------

# Métricas

## Camada local

-   latência ToF → alerta;
-   estabilidade da leitura;
-   erro de distância;
-   erro do TTC;
-   taxa de falsos alertas;
-   precisão de direção;
-   frequência efetiva do laço.

## Visão computacional

-   Precision;
-   Recall;
-   mAP;
-   FPS;
-   tempo de inferência.

## Tracking

-   IDF1;
-   ID switches;
-   estabilidade do `track_id`;
-   precisão da trajetória.

## Comunicação

-   latência ESP32 → VM;
-   latência de inferência;
-   latência VM → ESP32;
-   latência fim a fim;
-   frames por segundo;
-   MB/min transmitidos;
-   perda/descarte de frames.

## Sistema

-   taxa de detecção de situações de risco;
-   falsos positivos;
-   falsos negativos;
-   tempo de antecipação do alerta;
-   comportamento durante falhas de rede.

------------------------------------------------------------------------

# Objetivo experimental

Além da construção do protótipo, o Sonar Vision busca avaliar
experimentalmente como diferentes estratégias afetam a navegação
assistiva.

Entre os pontos de interesse:

1.  eficácia da fusão ToF + IMU;
2.  precisão do TTC calculado localmente;
3.  redução de banda através da captura adaptativa;
4.  impacto da latência da VM na percepção semântica;
5.  capacidade de distinguir alvos convergentes de alvos passantes;
6.  eficácia do feedback tátil para direção e proximidade;
7.  comportamento do sistema quando a conexão com a nuvem é perdida.

------------------------------------------------------------------------

# Contexto acadêmico

O **Sonar Vision** é desenvolvido como Projeto Integrador do curso de
**Análise e Desenvolvimento de Sistemas --- Senac**.

O projeto explora conceitos de:

-   Internet das Coisas (IoT);
-   sistemas embarcados;
-   FreeRTOS;
-   sensores ToF;
-   fusão sensorial;
-   visão computacional;
-   rastreamento de objetos;
-   computação em nuvem;
-   sistemas distribuídos;
-   tecnologia assistiva.

------------------------------------------------------------------------

## Licença

A licença do projeto ainda será definida.
