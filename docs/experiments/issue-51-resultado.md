# Resultado do piloto de cadeiras e mesas — #51

Data: 2026-10-06, horário local. Responsável: Bryan.
[Especificação aprovada](issue-51-piloto-moveis.md),
[ADR 0014](../decisions/0014-piloto-cadeiras-mesas.md),
[issue #51](https://github.com/BryanPinheiro77/sonar-vision/issues/51).

## Execução e decisão

Bryan aprovou a execução com “segue entao”. Uma rodada CPU completou 20 épocas;
checkpoint escolhido pela validação A: época 14, fitness 0,32885. Em empate,
a versão instalada sobrescreve best.pt: as épocas 10–14 tiveram a mesma melhor
fitness, e foi usada a última, conforme o callback e o CSV conferidos.
Seu SHA-256 foi congelado antes de executar o candidato no local B:
`f1452684ad27008a5a196f4d87e8dc19bb03e2bc9cfe56804c9634bdce1cbfcc`.

**Candidato rejeitado.** A rodada foi entregue, mas a meta de recuperar mesas
sem perder cadeiras não foi atingida. O detector geral da API permanece igual;
não há novo mapeamento table/dining_table, integração ou promoção do peso.
O caminho tátil do ESP32-S3 continua independente e inalterado.

| Detector, no B a confiança 0,35 | Cadeiras associadas / 4 | Mesas associadas / 4 | Previsões de móvel sem associação |
|---|---:|---:|---:|
| Baseline YOLOv8n | 3 | 0 | 0 |
| Candidato da época 14 | 0 | 0 | 0 |
| Meta aprovada do piloto | ≥3 | ≥2 | ≤1 |

No candidato, as quatro capturas não produziram qualquer detecção acima do
corte 0,35. Isso significa quatro FN de cadeira e quatro FN de mesa, não
caminho livre. Zero extras não compensa a perda de todos os alvos.
A baseline repetiu o resultado anterior nas mesmas capturas: perda de cadeira
aos 2 s, acerto aos 6/10/14 s, nenhuma mesa.

A validação usada pelo treinador no A teve métricas diferentes do diagnóstico
operacional. O sufixo `(B)` no CSV da biblioteca indica **bounding boxes**,
não o local de comparação B. Seu mAP agregado/seleção de fitness não substitui
a associação a confiança fixa 0,35 no local B. A qualidade do piloto não foi
aprovada só porque a métrica de validação parecia favorável.

## Configuração e recursos

Treino: antigo, 9 capturas/32 caixas; validação: A, 4/8; comparação: B, 4/8.
Classes internas: chair/table. YOLOv8n inicial verificado, Ultralytics 8.4.137,
CPU, imgsz 640, batch 4, seed 42, workers 0, AdamW, lr0 0,001, patience 20.
Configuração efetiva e augmentations constam no [agregado](issue-51-resultado.json).
Validação A escolheu o checkpoint; B não foi usado para early stopping ou tuning.

Mac arm64 / Apple M5, dez CPUs lógicas, Python 3.11.16, torch 2.14.1.
Tempo de treino/inicialização/finalização da biblioteca: 22,32 s. CPU média
da execução inteira (treino + comparação) foi 28,17% normalizada pelas dez CPUs;
pico de RSS 1494,375 MiB desde início do processo, incluindo carregamento,
treino, warmup e modelos de comparação. Não extrapolar para dataset maior/AWS.

| Detector | Inferência média | P50 | P95 |
|---|---:|---:|---:|
| Baseline | 19,02 ms | 18,41 ms | 20,90 ms |
| Candidato | 17,40 ms | 17,36 ms | 17,58 ms |

Quatro amostras por detector, cinco frames pretos de warmup excluídos, somente
inferência offline. P95 nearest-rank equivale ao máximo com quatro amostras.
Não é ensaio sustentado, rede, API, tracking ou câmera. Nenhuma conclusão de
melhoria robusta de latência ou capacidade foi tomada.

## Procedimento histórico e reprodução condicionada

Instalar os extras existentes do [módulo visual](../vision.md), obter o peso
YOLOv8n conforme [releases](../releases.md), e preparar manifestos/caixas de
mídia autorizada. Os dados deste piloto permanecem privados: outra pessoa
precisa obter o mesmo lote por meio autorizado para repetir seus números.
Não inventar um dataset público equivalente a esses locais.

A única rodada autorizada já foi executada. O comando de treino abaixo registra
o procedimento histórico; **não deve ser executado novamente com a aprovação
antiga**. Nova rodada exige desenho e autorização próprios antes de usar dados.
Para revisar esta entrega, executar somente os testes do exportador.

Comando histórico, com manifesto privado no formato documentado pela ferramenta:

```sh
PYTHONPATH=src python scripts/issue51_pilot.py \
  --manifest datasets/moveis/manifesto-preparacao.json \
  --weights models/yolov8n.pt --output results/issue51/rodada-01
PYTHONPATH=src python -m unittest discover -s tests -p test_issue51_pilot.py -v
```

O manifest traz `source_annotation_hashes`, `frozen_development_reference` e
`records`: sample_id, group, image relativo, image_sha256 e labels revisados.
Os grupos fixos deste piloto são development-office-original, cena-a-local-informado-pelo-autor
e cena-b-local-informado-pelo-autor. Labels trazem physical_class, box ou
box_xyxy_normalized e approval='approved by Bryan'; são registros de revisão,
não autenticação da identidade do revisor. As fontes congeladas corroboram
as mesmas caixas antes do uso. Não adaptar outro lote renomeando seus grupos
para simular o experimento: uma nova rodada exige novo desenho.

A ferramenta rejeita fontes/caixas alteradas, labels pendentes, classe inválida,
path fora da pasta de dados, vazamento entre papéis e contagens inesperadas.
Exporta data.yaml com **apenas train/val**; evaluation B é separado.
Não sobrescreve diretório de rodada. Execução offline, auto-install desativado,
plots desativados e verificação de fonte de gráfico dispensada para evitar
seu download não utilizado; isso não muda operações do modelo.

Antes da comparação, grava checkpoint-frozen.json com epoch/hash/fitness e
hash do CSV. pilot.json privado guarda previsões e métricas; treino/labels,
fontes, logs e pesos não entram no Git. A síntese pública contém apenas
configurações, hashes, contagens e recursos; não inclui fotos ou caixas brutas.
O fingerprint de código do agregado foi registrado após a execução; o código
não mudou entre execução e esse registro. Não afirmar checkout limpo/commit
publicado para esta rodada: ferramenta e documentação foram preparadas localmente.

## Verificação e limitações

- Cinco testes novos de exportação passaram: round-trip, referência/imagem
  alterada, aprovação/caixa/classe inválida, vazamento e escape de path.
- Suíte completa: 320 testes passaram em 37,665 s, com extras e peso real,
  sem skips. Inclui o núcleo, ByteTrack real, HTTPS e independência tátil simulada.
- Ruff 0.16.10, verificação de documentação e diff passaram.
- Conferidos: 20 épocas; empate resolvido na época 14 conforme treinador;
  checkpoint congelado inalterado; pixels idênticos entre baseline/candidato;
  hashes de todas as capturas exportadas; B ausente da configuração de treino;
  nenhuma execução/modelo/captura foi excluída para melhorar as contagens.

Um único local de treino, nove capturas correlacionadas, nenhum negativo e
aprovação de caixas sem certificação de completude exaustiva. A/B já foram
abertos anteriormente; B é comparação exploratória, não teste final cego.
Não foram medidos FP em cenas vazias, tracking, trajetória, protótipo físico,
rede, AWS ou regressão de todas as classes do detector geral.

## Próxima investigação

Ampliar desenvolvimento com outros móveis/locais, vistas e negativos revisados,
revisar completude de todos os alvos e definir outra rodada antes de treinar.
Se os resultados B forem usados nessa decisão, ele continua desenvolvimento/
comparação exploratória; obter locais novos para teste final. Este resultado
não demonstra qual combinação de dados/épocas/augmentation resolverá o problema.
Não foi reduzida a confiança, prolongado o treino ou escolhido outro checkpoint
após ver B para reclassificar este candidato como aprovado.

## Conferência para incorporação — 2026-10-17

A preparação foi recuperada em checkout atual, preservando os arquivos originais
no checkout do experimento. O SHA-256 do script publicado coincide com o código
registrado após a rodada; as alterações atuais são de documentação/índices.
O histórico de 320 testes acima descreve a execução original, não a suíte atual.

[Conferência de integridade](issue-51-fechamento.json): 20 verificações passaram,
incluindo checkpoint/CSV, última época empatada, hashes das 17 imagens exportadas,
pixels das quatro imagens B, contagens e tempos do agregado e exclusão de B do
arquivo do treinador. Foi leitura dos artefatos arquivados; nenhum novo treino
ou inferência de móveis foi realizado e nenhuma mídia/peso será publicado.

A #51 pode terminar como **rodada concluída, candidato rejeitado** após revisão
e incorporação. Isso não declara a detecção de móveis resolvida: a necessidade
de dados/desenvolvimento e avaliação independente permanece vinculada à #7.

Verificação no checkout atual: **394 testes passaram em 46,08 s**, zero falhas,
erros ou skips, com extras e peso geral confiável. Os cinco testes do piloto
validam o exportador; a regressão não repete o treino nem a comparação B.
check_docs: 102 Markdown, zero problemas; Ruff e diff --check passaram.
