# Arquitetura inicial

Este documento descreve a arquitetura planejada. Os componentes e parâmetros
ainda serão validados por benchmarks e testes de bancada.

O [escopo aprovado para a entrega](ESCOPO.md), registrado na #10,
inclui áudio e vibração. Na perda da conexão, observações visuais vencidas
devem ser descartadas e a indisponibilidade visual informada, sem bloquear o
caminho tátil. O [contrato #12](protocol/eventos-semanticos.md) define o perfil
experimental inicial aprovado por Bryan, ainda não validado no hardware.

## Separação de responsabilidades

O sistema possui duas camadas:

1. **ESP32-S3:** sensores, geometria, risco, TTC e feedback tátil local.
2. **VM:** detecção, tracking, trajetória, contexto semântico e telemetria.

```text
Óculos / ESP32-S3                     Nuvem / VM
├── VL53L5CX (ToF)                    ├── detecção de objetos
├── BNO085 (IMU)                      ├── IDs persistentes
├── OV2640 (câmera)                   ├── direção e trajetória
├── risco e TTC local                 ├── API, MQTT e eventos
├── feedback háptico                  └── métricas experimentais
└── áudio
```

O modo tátil local não pode depender da disponibilidade da câmera, rede ou VM.
Veja o [ADR 0001](decisions/0001-cloud-first.md).

## Percepção

O VL53L5CX fornece uma matriz 8×8; seu adaptador deverá declarar status,
convenção de distância e calibração. A orientação do BNO085 será usada para
compensar pontos em uma referência conhecida, sem inferir direção da caminhada.
A câmera fornece observações visuais e sugestões de áudio pela VM.

```text
ToF + IMU ► geometria + proximidade + risco/TTC local ► arbitragem tátil local
Câmera ► VM/detector/tracker ► observações visuais + áudio + telemetria
                                                ► arbitragem de áudio local
```

Classes, track_id e trajetória remotos não alteram risco, TTC ou vibração local.
O modo tátil continua independente de câmera/rede/VM. O núcleo simulado da
[#9](local-geometry.md) não aciona hardware; TTC candidato exige ponto associado
explicitamente na fixture e não comprova colisão física. Convenção real,
limiares operacionais e comportamento no ESP dependem de validação de bancada.
Correção aprovada no [ADR 0019](decisions/0019-nucleo-geometrico-local.md).

## Risco e feedback

O campo de percepção será inicialmente dividido em esquerda, centro e direita.
Dois atuadores LRA deverão comunicar lado, proximidade e urgência. Alertas de
áudio poderão acrescentar mensagens como “pessoa se aproximando pela esquerda”,
com prioridade, cooldown e controle de repetição.

O objetivo do tracking é manter um histórico por `track_id`, estimar movimento
e distinguir:

- **alvo convergente:** sua trajetória tende à posição do usuário;
- **alvo passante:** cruza o campo de visão sem convergir para o usuário.

## Captura e comunicação

A hipótese inicial é usar captura adaptativa: baixa taxa de quadros no estado
normal e maior frequência quando os sensores indicarem atenção. O protocolo
deverá priorizar frames recentes e descartar informação visual atrasada.

Mensagens inicialmente previstas:

```text
ESP32 → VM: HELLO, FRAME, RISK, COMMAND, HEARTBEAT
VM → ESP32: TRACKS, SPEAK, SET_MODE, CONFIG
```

Esses nomes ainda não constituem um contrato implementado. Mudanças futuras no
protocolo deverão ser registradas em uma issue e, quando afetarem mais de um
módulo, em um ADR.

O [ADR 0003](decisions/0003-eventos-semanticos.md) define para a primeira
inferência JSON/HTTPS com observação e sugestão de áudio separadas na resposta,
sem comandos de vibração. Os nomes acima permanecem ideias históricas, não
autorizam implementar SET_MODE/CONFIG. MQTT é opção futura de telemetria.

## Firmware

A organização prevista mantém lógica pura separada do hardware:

```text
firmware/
├── src/core/       # geometria, risco, TTC, fala e modos
├── src/drivers/    # ToF, IMU, câmera, háptico e áudio
└── src/tasks/      # orquestração FreeRTOS
```

As tarefas críticas de sensores e feedback deverão ser isoladas das tarefas de
rede e mídia. A estrutura real somente será criada pela issue que autorizar a
primeira implementação de firmware.

## Decisões ainda abertas

- limiares de distância, risco e TTC;
- resolução e frequência de captura;
- contrato de mensagens e autenticação;
- provedor e dimensionamento da VM;
- persistência de telemetria;
- necessidade futura de hardware Edge.
