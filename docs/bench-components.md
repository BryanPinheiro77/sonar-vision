# #1 — componentes e interfaces da primeira bancada

- Data: 2026-10-09.
- Status: **inventário documental em revisão**; identificação dos módulos,
  esquema/pinos e validação elétrica ainda incompletos. #1 permanece aberta.
- Responsável pelo inventário: Bryan, com apoio de IA; revisão da bancada/grupo
  a registrar antes do aceite.
- Fontes: README, AGENTS.md, ADR0001/0020/0021, issue #1, informações e títulos
  dos prints de compra enviados por Bryan, documentação primária abaixo.

## 1. O que está confirmado e o que o anúncio não comprova

Os prints identificam títulos e quantidades anunciadas; não demonstram marcação
do chip recebido, esquema, reguladores, pull-ups, pinout ou calibração. Há dados
pessoais nos comprovantes; os arquivos brutos e números de pedidos ficam privados.
A tabela registra somente informações técnicas necessárias ao projeto.

**Confirmações diretas do responsável:** um TCA9548A; dois DRV2605L, um por
atuador; WM8960 comprado para substituir MAX98357A (ADR0021). A intenção de
usar dois canais está confirmada. Novo print da descrição do motor informa
rotação de9000RPM, indicando **motor rotativo ERM** por inferência técnica.
Fabricante/modelo inequívoco e ensaio ainda não foram fornecidos; a substituição
experimental da baseline LRA depende de decisão do responsável.

| Função | Identificação informada/visível no anúncio | Quantidade informada | Comparação com baseline | Confirmação restante |
| --- | --- | ---: | --- | --- |
| MCU/placa | “Placa de Desenvolvimento ESP32-S3 WROOM N16R8 CAM”; opção “ESP32-S3 OV2640” | 1 kit | Compatível por título com N16R8 e câmera previstos | Fabricante/revisão/esquema da placa, marcação WROOM-1, USB/regulador/pinout, memória real |
| Câmera | OV2640 incluída na opção do kit ESP32-S3 | 1 no kit | Modelo anunciado coincide com baseline | Interface/conector/mapeamento já roteado na placa e chip recebido; não presumir um pinout de outra S3-CAM |
| ToF | “VL53L5X V2 TOF”, opção “module” | 1 | Nome abreviado não confirma sozinho VL53L5CX | Link/esquema/identificação exata, domínios de alimentação, status e convenção de distância |
| IMU | “TENSTAR BNO085 AR VR IMU”, opção “BNO085 Sensor” | 1 | BNO085 anunciado coincide | Revisão do breakout, interface selecionada, níveis, reset/INT e parâmetros de orientação |
| Mux I2C | “TCA9548A — Multiplexador 8 Canais I2C” | 1 | Componente informado para separar os DRV; já registrado na #4 | Variante da placa, pull-ups, endereço, tensão, canais físicos e reset |
| Driver háptico | “Controlador de Motor Háptico DRV2605L ... IN/TRIG” | 2 | Quantidade confirmada para dois lados | Esquema/revisão das placas, alimentação/níveis, conexão e calibração por motor |
| Atuadores | “Motor de Vibração Vibracall 1027 3V”; descrição declara9000RPM | 2 | **ERM indicado** pela rotação declarada; diverge de LRA | Fabricante/código/datasheet e decisão sobre bancada ERM; limites e partida a medir |
| Áudio | “Módulo de Áudio Codec Estéreo WM8960 ... Mikustg” | 1 | Substituição de MAX98357A confirmada por Bryan, ADR0021 | Link/esquema/revisão, alimentação, saída, clock e transdutor |
| Transdutor | Nenhum modelo identificado nos prints | Pendente | Condução óssea prevista | Modelo, quantidade, impedância, potência, fixação/conforto e conexão elétrica |
| Alimentação | Fonte/bateria/reguladores não identificados | Pendente | Arquitetura de alimentação não congelada | Modelos, capacidade/picos, proteções, limites USB/regulador e distribuição aos módulos |

Não classificar motores apenas pelo formato de moeda ou pelo nome “1027”. A
nova evidência é a **rotação declarada em RPM**, compatível com ERM, em vez de
oscilação linear descrita por frequência de um LRA. Essa classificação é uma
inferência sobre a descrição comercial, não identificação física do fabricante.
O DRV2605L suporta ERM e LRA [E5], com modos/calibração diferentes. A proposta
para usar os motores existentes em bancada está no [ADR0022](decisions/0022-ensaio-erm-1027.md),
aguardando decisão. Nenhuma substituição de atuador está aprovada neste estágio.

### Dados novos do vendedor — sem validação física

O print de descrição informa: operação2,5–4V, corrente máxima80mA, rotação9000RPM,
cabo3cm, diâmetro9mm e altura4mm. Registrar exatamente esses valores como
**declarações do anúncio**, não limites certificados do motor recebido.
O nome1027 não autoriza substituir dimensões por10×2,7mm de outro produto.
Corrente/picos de partida, rated voltage/overdrive e controle ainda precisam de
verificação; a faixa do vendedor não configura a saída do driver automaticamente.

O print de descrição da S3 lista8MB PSRAM e operação3–3,6V, compatíveis como
referência com a variante anunciada. “Até45GPIO” e números de periféricos são
características genéricas do SoC; não mostram GPIOs disponíveis na placa nem
mapeamento do conector da câmera. Esquema/revisão e pinout permanecem pendentes.

O terceiro print lista campos genéricos “microcontroladorArduino”, clock0kHz e
memórias0KB, sem identificar o componente na própria imagem. Esses campos não
fornecem esquema ou parâmetros elétricos confiáveis de uma placa WM8960/S3;
não usar valores zero como configuração. Descrição técnica do codec segue pendente.

### Links recebidos e alcance da verificação

- [Placa S3-CAM, anúncio AliExpress 1005012656370024](https://pt.aliexpress.com/item/1005012656370024.html):
  metadados do fornecedor repetem N16R8 e alternativas OV2640/5640; o print
  identifica a opção comprada OV2640. Conteúdo completo/esquema e imagens técnicas
  não ficaram acessíveis nesta coleta; não considerar pinagem validada.
- [WM8960, anúncio Mercado Livre MLB2050093299](https://www.mercadolivre.com.br/modulo-de-codec-de-audio-estereo-wm8960-para-nymyiu/p/MLB2050093299):
  link informado pelo responsável; a página retornou acesso sem ficha técnica.
  O título/quantidade vêm do print; a substituição vem da confirmação direta.
- [Motor1027, anúncio Mercado Livre MLBU1138967004](https://www.mercadolivre.com.br/motor-de-vibracao-vibracall-1027-3v/up/MLBU1138967004):
  link informado; descrição posteriormente fornecida por print, com9000RPM
  indicando ERM. Esquema/fabricante/modelo físico não comprovados pelo anúncio.

Links de produto estão registrados sem parâmetros de navegação/compra. Capturas
ou texto da descrição técnica e esquema foram solicitados ao responsável para
completar a identificação. Não atribuir características de outro anúncio apenas
porque apresenta a mesma forma ou nome genérico.

## 2. Referências elétricas — chip versus placa comprada

Valores abaixo vêm dos chips/famílias em datasheets, **não são tensões escolhidas
para ligar os módulos do anúncio**. Reguladores, conversores de nível e straps
podem mudar o que o conector aceita. Todas as posições GPIO e portas físicas do
mux estão pendentes. Endereços referem-se a **7bits**, salvo anotação explícita.

| Componente | Alimentação do chip / referência | Interface/endereço de referência | Restrições a conferir no módulo |
| --- | --- | --- | --- |
| ESP32-S3-WROOM-1 N16R8 | VDD33 3,0–3,6 V, típico 3,3 V [E1] | GPIO/periféricos; não tem endereço I2C como MCU controlador | N16R8: 16MB flash Quad + 8MB PSRAM Octal; GPIO35/36/37 reservados à PSRAM nessa variante. Entrada USB/5V da placa é diferente de VDD33 do módulo [E1] |
| OV2640 do kit | Domínios/conector da placa a confirmar | Sensor configurado pelo driver OV2640; captura paralela do módulo conforme placa [E6] | Mapeamento nativo da placa/conector, XCLK, sync/dados, buffers e PSRAM; não copiar pinagem de outro fabricante |
| VL53L5CX, se confirmado | ST descreve opções 3,3/2,8 V e IOVDD 1,8 V, conforme domínios/configuração [E2] | I2C; 0x29 em 7bits deriva de 0x52 byte de escrita do datasheet; capacidade do chip até1MHz [E2] | Confirmar que seja CX; board/reguladores/níveis, INT/LPn/reset, status e distância radial antes de usar core #9 |
| BNO085 anunciado | Tensões da placa não confirmadas | Datasheet CEVA a reconferir com esquema do breakout; interface/straps/endereço pendentes [E3] | INT/reset, temporização do protocolo, qualidade/referência da orientação e comportamento do barramento |
| TCA9548A | VCC 1,65–5,5 V, conforme datasheet [E4] | I2C até400kHz; endereço 0x70–0x77 conforme A0/A1/A2, sem selecionar valor agora [E4] | Pull-ups por ramal, tensões, canais habilitados e RESET; não é driver de potência |
| DRV2605L ×2 | VDD 2–5,2 V [E5] | I2C 0x5A (7bits), coincidente nos dois drivers [E5] | Ramais distintos para acesso independente; tipo/amplitude/calibração do atuador; OUT+/OUT− são um par diferencial |
| WM8960 | AVDD2,7–3,6 V; domínios digitais1,71–3,6 V; alimentação speaker até5,5 V, conforme datasheet [E7] | Controle serial 2fios + interface de áudio; endereço7bits 0x1A, byte de escrita0x34 [E7] | Alimentação real da placa, MCLK/referência da PLL, master/slave, formato I2S e saída speaker/headphone apropriada ao transdutor |
| Motor Vibracall 1027 3V | Vendedor declara2,5–4V e80mA máx.; título3V | Saída do driver; sem endereço I2C próprio;9000RPM declarado indicaERM | Identificação física, decisão/calibração ERM, corrente/picos de partida; não configurar comoLRA ou ligar ao GPIO |
| Transdutor | Pendente | Saída de áudio da placa a definir após identificação | Impedância/potência, saída diferencial ou headphone, montagem e limites de ganho |

[E1] [Espressif WROOM-1/1U v1.8, tabela de variantes, pinos e condições](https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf).
[E2] [ST VL53L5CX: alimentação e I2C](https://www.st.com/resource/en/datasheet/vl53l5cx.pdf).
[E3] [CEVA BNO08X datasheet](https://www.ceva-ip.com/wp-content/uploads/BNO080_085-Datasheet.pdf).
O endpoint CEVA ficou indisponível na reconferência; não preencher números
elétricos/endereço como verificados por esta coleta até ter documentação acessível.
[E4] [TI TCA9548A: alimentação, clock e endereço](https://www.ti.com/lit/ds/symlink/tca9548a.pdf).
[E5] [TI DRV2605L: alimentação, controle e atuadores](https://www.ti.com/lit/ds/symlink/drv2605l.pdf).
[E6] [Driver oficial Espressif OV2640](https://github.com/espressif/esp32-camera/blob/master/sensors/ov2640.c).
[E7] [Datasheet primário Cirrus Logic WM8960 rev4.4, cópia no suporte TI](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/6/WM8960.pdf).
Datasheet imprime “0011010 (0x34h)”: a sequência de 7bits é0x1A; 0x34 inclui
bit de escrita. Não copiar0x34 para uma API que espera endereço de7bits.

## 3. Interfaces e conflitos já identificados

### I2C e dois lados

Esquema lógico informado: ESP32-S3 → TCA9548A → dois ramais → um DRV2605L e
um atuador por ramal. Não há atribuição de números de ramal ou GPIO.

- Os DRV repetem0x5A; selecionar somente o ramal alvo para acesso independente.
  Seleção + transação precisam ser indivisíveis entre tarefas. Ler dois dispositivos
  de mesmo endereço habilitados juntos não identifica os retornos separadamente.
- Troca do ramal não é comando para parar o driver. Reprodução conjunta é possível
  conforme modo/controle, mas sincronismo precisa ser medido; registrar atraso E/D.
- O limite do TCA é400kHz; o limite de1MHz do ToF não autoriza usar1MHz no
  barramento que inclui o mux. Frequência/topologia dependerão de todos os
  dispositivos e características físicas; não são escolhidas aqui.
- Pull-ups de várias placas em paralelo, capacitância/comprimento e domínios de
  tensão exigem esquema. Conversão de níveis não pode ser presumida da cor da placa.
- Não decidir que todos os sensores/codec ficarão atrás do mux sem analisar tempo
  de leitura, contenção e falhas; registrar a posição real de cada dispositivo.

### Câmera, áudio e memória

- A pinagem nativa da câmera pode ocupar GPIOs antes de escolher ToF/IMU/áudio.
  Para N16R8, respeitar GPIO35/36/37 usados pela PSRAM; verificar USB/boot/LED e
  periféricos já roteados na placa, sem criar mapa PlatformIO a partir da foto.
- Câmera e áudio exigem planejamento de clocks/DMA/buffers e PSRAM. Medir heap/
  stack e prioridades quando integração existir; não aprovar RAM/WCET com base
  nos testes nativos do core. Firmware C++17/Arduino-ESP32/FreeRTOS permanece.
- WM8960 requer controles e clock de sistema; PLL usa MCLK como referência [E7].
  Não aplicar a integração simples de MAX98357A sem verificar fonte de clock da
  placa. A troca de componente não muda o PCM candidato nem o contrato0.1.
- O transdutor precisa corresponder à saída correta e aos limites de carga.
  Não unir saída diferencial de speaker ao terra como se fosse headphone.
- Leitura/configuração de áudio/mídia não pode manter barramento/tarefa crítica
  bloqueada. Timeout/recuperação/prioridades dependem do protocolo e do firmware;
  nenhuma duração é inventada neste inventário.

### Alimentação e atuação

- Verificar orçamento de corrente e picos simultâneos de Wi-Fi/câmera, dois
  drivers/motores e áudio, limite do regulador/USB e desacoplamento por módulo.
  Uma tensão nominal de chip não demonstra capacidade do regulador da placa.
- Dimensionamento requer dados reais dos atuadores e transdutor; não calcular
  autonomia, escolher bateria ou ligar cargas com corrente desconhecida.
- Calibrar cada driver para seu próprio atuador. Modo LRA exige confirmação de
  LRA; no caso ERM, revisar hardware/perfil antes de usar a proposta da #4.
- Independência da nuvem continua requisito. Interrupção visual/codec não pode
  bloquear o alerta local; isso permanece pendente de ensaio físico.

Esses conflitos são análise documental, não resultados de osciloscópio/bancada.

## 4. Pendências para concluir a #1

1. Links/esquemas/identificação da placa S3-CAM N16R8 e seu módulo OV2640,
   breakout ToF “VL53L5X V2”, TENSTAR BNO085, TCA e DRV. Marcação e variante
   física podem ser verificadas quando as placas estiverem disponíveis.
2. A descrição do motor1027 já foi recebida;9000RPM indicaERM. Registrar decisão
   sobre ensaio dos motores comprados ou manutenção de LRA (ADR0022), obter
   fabricante/datasheet e verificar parâmetros físicos. Não presumir que a compra
   aprovou a substituição da baseline.
3. Link/esquema da placa WM8960 e dados do transdutor de condução óssea.
4. Fonte/alimentação/reguladores, tensões dos conectores/I/O, pull-ups/straps e
   endereços efetivos; verificar conflitos de memoria/periféricos na placa exata.
5. Revisão do grupo na tabela e registro de decisão elétrica pertinente. Só
   depois publicar configurações de placa/pinos numa issue de implementação.

| Critério da #1 | Estado atual |
| --- | --- |
| ESP32-S3-WROOM-1 N16R8 e placa exata | Anunciado N16R8 S3-CAM; esquema/marcação pendentes |
| Versões/módulos dos sensores/atuadores/áudio | Inventário transcrito; várias variantes pendentes; motorERM inferido da descrição, decisão pendente |
| Tensão/barramento/endereço/requisitos | Referências de chip verificadas onde acessíveis; parâmetros das placas pendentes |
| Conflitos de interfaces/memória/alimentação | Análise documental registrada, sem mapa de pinos |
| Tabela revisada pelo grupo | Preparada; revisão/aceite completo pendentes |
| Não escolher pinos silenciosamente | Cumprido nesta entrega: nenhum pino atribuído |
| ADR para alteração arquitetural | WM8960 confirmado em ADR0021; atuador continua sem substituição aprovada |

## 5. Verificação e limites

Verificação aplicável: `python scripts/check_docs.py` e `git diff --check`.
Não há build/driver/pinos novos, aquisição ou atuação executada, peso/dataset/
credencial nem componente Edge. Referências elétricas não validam os breakouts
comprados. A #1 não pode ser encerrada apenas porque foram identificados títulos
nos comprovantes; requisitos incompletos permanecem visíveis acima.
