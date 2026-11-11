# ADR 0006 — avaliação offline contra referências anotadas

- Data: 2026-10-02.
- Status: proposta implementada como ferramenta na #33; critérios não aprovados.
- Responsável previsto: Matheus (@Matheus-xz), com apoio de IA.
- Revisão: Bryan e responsáveis pelo protocolo #7.
- Referências: #7, #21, #30, #33 e ADR 0001/0003.

## Contexto

Contagens do detector e IDs do tracker não medem acurácia, pessoas reais ou
segurança. Benchmark e contrato 0.1 não transportam referências/caixas suficientes
para avaliação anotada. A #33 pede relatório reproduzível, falhas por condição e
revisão de identidade; limiares/amostras da #7 ainda estão pendentes.

## Proposta

Snapshot local versionado mantém manifesto #7, configuração, modelo, frames,
referências anotadas, predições e intervalos de latência no mesmo relógio.
Não altera mensagens 0.1 nem caminho tátil/áudio. Biblioteca padrão Python,
sem detector/banco/serviço novo.

Associar por classe e IoU configurável, maximizando primeiro cardinalidade e
depois soma de IoU com Hungarian. Ordem de entrada resolve empate. Política de
invisibilidade/ignore e continuidade é declarada no snapshot e descrita no guia.
São propostas de avaliação, não decisões experimentais aceitas pelo grupo.

Relatar TP/FP/FN e denominadores, grupos, escadas e abstenções. Revisar IDs por
referência dentro de clip/epoch/segmento, sem contagem de pessoas ou métricas MOT
padronizadas inventadas. Falhas/timeout participam das contagens e tempos.
Comparar versões somente sobre as mesmas capturas, anotações e convenções.

JSON/eventos ficam em results/; síntese pública somente agregada em
docs/experiments. Não copiar boxes/IDs/configuração livre para Markdown.
Proveniência/permissões e independência da anotação exigem revisão humana.

## Alternativas consideradas

- Associação gulosa pela maior IoU: simples, mas pode perder correspondências
  válidas em cenários com múltiplos alvos; solver ótimo tem custo limitado pela
  capacidade explicitada da ferramenta e testes de força bruta independentes.
- Inferir métrica a partir de eventos lost/recovered ou quantidade de IDs:
  não compara à referência e confunde reinício/oclusão com identidade real.
- Instalar ferramenta externa de AP/MOT: útil futuramente, mas demanda protocolo
  e dependências; esta entrega cobre contagens/latência e diagnóstico explícito,
  sem alegar AP/mAP/IDF1/HOTA.
- Publicar resultados por frame: pode revelar trajetórias/identidades; síntese
  agregada separada e revisão privada atendem à análise sem expor dados brutos.

## Consequências e limites

Nenhum limiar de risco, parâmetro de firmware ou formato de rede mudou.
IoU/cutoff/gap/mínimo da fixture não aprovam avaliação final. Grupo deve revisar
e congelar regras/amostras antes do teste independente da #7.
Integridade/declarações não comprovam licença, qualidade das anotações,
independência física nem relógios corretos. Sem dados reais ou validação física.
