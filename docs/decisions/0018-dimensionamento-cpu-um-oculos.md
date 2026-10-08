# ADR0018 — dimensionamento CPU para um óculos

- Data: 08/10/2026.
- Status: decisão experimental aprovada por Bryan em08/10/2026; entrega por PR revisado.
- Responsável: Bryan, com apoio de IA.
- Issue: [#22](https://github.com/BryanPinheiro77/sonar-vision/issues/22).

## Contexto e evidência

A #22 seleciona infraestrutura para a inferência remota antes da operação da#23.
O usuário confirmou um único óculos. ESP/câmera ainda indisponíveis; o computador
simula uma requisição ativa com JPEG pronto, sem fila ou retransmissão.

[CPU2](../experiments/issue-22-aws-results.md) atingiu4,94–5,00 admissões/s
em três600s com geral+r21. Mais threads ou paralelizar emCPU2 não atingiram8/s.
[CPU4 com rede estável](../experiments/issue-22-stable-results.md), paralelo1,
atingiu8,292/8,385/8,427 em três600s, oferta10/s, warmup30s separado.
Inferência P95 de73,95–74,49ms; trabalho do servidor74,71–75,28ms;
JPEG pronto até admissão P95 de141,71–144,29ms e P99 de152,43–155,31ms.
Sem falhas por tentativa, logs faltantes, suspensão, restart ouOOM.

CPU Docker média28,37–28,82% de4vCPUs e RAM máxima383359386bytes,
excluindo cache. Memória do host foi conferida em snapshots, sem série temporal
completa ou pico de início. Não afirmar desempenho de dias nem calibração física.

## Decisão aprovada para a etapa experimental

Selecionar **c7i-flex.xlarge,4vCPU/8GiB, sa-east-1**, para a próxima etapa
experimental de um óculos. Docker limita API a4vCPU/3GiB, preservando RAM ao SO.
YOLO geral+r21,CPU,FP32,confiança0,35,imgsz640,IoU0,50,upload até640,JPEG95.
Executar os modelos em paralelo com intraop1 pelo runner experimental explícito;
o padrão serial da API não recebe as medidas deste runner. R20 para rollback.

São Paulo foi a região efetivamente medida. Virgínia teve comparação de preço,
sem benchmark de rede: não afirmar que uma é mais rápida pelo mapa.
GPU/Edge não têm necessidade demonstrada para a meta de trabalho de8/s.
ManterCPU2 como resultado comparativo rejeitado para essa carga, não como fallback
que preserva o mesmo FPS. Modelos, classes, qualidade JPEG,API/contrato, prazo de
validade e timeouts são preservados.

## Metas aprovadas explicitamente em08/10/2026

As propostas anteriores70ms/100ms **não foram satisfeitas** nas rodadas longas.
A tabela abaixo é revisão de orçamento de desempenho informada pelas medições,
preparada em08/10/2026; não reclassifica testes antigos como protocolo congelado
antes da medição. Não muda limiares de risco físico ou validade do contrato.

| Medida / escopo | Revisão proposta | Resultado medido |
|---|---:|---:|
| Admissões por óculos, oferta10/s, uma requisição ativa | ≥8/s em3×600s | 8,292–8,427/s |
| Trabalho no servidor (decode+inferência+política+encode; sem upload) | P95≤80ms | 74,71–75,28ms |
| JPEG pronto no computador até admissão no mesmo relógio | P95≤150ms | 141,71–144,29ms |
| JPEG pronto até admissão | P99≤250ms | 152,43–155,31ms |
| Falhas por tentativa | ≤5%, drops pré-captura separados | 0%; drops1025/968/944 |

Bryan respondeu: “Aprovo esse perfil e as metas revisadas para a etapa experimental”.
[Registro de aprovação](../experiments/issue-22-approved-profile.json). As três
rodadas atendem este perfil revisado; não atendem o anterior. O aceite é
explicitamente posterior às medidas exploratórias, sem nova rodada apresentada
como validação prospectiva. Metas originais permanecem oportunidades de melhoria.

Captura/codificação físicas ficam para os testes deESP/OV2640; não chamar esta
meta de150ms de sensor→resultado. Definir orçamento próprio desses estágios
quando houver medição. Tracking/trajectória requerem casos independentes
anotados; avaliar nas issues#11/#7. Qualidade conhecida de escadas169/177,
mesmas oito falhas, não é taxa de acurácia independente.

## Custo e operação

[Teto temporário](../experiments/issue-22-aws-budget.json):US$15 deconsumo,
inclusive créditos, até8horas somadas. Paid plan foi autorizado separadamente
após incompatibilidade do tipoCPU4 comFree plan. Saldo foi informado pelo dono,
não certificado pela API de cobrança. Nenhum orçamento mensal está aprovado.

Preço registradoCPU4:US$0,26135/h; IPv4US$0,005/h; gp3São PauloUS$0,152/GB-mês.
Um root20GB ativo apenas durante o ensaio, mês estimado de720h, implica
aproximadamenteUS$0,27057/h antes de tráfego/impostos. São estimativas datadas,
não garantia de fatura. [Custo consolidado](../experiments/issue-22-final-cost.json)
inclui hipóteses explícitas de tráfego, recursos e limites da medição.

Vários ensaios terminaram com remoção manual, além de prazo automático deVM.
[Auditoria](../experiments/issue-22-final-resource-audit.json): zero recursos
próprios ativos/parados, discos, chaves eSG. Operação temporária da#23 deve
respeitar esse teto remanescente; implantação mensal exige orçamento próprio.

## Alternativas e consequências

- CPU2 custa menos, mas não sustenta a cadência atual com ambos os modelos.
- CPU4 serial/outros números de threads não reproduziram a taxa do paralelo1.
- channels_last não melhorou o ensaioCPU2; não adotá-lo sem prova naCPU4.
- Reduzir imagem/compressão/confiança ou remover o modelo especialista muda
  o perfil e exige avaliação; não é comparação equivalente.
- Dois clientes não são requisito confirmado; resultados históricos de
  contenção não entram no aceite de um óculos.

A nuvem oferece semântica/tracking, sem controlar vibração ou risco local.
A indisponibilidade nunca pode bloquear o caminho tátil. Esse isolamento foi
exercitado em simulação, não validado fisicamente noESP.

## Entrega e limitações

[Conclusão e critérios da#22](../experiments/issue-22-conclusao.md) e
[reprodução sem caminhos privados](../experiments/issue-22-reproduce.md).
Medições registradas são exploratórias com entrada sintética/quadros autorizados;
a liberação experimental pode usar a evidência existente após aceite explícito,
sem apresentar revisão posterior como validação prospectiva independente.

Publicação por PR revisado, acesso legítimo aos pesos pelo grupo permanecem requisitos de entrega. O perfil e as metas acima já foram aprovados. Este ADR não declara produção,
segurança física ou conclusão das issues de hardware/qualidade visual.
