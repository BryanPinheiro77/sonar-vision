# Conclusão experimental de dimensionamento — #22

Data:08/10/2026. Responsável:Bryan, com apoio de IA.
**Parte técnica concluída para o perfil experimental aprovado. A entrega por
PR revisado precede o fechamento da issue.**

## Decisão

Usar **c7i-flex.xlarge,4vCPU/8GiB emSãoPaulo**, um óculos, geral+r21 e
runner paralelo1 explícito. CPU2 não atingiu a cadência proposta com dois modelos.
Três rodadas externas de600s: **8,292 /8,385 /8,427 admissões/s**, oferta10/s,
warmup30s separado, zero falhas por tentativa. As perdas pré-captura por ocupado
continuam publicadas; nenhuma fila/retransmissão foi adicionada.

Bryan aprovou explicitamente o perfil e as metas revisadas em08/10:
trabalho no servidorP95≤80ms, JPEG pronto→admissãoP95≤150ms/P99≤250ms e≥8/s.
[ADR0018](../decisions/0018-dimensionamento-cpu-um-oculos.md) e
[aprovação](issue-22-approved-profile.json). O aceite das medidas exploratórias
é posterior e transparente; não é protocolo prospectivo congelado antes delas.
As metas anteriores70/100ms não foram atendidas e continuam no histórico.

## Critérios da issue e evidências

| Critério #22 | Evidência / estado nesta entrega |
|---|---|
| CPU/RAM/FPS/médias e percentis, hardware/aquecimento/modelo/carga | [CPU4 estável](issue-22-stable-aws-cpu.json),CPU2 ecomparações históricas; RAMDocker semcache, memóriahost emsnapshots |
| Estágios, descartes e uma requisição ativa | percentis read/decode/inferência/política/encode/work/total; duraçãoHTTPS no cliente, drops antes da captura separados; captura física eRTTpuro não medidos |
| Alternativas, região e carga | CPU2/CPU4 serial/paralelo/threads/memoryformat; SãoPaulo realmente medido; GPU/Edge semnecessidade demonstrada; doisclientes históricos fora do requisito atual |
| Custo de computação/disco/rede/associados | [ledger e sensibilidades](issue-22-final-cost.json), preços datados/hash, tráfego com e semfranquia; estimativa nãofatura |
| Orçamento antes do gasto e limpeza | US$15/8h autorizados, Paidplan aprovado separadamente, [auditoria semresíduos](issue-22-final-resource-audit.json) |
| Decisão emADR com limites/repetição | ADR0018 e [procedimento de reprodução](issue-22-reproduce.md) |
| Documentação e índices | relatório consolidado, JSONs de evidência, índice de docs e ADRs |
| PR revisável / evidência acessível ao grupo | checkout de entrega e pacote de reprodução preparados para PR revisado; pesos legítimos pelo handoff do responsável |
| Sem credenciais/dados/weights noGit; origem/licença | executores e agregados semsegredos, peso geral oficial+R21 privado comhash/manifesto; mídia permanece privada |

Não extrapolar os resultados paraESP/OV2640 ou uso vestível. A ausência de
hardware não exige fingir tempo de capturazero; o escopo aceito começa noJPEG
pré-codificado. O núcleo tátil local permanece independente da nuvem por
arquitetura/teste simulado; sua execução física fica para as issues de firmware.

## Desempenho, qualidade e custo

| Medida | Rodada1 | Rodada2 | Rodada3 | Limite aprovado |
|---|---:|---:|---:|---:|
| Admissões/s dentro da janela | 8,292 | 8,385 | 8,427 | ≥8 |
| Trabalho servidorP95(ms) | 75,281 | 74,716 | 74,709 | ≤80 |
| JPEG pronto→admissãoP95(ms) | 144,289 | 142,460 | 141,712 | ≤150 |
| JPEG pronto→admissãoP99(ms) | 155,309 | 152,880 | 152,427 | ≤250 |
| Falhas por tentativa | 0 | 0 | 0 | ≤5% |

Zero clocks descontínuos, logs faltantes, OOM/restarts. RAMDocker máxima~366MiB
na carga; não é pico de coldstart oumemória total dohost. CPUmédia~28,4–28,8%
dos4vCPUs; não prova sustentação de dias nem margens de hardware.

169/177casos conhecidos corretos, mesmas oito falhas. Não é acurácia
independente nem prova de identidade/tracking real. ClipesA/B atingiram9,90/9,95/s,
mas somente60s por clipe e tensor/aspecto diferentes; não substituir os3×600s.

Consumo acumulado deVMs: **3,751h**, compute/IP/disco estimados **US$0,719**.
Tráfego não foi medido completamente: sensibilidade explícita de1GB porVM,
quatroVMs, custa atéUS$0,60 **nesse cenário** sem franquia restante; total de
cenárioUS$1,319 antes deimpostos. Comfranquia suficiente, subtotalUS$0,719.
Esse cenário não é limite superior medido de tráfego nem fatura certificada.
Créditos contam como consumo; saldo foi informado pelo proprietário.

## Continuação

Após publicação/revisão, o dimensionamento experimental permite a etapa#23
com esse perfil, HTTPS/credenciais/limites/saúde/rollback/remoção, respeitando o
saldo dehoras/teto dos testes. Não aprova serviço mensal permanente.
A captura física será benchmarkada com oESP e a rede real deuso. A avaliação de
tracking/qualidade e as falhas conhecidas continuam nas issues#11/#16/#7;
novos vídeos entram primeiro no candidato fixo, sem treino automático.
