# Reteste com rede estável — #22

Data: 08/10/2026 UTC (07–08/10 em São Paulo). Responsável: Bryan, com apoio de IA.
Status: medições concluídas e recursos removidos; não é aceite de segurança,
tracking ou implantação permanente.

## Atualização de aceite em08/10/2026

Bryan aprovou explicitamente a revisão80ms/150ms(P95),250ms(P99),≥8/s
para a etapa experimental. [Conclusão](issue-22-conclusao.md) e
[ADR0018](../decisions/0018-dimensionamento-cpu-um-oculos.md). O texto abaixo
preserva as propostas históricas e o resultado original; não prova capturaESP
ou tracking independente.

## Resultado

Um óculos simulado, oferta de 10 JPEGs/s, uma requisição ativa, sem fila nem
retransmissão. YOLO geral + candidato r21, execução paralela dos dois modelos,
um thread intraop por modelo, CPU4 São Paulo. API e contrato preservados.
O runner é experimental e explícito; o padrão serial do produto permanece.

| Ensaio | Duração medida | Admissões/s | Inferência P95 | HTTPS P95 | CPU média / 4 vCPU |
|---|---:|---:|---:|---:|---:|
| r1 | 600 s | 8.292 | 74.49 ms | 143.97 ms | 28.55% |
| r2 | 600 s | 8.385 | 73.95 ms | 142.17 ms | 28.37% |
| r3 | 600 s | 8.427 | 73.95 ms | 141.44 ms | 28.82% |
| corpus-A | 60 s | 9.900 | 59.91 ms | 80.78 ms | 26.70% |
| corpus-B | 60 s | 9.950 | 63.14 ms | 86.80 ms | 27.61% |

As três repetições de 600 s, cada uma após 30 s de aquecimento separado,
atingiram a meta de trabalho de pelo menos 8 admissões/s. Zero falhas nas
tentativas, zero logs faltantes, continuidade de relógio confirmada e zero
reinícios/OOM. As oportunidades descartadas antes da captura por cliente ocupado
foram 1025/968/944 entre 6000 por rodada; não são tentativas bem-sucedidas.
Na R2 houve 5032 respostas admitidas ao todo, das quais 5031 dentro dos 600 s;
a taxa estrita reportada usa somente essas 5031.

**Atingir FPS não satisfaz todas as metas de latência propostas.** Nos ensaios
longos, o trabalho do servidor teve P95 de 74,7–75,3 ms (proposta ≤70 ms), e
captura sintética até admissão P95 de 141,7–144,3 ms (proposta ≤100 ms).
P99 da captura sintética até admissão ficou entre 152,4 e 155,3 ms, abaixo da
proposta de 250 ms. Captura e codificação físicas não estão incluídas.
Não alterar validade, timeout, compressão ou critérios para fazer o ensaio passar.

Clipes A/B: 16 JPEGs pré-codificados por vídeo autorizado, repetidos durante
60 s; não são três repetições sustentadas com cenas reais nem avaliação de
tracking. Proporção/tamanho do tensor e dos JPEGs diferem do sintético preto:
não atribuir a diferença de taxa somente à presença de objetos.

## Qualidade e limites

177/177 casos conhecidos receberam resposta admitida. **169/177 corretos**,
com as mesmas oito falhas: N05-s06, D063, D023-lance-distante,
D063-lance-distante, L20-04, L20-05, NV-01, NV-03. Não houve novo treino.
Esses casos incluem dados de desenvolvimento e não medem acurácia independente.
O teste confirma o resultado do conjunto conhecido, não igualdade bit a bit
com cada resultado de outra plataforma.

RAM máxima do contêiner nas rodadas longas: 383359386 bytes (~366 MiB),
excluindo cache de arquivos segundo Docker; não é RSS nem pico do host.
CPU média de 28,4–28,8% da capacidade de quatro vCPUs. Sem série de RAM/steal
do host: somente snapshots de memória inicial/final. Não concluir desempenho
contínuo de dias a partir de 30 minutos, especialmente para CPU Flex.

A rede foi declarada estável pelo operador e as tentativas reais foram sem
falhas. HTTPS mede transporte, TLS, servidor e validação; não é RTT puro.
As medidas anteriores com rede instável continuam no histórico.

## Custo e remoção

Nova VM: 0.673 h, aproximadamente
US$0.182 de compute/IP/disco. Total dos
ensaios até aqui: **3.751 h e US$0.719**
de compute/IP/disco, dentro de 8 h/US$15 aprovados.

Estimativa de catálogo, não fatura: exclui impostos e eventual tráfego pago;
contador TX foi obtido antes da última exportação. Créditos contam como consumo.
Saldo US$120 foi informado por Bryan, não conferido via API de cobrança.

Prazo automático de 100 minutos + comportamento EC2 terminate; encerramento
manual após exportação às 03:13:37 UTC. Auditoria: instância terminated,
zero volumes, zero chaves SSH e zero grupos de segurança residuais do ensaio.
Nenhuma VM foi deixada ligada para preparar documentação.

## Evidência e próxima etapa

- [Configuração, hashes, versões e medidas](issue-22-stable-aws-cpu.json).
- [177 casos conhecidos](issue-22-stable-known.json).
- [Custo e auditoria de limpeza](issue-22-stable-cost.json).
- [Auditoria final de todos os recursos próprios da #22](issue-22-final-resource-audit.json).
- [Catálogo de preço consultado](issue-22-stable-pricing.json).
- [Perfil r21 e rollback r20](issue-22-r21-profile.json).
- [Histórico CPU4 com rede instável](issue-22-cpu4-results.md).
- [Procedimento remoto reproduzível](issue-22-remote.md).

Preparar o runbook da #23 e validações operacionais locais. Deploy permanente,
alertas reais de cobrança e publicação por PR ainda não foram concluídos.
ESP/OV2640, rede da apresentação, avaliação independente e vídeos anotados de
tracking permanecem pendentes. O caminho tátil local é independente da nuvem
por arquitetura; sua execução física ainda não foi validada.
