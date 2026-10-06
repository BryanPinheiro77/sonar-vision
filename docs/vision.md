# Módulo de detecção e tracking — #21

Implementação experimental independente de HTTP em `src/sonar_vision/`.
Responsável: Bryan. Não implementa distância, risco/TTC, trajetória (#11),
seleção de fala (#31), API (#24) ou firmware. A #16 adiciona uma integração
experimental opcional para escadas e sentido.
O caminho tátil local continua independente deste módulo.

## Instalação e testes

Na raiz do repositório, Python 3.11 ou superior:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m sonar_vision.benchmark --frames 100 --output results/scripted-01.json
```

O núcleo e o benchmark simulado não precisam de câmera, rede, torch nem pesos.
Sem o extra abaixo, os testes do adaptador ByteTrack aparecem como **skipped**;
isso não equivale a validar o tracker real.

```sh
python -m pip install -e '.[vision]'
python -m unittest discover -s tests -v
```

Alternativa sem instalação, para testes de código-fonte:
`PYTHONPATH=src python -m unittest discover -s tests -v`.
Dependências diretas opcionais estão fixadas no `pyproject.toml`. O relatório
registra também versões transitivas relevantes; não há lock universal ou
garantia de desempenho entre plataformas. Não atualizar Ultralytics sem testar
novamente o adaptador, especialmente IDs e índices de detecção.

## Interface para Julio (#24)

```python
from sonar_vision import Frame, VisionService
from sonar_vision.ultralytics_backend import UltralyticsFactory, VisionConfig

# Inicialização do processo, não por requisição. Arquivo confiável, já obtido.
factory = UltralyticsFactory("models/yolov8n.pt", VisionConfig())
vision = VisionService(factory)
vision.open("device-authenticated", "session-from-device")

# image_bgr: numpy.ndarray uint8 HxWx3 decodificada e limitada pela API.
result = vision.process(Frame(
    device_id="device-authenticated", session_id="session-from-device",
    frame_id="1", captured_at_ms=1234, image=image_bgr,
))
response = {"observation": result.observation(), "audio": None}
# A política de anúncios preencherá audio em outra issue.
vision.close("device-authenticated", "session-from-device")
```

Para integração sem ML, `VisionService(SyntheticBackend)` usa a fixture em
`sonar_vision.benchmark`; testes também mostram como injetar um backend próprio
com `infer(image) -> list[Detection]` e `close()`. Cada chamada à factory deve
criar um backend com **tracker novo**, nunca reutilizar estado entre sessões.

### Entrada e saída

- `device_id`: vem da autenticação na API, **não** do JSON enviado pelo cliente.
- `session_id`: criado pelo dispositivo; 1..128 bytes UTF-8. Abrir explicitamente.
- `frame_id`: contador decimal canônico crescente (`"0"`, `"1"`, …), até 128 bytes.
- `captured_at_ms`: inteiro seguro em JSON, monotônico do dispositivo, ecoado
  sem trocar pelo relógio do servidor. Regressões são rejeitadas.
- Imagem: BGR uint8, sem espelhamento adicional; resolução constante na sessão.
  Mudança de resolução exige `reset` antes da próxima inferência.
- `Result.detections`: classes normalizadas, confiança, caixa xyxy normalizada
  em [0,1] **na imagem original** e ID string ou `None` (sem tracking confirmado).
- `Result.history`: snapshots limitados por ID, com frame, captura e caixa;
  nenhuma imagem é mantida no histórico. Não interpolar através de oclusão.
- `Result.events`: `appeared`, `lost`, `recovered`, `expired`, `evicted` são
  diagnósticos do histórico exposto, **não** contagem de pessoas/ID switches.
- `processing_ms`: tempo de inferência/tracking/normalização, sem HTTP/decode.

`result.observation()` produz somente os campos do
[contrato 0.1](protocol/eventos-semanticos.md). Caixas, histórico, diagnósticos,
device_id e tempo de processamento **não são campos novos do protocolo**.
Direção espacial e movimento ficam `unknown`; definir setores/direção exige a
etapa posterior, sem inventar limiares de segurança. `stair_direction` é
`up/down/unknown` para stairs quando o peso opcional da #16 está ativo;
sem ele, `unknown`. Para outras classes, é `null`. Modelos COCO usados aqui
não detectam escadas por si: normalização do nome não cria essa capacidade.

Preservamos classes previstas no contrato; `dining table` → `dining_table` e
`traffic light` → `traffic_light`; demais classes fora do vocabulário → `unknown`.
Não inferimos idade: criança detectada como person permanece person.
Todos os objetos passam pelo tracker; a saída é limitada às 20 detecções de
maior confiança (empates mantêm ordem do detector). Isso **não prioriza risco**
e pode omitir obstáculos importantes em multidões; política de relevância não
está pronta. Resultado vazio não significa caminho livre.

### Ciclo de vida e falhas

- Chave interna `(device_id, session_id)`; identidade completa inclui epoch e ID.
- `open` é idempotente para sessão existente, não reinicia tracker.
- `reset` troca backend/epoch e apaga histórico, preservando a última referência
  temporal/frame para rejeitar replay. `close` remove a sessão e seus recursos.
- Erro no backend invalida a sessão: o tracker pode ter sido parcialmente
  alterado. Reabrir explicitamente gera epoch novo, nunca continuar silenciosamente.
- Sessões ociosas expiram por relógio monotônico do servidor; limpeza ocorre
  na próxima abertura, reinício ou processamento, sem thread em background.
- `SessionMissing`: sessão não aberta/expirada; `Busy`: capacidade ocupada;
  `ValueError`: metadados, ordem, imagem ou saída inválidos. A API deve traduzir
  erros e não devolver detalhes internos/credenciais ao cliente.
- Um lock **não bloqueante** serializa todas as operações da instância, inclusive
  dispositivos diferentes. Trabalho concorrente recebe Busy, sem fila de frames.
  Isso é limite conservador experimental, não projeto final de concorrência.
- Não há autenticação, rejeição automática de sessões antigas por dispositivo,
  limite de upload, cancelamento de GPU ou relógio compartilhado nesta camada.
  A API deve escolher sessão ativa, limitar pixels antes de decodificar, fechar
  a anterior em reboot e invalidar respostas de requisições canceladas.
  `close/reset` durante inferência pode retornar Busy; não enfileirar frames.
- Em múltiplos processos, a API precisa encaminhar a sessão à instância dona
  ou invalidar epoch ao trocar de worker; memória não é compartilhada.
- Validade continua 1000 ms **desde captura**. A API/cliente verifica idade e
  orientação; não há como comparar diretamente relógios monotônicos remotos.

### Limites operacionais configuráveis

`VisionService`: 8 sessões, inatividade de 60 s, até 256 históricos, 60 amostras
por ID, expiração após mais de 60 frames processados sem observação. Estes são
limites de memória do protótipo, **não** limiares de risco nem timeout do protocolo.
Ao recuperar ID após ausência, começa um novo segmento de histórico. Expulsão
por capacidade aparece como `evicted`; não promete continuidade de identidade.
O backend tem seus próprios estados ByteTrack limitados por deteções/buffer;
os 256 históricos não são limite global de memória de torch.

`VisionConfig`: entrada 640, confiança 0.35, CPU, até 300 detecções; ByteTrack
high=0.25, low=0.1, new=0.25, buffer=60, match=0.8, fuse_score=true.
São parâmetros experimentais aproveitados do lab. Buffer conta **frames
processados**, não segundos; baixar frequência muda sua duração temporal.
Confiança 0.35 filtra antes do tracker e impede a associação com detecções
abaixo desse corte: existe um trade-off a medir, não um ajuste já otimizado.

## Modelos, artefatos e licenças

YOLOv8n continua baseline comparável; YOLO26n é alternativa configurável já
testada. Nenhum é superior apenas pela data. O construtor exige escolher
explicitamente um `.pt` local: não baixa pesos nem abre câmera automaticamente.

### Escadas e sentido: integração experimental da #16

O mesmo `UltralyticsFactory` aceita o peso oficial `yolov8n-oiv7.pt`, que
inclui a classe `Stairs` entre suas 601 classes. Com o peso obtido de fonte
confiável e salvo fora do Git, troque apenas o caminho na inicialização:

```python
factory = UltralyticsFactory("models/yolov8n-oiv7.pt", VisionConfig())
```

Não há download automático nem mudança de modelo padrão. O adaptador traduz
`Stairs` para `stairs` e, sem peso de direção, a observação produz
`stair_direction="unknown"`: esse peso detecta presença, **não
subida/descida**. Um teste local pela
interface visual com uma foto de escada vista de baixo produziu uma detecção
`stairs`, confiança `0.7527`, sentido `unknown`; SHA-256 do peso usado:
`3851dfbf39ed2a076b1f39215cc22dba64eb5646f282bf964703785b0bed6a41`.
Isso confirma compatibilidade de execução, não acurácia nem segurança.

Para preservar as classes gerais e acrescentar sentido, carregue **dois**
pesos confiáveis locais: o detector geral usado pelo módulo e o peso de duas
classes `stairs_up/stairs_down` treinado no laboratório. A segunda etapa é
explícita; um peso de duas classes passado como detector principal é rejeitado.

```python
factory = UltralyticsFactory(
    "models/yolov8n.pt", VisionConfig(),
    stair_direction_weights="models/stairs-up-down-v3.pt",
)
vision = VisionService(factory)
```

O detector principal e seu ByteTrack continuam responsáveis pelas classes
originais. Para caixas de escada que coincidam com suas caixas (`IoU >= 0.5`),
o segundo peso acrescenta `up/down`; conflito ou ausência de sentido produz
`unknown`. Caixas do segundo peso sem correspondência entram como `stairs`
com `track_id=null`. Caixas `up/down` sobrepostas e conflitantes são reunidas
como `unknown`. O valor `0.5` veio do piloto da #16; não é limiar de segurança
aprovado. Consulte [ADR 0013](decisions/0013-sentido-escadas-opcional.md).

Os pesos **não acompanham o clone Git**. Baixe o detector geral oficial e a
[pré-release pública do modelo de escadas](releases.md), conferindo seus
SHA-256:

```sh
python3 scripts/download_vision_models.py
```

O comando grava `models/yolov8n.pt` e `models/stairs-up-down-v3.pt`; sem os
arquivos, a opção não inicializa. Ninguém precisa das fotos de treino ou de
executar o treinamento para usar os pesos publicados. O pacote opcional
`.[vision]` já inclui a versão
fixada do Ultralytics; nenhuma nova dependência foi adicionada. Em teste local
com YOLOv8n como detector geral, a interface completa repetiu os 17 acertos,
1 `unknown`, 2 perdas e 0 falsos positivos nas 30 imagens **já abertas** na
avaliação anterior; isso é verificação de integração, não nova avaliação
independente. A decisão de ativar o segundo peso no produto continua pendente
da #7. O feedback tátil local do ESP32-S3 independe desta detecção visual.

1. Obter pesos de detecção a partir das páginas oficiais
   [YOLOv8](https://docs.ultralytics.com/models/yolov8/),
   [YOLO26](https://docs.ultralytics.com/models/yolo26/) ou
   [Open Images V7](https://docs.ultralytics.com/datasets/detect/open-images-v7/),
   conferindo origem/licença.
2. Guardar localmente em `models/` (`*.pt` é ignorado). Não carregar `.pt` de
   origem desconhecida: a desserialização de modelos é uma fronteira de confiança.
3. Registrar o SHA-256 produzido no relatório e a origem exata do artefato.
   Hash local identifica o arquivo; sozinho não comprova autenticidade.
4. Vídeos autorizados ficam fora do Git. Registrar consentimento/permissão,
   cenário, condições e limitações antes de compartilhar. Não baixar e publicar
   vídeo de terceiros presumindo licença livre.

Ultralytics usa [AGPL-3.0](https://github.com/ultralytics/ultralytics/blob/main/LICENSE);
o projeto é AGPL-3.0-only. O wrapper
[opencv-python é MIT](https://github.com/opencv/opencv-python/blob/4.x/LICENSE.txt)
e [lap é BSD-2-Clause](https://github.com/gatagat/lap/blob/master/LICENSE).
Preservar avisos das dependências e dos componentes nativos/transitivos nas
distribuições. Licença do repositório não relicencia pesos ou vídeos; futuras
imagens Docker/bundles (#28) precisam incluir os avisos aplicáveis.

## Benchmark reproduzível

```sh
# Imagens pretas geradas em memória: latência/smoke, não acurácia.
python -m sonar_vision.benchmark --weights models/yolov8n.pt \
  --frames 60 --output results/v8-blank-01.json

# Vídeo local autorizado; não abre janela nem grava imagens.
python -m sonar_vision.benchmark --weights models/yolo26n.pt \
  --video videos/cenario-autorizado.mp4 --frames 100 \
  --output results/v26-video-01.json

# Segunda etapa opcional de escadas; mede custo de dois pesos no mesmo processo.
python -m sonar_vision.benchmark --weights models/yolov8n.pt \
  --stair-direction-weights models/stairs-up-down-v3.pt \
  --frames 60 --output results/stairs-two-models-01.json
```

Repita alterando apenas os pesos para comparar. Warmup padrão: cinco frames;
carregamento do modelo não integra latência. P50/P95 usam nearest-rank;
FPS efetivo = frames medidos / tempo corrido (inclui decode, sem renderização).
O relatório v2 também inclui P99, CPU do processo, pico de RSS e tempo de
leitura/decodificação de vídeo local. CPU usa um núcleo como base; pico de RSS
inclui carga do modelo e warmup. Nenhuma dessas métricas é latência de rede.
Não confundir com média de FPS instantâneo, FPS do vídeo ou capacidade da nuvem.
Relatórios incluem versões, hash, resolução, parâmetros e limitações, sem
caminho do vídeo, imagens ou históricos de IDs. Arquivo existente não é sobrescrito.
Em EOF/falha de decode, o relatório distingue interrupção do limite de frames,
mas OpenCV não permite distinguir de forma confiável EOF de falha de leitura.

Consulte [evidências e limites da #21](experiments/issue-21.md) e
[ADR 0004](decisions/0004-modulo-visual-por-sessao.md). O
[perfil exploratório da #22](experiments/issue-22.md) registra o plano para
medir ponta a ponta quando API e cliente estiverem funcionais.
