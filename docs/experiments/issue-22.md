# Issue #22 — perfil local e plano de dimensionamento

Data: 2026-09-26. Estado: medição exploratória local; dimensionamento da VM
pendente. Responsável humano pela revisão: Bryan. Estes números não são metas
aprovadas, teste da AWS nem validação do protótipo vestível.

## O que já pode ser medido

O benchmark do módulo da #21 executa YOLOv8n/ByteTrack sem janela. O relatório
JSON `schema_version: 2` registra ambiente, versões, hash dos pesos,
configuração, frames de aquecimento, duração, FPS efetivo, média/P50/P95/P99
do processamento, tempo de leitura e decodificação de vídeo local (quando
usado), tempo de CPU do processo e pico de RSS. CPU em porcentagem usa um núcleo
como base e pode passar de 100%. O pico de RSS inclui carga do modelo e warmup,
não é série temporal nem consumo de toda a máquina.

Para repetir com artefatos obtidos conforme o [guia de visão](../vision.md),
na raiz do repositório, use o ambiente com `.[vision]` instalado:

```sh
PYTHONPATH=src python -m sonar_vision.benchmark \
  --weights models/yolov8n.pt --frames 60 \
  --output results/issue22-v8-blank-01.json
PYTHONPATH=src python -m sonar_vision.benchmark \
  --weights models/yolov8n.pt --video videos/cenario-autorizado.mp4 \
  --frames 100 --output results/issue22-v8-video-01.json
```

Use nome novo para cada repetição; o programa não sobrescreve resultados.
Registre separadamente commit (`git rev-parse HEAD`), modelo exato de máquina,
RAM, temperatura/estado térmico se houver medidor confiável, alimentação,
outros processos relevantes, origem/permissão do vídeo, resolução, FPS de origem,
iluminação, cenário, duração e motivo de parada. Não publique vídeo, identidades,
caminhos pessoais nem pesos. Um vídeo privado impede terceiros de reproduzirem
o **mesmo conteúdo**; a entrada sintética permite repetir o procedimento, mas
não mede precisão ou custo de cenas reais.

## Medição exploratória em 2026-09-26

MacBook Air Mac17,3, Apple M5 (10 núcleos), 16 GB RAM, macOS 27.0 arm64,
Python 3.14.7, CPU. Ultralytics 8.4.137, OpenCV 4.14.0.94, lap 0.5.13,
torch 2.13.0, numpy 2.5.2. YOLOv8n com SHA-256
`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`,
obtido previamente no laboratório local; origem de obtenção indicada no guia.
Entrada 640, confiança 0,35, ByteTrack buffer 60; demais parâmetros no JSON.
Cinco frames de warmup excluídos; a carga do modelo ficou fora da latência.
Estado térmico e carga de fundo **não foram medidos**. `pmset -g therm` não
forneceu dados nesta máquina. Portanto, estes valores descrevem apenas as
execuções observadas, sem conclusão de capacidade sustentada.

| Entrada | Repetições × frames | Processamento médio por execução | P95 por execução | FPS efetivo por execução | CPU do processo | Pico RSS |
|---|---:|---:|---:|---:|---:|---:|
| Preto sintético 640×480 | 3 × 60 | 21,18 / 22,16 / 21,82 ms | 21,84 / 25,04 / 24,04 ms | 47,22 / 45,12 / 45,82 | 243 / 237 / 240% de um núcleo | 414 / 415 / 417 MiB |
| Vídeo local autorizado | 3 × 100 | 19,39 / 19,67 / 19,91 ms | 20,65 / 21,08 / 21,66 ms | 49,53 / 48,81 / 48,23 | 250 / 248 / 246% de um núcleo | 485 / 490 / 484 MiB |

No vídeo, a leitura/decodificação local teve média de 0,80 / 0,81 / 0,82 ms.
O vídeo é o arquivo local já usado na #21, não publicado; seu conteúdo e
proveniência precisam ser revisados antes de compartilhar evidência derivada.
Os relatórios completos das três execuções com imagem preta estão disponíveis
em [01](issue-22-blank-01.json), [02](issue-22-blank-02.json) e
[03](issue-22-blank-03.json). Eles contêm métricas e configuração, sem imagens,
caminho local ou identidades. Os relatórios do vídeo permanecem em `results/`,
ignorado pelo Git. A tabela é uma síntese revisável, mas não permite reprodução
idêntica das três linhas de vídeo sem o mesmo arquivo autorizado. Não comparar
estas execuções curtas com
latência em nuvem ou com câmera ao vivo. O FPS inclui decodificação quando há
vídeo, mas não captura física, codificação de upload, rede ou resposta.

## Ensaio exploratório HTTPS com detector real — 2026-10-06

O cliente da #30 leu 24 frames de um vídeo **sintético original** (480×360,
retângulo branco móvel em fundo preto, 15 FPS), identificado como
`generated-rectangle-2026-10-06`. A API HTTPS de loopback da #27 usou
YOLOv8n/ByteTrack com os pesos locais de SHA-256 já registrado acima.
Ambiente: macOS 27.0.1 arm64, Python 3.11.16, CPU, Ultralytics 8.4.137.
`--video`, `--source-id` e o procedimento de repetição estão em
[integração](../integration.md). O [relatório completo revisado](issue-6-loopback-synthetic.json)
identifica o commit `2a70931`, checkout limpo, hash da fonte, pesos e configuração;
não contém vídeo, token nem caminho do arquivo.

Para gerar novamente a fonte sintética, use o ambiente com o extra `vision`:

```sh
python - <<'PY'
from pathlib import Path
import cv2
import numpy as np
path = Path("results/issue6/synthetic-moving-rectangle.mp4")
if path.exists():
    raise SystemExit("Escolha outro caminho para preservar a entrada existente")
path.parent.mkdir(parents=True, exist_ok=True)
writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15, (480, 360))
assert writer.isOpened()
try:
    for index in range(36):
        frame = np.zeros((360, 480, 3), dtype=np.uint8)
        cv2.rectangle(frame, (30 + index * 5, 90), (110 + index * 5, 230), (255, 255, 255), -1)
        writer.write(frame)
finally:
    writer.release()
PY
```

Essa fonte é criação própria (`AGPL-3.0-only`), sem pessoas ou material externo.
A codificação pode variar entre versões de OpenCV/FFmpeg; o relatório registra
o hash da entrada efetivamente usada, sem exigir bytes idênticos em outra máquina.

Sem aquecimento, a primeira requisição excedeu 1500 ms (503), e as 11
seguintes receberam `busy` enquanto o trabalho continuava. Após aquecer o
modelo **antes** de abrir o servidor, 24/24 requisições foram admitidas (HTTP
200). Na repetição revisada, a ida e volta incluindo leitura/codificação do
frame teve média 21,78 ms, P95 22,89 ms e P99 26,64 ms; captura até decisão no
simulador teve média 21,67 ms e P95 23 ms. A inferência registrada pelo
servidor teve média 19,73 ms e P95 20,95 ms. O processo consumiu 119% de um
núcleo em média **incluindo inicialização** e atingiu pico de RSS de 470 MB; esse pico cobre
carga/aquecimento do modelo e não é memória sustentada por frame.

O vídeo não contém classes reais para avaliar detecção, tracking, trajetória
ou escadas. O loopback não mede Wi-Fi, AWS, câmera, captura do sensor ou
feedback físico. Uma requisição sequencial por dispositivo não mede carga
concorrente. Estes números não definem instância, orçamento ou meta aprovada.

## Próximas medições da #6/#22

Usar identificador de sessão/frame para correlacionar eventos, sem registrar
imagem. No **cliente**, medir com relógio monotônico: captura, codificação,
envio, espera, recebimento e decisão de aceitar/descartar; medir captura até
resposta como intervalo ponta a ponta no mesmo relógio. No **servidor**, medir
recebimento, validação/decodificação, admissão/espera (se houver), inferência e
serialização/envio da resposta. Relógios de máquinas distintas não devem ser
subtraídos diretamente; juntar durações por frame. Se não houver fila, registrar
espera zero e contagem de `Busy`/descarte, sem inventar tempo de fila.

Registrar média, P50/P95/P99 e máximo por etapa, FPS recebido/processado,
bytes por frame, CPU/RAM durante a carga, erros e descartes por causa:
vencimento desde captura (1000 ms no perfil experimental), resposta fora de
ordem, `Busy`, timeout e falha de rede. Enviar **no máximo uma requisição ativa
por dispositivo**, variar número de dispositivos e taxa oferecida, e repetir
com rede degradada. A captura usa relógio do dispositivo; o servidor não deve
decidir validade usando timestamps de relógios não sincronizados. Registrar
efeito sobre feedback tátil local separadamente, com rede/VM indisponíveis.

Antes da avaliação final, o grupo deve aprovar metas quantitativas, cenários,
quantidade de repetições e carga concorrente. A recomendação de começar com
três execuções por cenário é apenas procedimento exploratório, não critério
de aceite aprovado.

## Capacidade, custo e decisão ainda pendentes

Usar o perfil local e o teste ponta a ponta para estimar CPU/RAM necessários
por dispositivo e por carga simultânea, com margem baseada na variabilidade
observada. Comparar CPU/GPU somente se a CPU não atender às metas aprovadas;
registrar região, tipo de instância, versão do modelo e hipótese de carga.
Não extrapolar diretamente o Mac M5 para AWS.

Planilha/registro de custo deve ter data, moeda e links das fontes para:
computação (horas e cobrança por desligamento), disco/snapshots, tráfego de
entrada e saída, IP/endereço e serviços auxiliares realmente usados. Calcular
custo por hora de teste e mês na carga prevista, com limites de gasto. O grupo
deve aprovar orçamento e autorização **antes** de provisionar qualquer recurso
pago; registrar desligamento, exclusão de volumes/snapshots e verificação de
cobrança residual. Nenhum recurso pago foi criado nesta etapa.

Após os testes e a aprovação das metas, registrar a escolha, alternativas,
limitações e procedimento de repetição em ADR. Ainda não existe base para
escolher instância, região, GPU ou orçamento final.

O módulo visual e este benchmark não controlam a vibração. O alerta tátil
local no ESP32-S3 deve permanecer independente da câmera, rede e VM; isso
continua pendente de verificação em hardware.
