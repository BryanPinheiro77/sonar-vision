# Evidências da issue #21 — módulo visual

Data: 2026-09-19. Execução assistida por IA, responsável humano Bryan.
Resultados de engenharia, não validação de segurança, identidade ou colisão.

## Procedimentos disponíveis a todos

- `python -m unittest discover -s tests -v`: cenários determinísticos, incluindo
  ByteTrack real sobre caixas sintéticas quando instalado `.[vision]`.
- `python -m sonar_vision.benchmark --frames 100 --output results/scripted-01.json`:
  backend simulado, sem ML. Não interpretar seu throughput como desempenho YOLO.
- `python -m sonar_vision.benchmark --weights models/yolov8n.pt --frames 60 --output results/v8-blank-01.json`:
  YOLO/ByteTrack reais sobre 640×480 preto em memória, 5 frames de warmup.
  Todos conseguem gerar essa entrada sem acesso ao laboratório ou vídeos privados.
- Para conteúdo real, usar vídeo autorizado conforme #7 e os comandos do
  [guia](../vision.md). Isso não requer disponibilizar mídia de participantes no Git.

## Verificações desta entrega

26 testes passaram com dependências de visão instaladas: 22 do núcleo/métricas
e 4 do adaptador ByteTrack real. Sem dependências opcionais, os 22 do núcleo
passam e os 4 do adaptador são explicitamente ignorados (skipped).
Pacote wheel construído e instalado em diretório temporário; não é release.

Cobertura de cenários: classes multiclasse/unknown, caixas e confiança inválidas,
IDs ausentes, aparecimento, perda, recuperação, expiração, reentrada com ID novo,
histórico limitado, reset, fechamento, timeout ocioso, duas sessões/dispositivos,
ordem de frames, regressão de relógio, falha parcial, capacidade e rejeição Busy.
Teste real intercala trackers e introduz um segundo alvo após iniciar outra sessão:
isso verifica que o contador do primeiro não é reiniciado pelo segundo.

Não é prova de boa associação em oclusões reais. Nos testes com caixas, as
trajetórias são deliberadamente simples e conhecidas.

## Medições locais desta entrega

Ambiente reportado: macOS 27.0 arm64, Python 3.14.7, CPU, Ultralytics 8.4.137,
OpenCV 4.14.0.94, lap 0.5.13, torch 2.13.0, numpy 2.5.2.
Parâmetros: imgsz=640, conf=0.35, ByteTrack buffer=60; demais parâmetros no guia.
Cinco frames de warmup excluídos; sem janela, sem rede, sem salvamento de imagens.

| Entrada | Modelo | Frames medidos | Latência média | P50 | P95 | FPS efetivo |
|---|---|---:|---:|---:|---:|---:|
| Preto sintético 640×480 | YOLOv8n | 60 | 20.01 ms | 19.56 ms | 22.30 ms | 49.97 |
| Trecho local de cruzamentos 2160×3840 | YOLOv8n | 100 | 19.98 ms | 19.52 ms | 22.04 ms | 44.59 |
| Mesmo trecho local | YOLO26n | 100 | 19.64 ms | 19.21 ms | 21.90 ms | 44.98 |

O trecho real corresponde aos primeiros 105 frames do vídeo que Bryan já
forneceu para testes, com FPS de origem aproximado de 30.0036. Não foi publicado;
portanto essas duas linhas são evidência local, **não benchmark público de
acurácia reproduzível sem obter o mesmo vídeo**. A reprodução pública do fluxo
usa entrada sintética; protocolo/dataset compartilhável permanece na #7.
Não comparar diretamente o FPS de vídeo decodificado sem renderização com o
loop gráfico antigo do laboratório. Não são medições de latência ponta a ponta.

Hashes dos pesos locais, para identificar os artefatos medidos (não atestado de origem):

- YOLOv8n: `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.
- YOLO26n: `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.

Relatórios JSON completos ficam em `results/` local, ignorado no Git. Comandos
geram novos relatórios sem sobrescrever arquivos existentes. Esta síntese não
contém frames, trajetórias individuais, caminhos pessoais nem credenciais.

## O que aproveitamos do laboratório

Relatórios de 2026-09-12: mesmo vídeo completo, 415 frames medidos e 5 de warmup,
CPU, conf=0.35, entrada 640 e ByteTrack buffer=60, Ultralytics 8.4.137.

| Modelo | FPS efetivo do loop antigo | Inferência média | Inferência P95 |
|---|---:|---:|---:|
| YOLOv8n | 17.217 | 19.874 ms | 21.691 ms |
| YOLO26n | 17.328 | 19.918 ms | 24.631 ms |

Bryan observou continuidade do ID 30 em um cruzamento com YOLO26n. É observação
qualitativa de um alvo, não métrica global de ID switches. Os logs não têm
identidades anotadas para IDF1/HOTA. Mais IDs ou maior confiança não demonstram
melhor tracking. Por isso o módulo aceita ambos os modelos, sem eleger vencedor.
Não copiamos o estimador monocular de risco do lab para o módulo de produção.

## Pendências fora da #21

- #7: dataset/protocolo controlado, anotação de identidades e avaliação de baixa luz.
- #11: trajetória aparente e direção, sem prometer convergência física.
- #16: detector de escadas e subida/descida; não implementado por pesos COCO.
- #22: repetição/variabilidade, CPU/GPU, concorrência e dimensionamento AWS.
- #24/#27: autenticação, integração HTTPS, cancelamento, falhas e teste ponta a ponta.
- Hardware e segurança assistiva: não testados nesta entrega.
