# #22 — comparação CPU4 e diagnóstico de rede

07/10/2026. Responsável: Bryan, com apoio de IA. **Rodada encerrada, VM
terminada e recursos temporários removidos. A #22 permanece aberta:** não
houve aceite de desempenho externo sustentado nem deploy permanente.

## Perfil

São Paulo, c7i-flex.xlarge,4vCPU/8GiB nominais, Intel Xeon Platinum8488C,
Ubuntu24.04,20GB gp3 criptografado/DeleteOnTermination, IMDSv2. Expiração
configurada100min após bootstrap; remoção manual antes dela. Contêiner API
4CPU/3GiB, mesmo digest Python/pacotes e builder main/PR53 `adb0d2b` do CPU2.
Geral+r21, confiança0,35, imgsz640, IoU0,50, FP32, max-det300, upload
max-edge640/JPEG95. R20 preservado localmente. Sem treino, nova classe,
alteração da API/contrato ou firmware. [Perfil/hashes](issue-22-r21-profile.json).

Paid autorizado explicitamente por Bryan, concluído pelo proprietário no
console após a CLI operacional receber AccessDenied. Free plan bloqueou o
lançamento real com InvalidParameterCombination; IAM DryRun tinha passado.
Bryan confirmouUS$120 ainda no console; saldo não foi lido pela API.
[Preflight](issue-22-cpu4-preflight.json). Quota16vCPU, sem ampliação de quota.

## HTTPS externo

Cliente Mac separado, oferta10/s, warmup30s por dispositivo, janelas60s,
TLS/CA verificados e tokens distintos; acesso limitado ao IPv4 do operador/32.
Um envio por dispositivo, um frame global na API, sem fila. ClipeA/B:
16JPEGs selecionados por origem, gravados/autorizados por Bryan, proporção
preservada; dimensões diferentes do preto640×480. Não mede captura/encoding.

| Ensaio | Admissões/s por dispositivo | P95 inferência | P95 chamada HTTPS |
|---|---:|---:|---:|
| auto-pilot | 4.817 | 98.89ms | 207.20ms |
| serial1-pilot | 4.733 | 121.15ms | 212.04ms |
| parallel-pilot | 6.950 | 64.89ms | 171.36ms |
| two-aligned | 4.100 / 4.250 | 69.20ms | 235.17ms / 239.11ms |
| two-staggered | 3.867 / 4.567 | 72.11ms | 198.53ms / 187.66ms |
| selected-corpus-A | 5.317 | 55.26ms | 252.42ms |
| selected-corpus-B | 4.417 | 56.71ms | 319.44ms |
| parallel2-pilot | 5.467 | 69.85ms | 249.08ms |

Paralelo com1thread por modelo foi o candidato do piloto; nenhum perfil
externo atingiu8admissões/s. Três rodadas600s externas não iniciadas, conforme
o gate exploratório. Relógios contínuos e nenhum log de desempenho ausente.
Nos pilotos de um dispositivo, nenhuma falha por tentativa; oportunidades
perdidas por cliente ocupado ficam registradas. Dois dispositivos tiveram
295/402busy nos ensaios alinhado/espaçado. Não comprova justiça ou8/s por óculos.

CPU média no piloto paralelo:20,27% da capacidade4vCPU; RAM Docker máxima
380423373bytes, sem cache, não RSS. Threads efetivas do automático após
warmup:3 no builder/worker; serial1:1 no worker. Paralelo verifica a contagem
em cada predição. Mais threads não melhoraram o piloto. Rede variou entre
rodadas; não atribuir todas as diferenças ao número de threads. Checagens
locais podem sobrepor parte do piloto auto; resultados são exploratórios.
[Agregados/pacotes/contadores/fontes](issue-22-cpu4-aws-cpu.json).

## Evidência do caminho de envio

Bryan relatou internet intermitente. No melhor perfil, P95 de leitura do corpo
foi120,19ms no clipeA e197,87ms noB, enquanto inferência foi55,26/56,71ms.
Na avaliação conhecida, dois envios leram o corpo em1527,13/1614,45ms e foram
rejeitados por deadline_before_admission, antes de executar o modelo. Outras
respostas200 expiraram na validação do cliente. Não aumentar timeouts/validade
silenciosamente nem tratar rejeição de transporte como falha de treinamento.

IP público oscilou; regras próprias22/8443 foram atualizadas e voltaram ao
IPv4 diretamente observado, sem abertura geral. SSH ficou interrompido na
entrega de resultados; arquivos completos dentro da VM foram recuperados.
Isso não transforma medição local em medição externa válida. Nenhuma
subtração de timestamps entre hosts ou estimativa de RTT puro foi usada.

## HTTPS dentro da VM

Diagnóstico: mesmo backend paralelo1, modelos e JPEGs, cliente em contêiner
isolado com rede host, HTTPSlocalhost/CA verificada. CPU/RAM do host são
compartilhadas por cliente e servidor: não substitui cliente externo. Única
biblioteca de cliente instalada em volume privado: httpx2==2.13.1 já declarada
no extra api-dev; imagem e dependências da API não alteradas.

| Fonte | Admissões/s | P95 inferência | P95 chamada HTTPS |
|---|---:|---:|---:|
| black | 9.917 | 69.11ms | 73.11ms |
| A | 10.000 | 60.56ms | 64.70ms |
| B | 10.000 | 64.88ms | 69.76ms |

Todas as tentativas desses três ensaios foram admitidas, relógios contínuos,
zero logs ausentes. Preto595admissões/60s; clipes600/60s cada, limitados à
oferta10/s. Apenas pilotos60s/30s warmup: **não três repetições sustentadas**
e não hardware/rede vestível aceitos. Mostra capacidade nesse laboratório e
reforça o efeito do caminho externo; não promete10/s em toda cena/rede.
Retomada redundante deB foi interrompida após localizar o original completo;
o arquivo original foi preservado e somente seus recibos foram correlacionados.
[Agregados/limitações](issue-22-cpu4-loopback.json).

## Modelo e entrega são avaliados separadamente

Controle serial1 e candidato paralelo1 tiveram **169/177 acertos de predição**
no critério congelado, mesmas oito falhas conhecidas, sem regressão observada.
Esse número inclui diagnósticos privados de respostas que chegaram tarde e
foram corretamente rejeitadas pelo cliente; não significa177entregas válidas.
Controle:175/177admitidas,2expired,167matches corretos admitidos. Paralelo1:
174/177admitidas,3expired,166matches corretos admitidos.
[Detalhamento](issue-22-cpu4-aws-known.json).

Paralelo2:173admitidas,2expired,2unavailable por deadline antes da inferência.
Modelo avaliado em175casos,167corretos, mesmas oito falhas;D064/D067 não
avaliados nesse modo por falha de upload. Sem regressão do modelo observada
nos casos com diagnóstico, com duas pendências explícitas nesse perfil
rejeitado para seleção. [Detalhamento](issue-22-cpu4-parallel2-known.json).

Referências de desenvolvimento161train/16val, não acurácia independente.
Igualdade exata de floats pode variar conforme CPU/configuração. Tracking,
movimento físico, risco, wearable, áudio/háptico no hardware não validados.

## Reprodução e verificação

[Procedimento externo/coleta](issue-22-remote.md),
[ADR](../decisions/0016-benchmark-remoto-temporario.md),
[runner de threads](../../scripts/benchmark_threads_api.py) (`--threads auto|1`)
e [runner paralelo](../../scripts/benchmark_parallel_api.py) (`--threads 1` ou `--threads 2`).
Montar runner somente leitura em `/run/sonar`, usar entrypoint no override
experimental. Separar sampler por ID concreto e exportar logs antes de cada
recriação. Padrão do produto inalterado. Hashes dos operadores inicial/novo
ficam separados no agregado; cliente externo é checkout dirty main+PR50.

Diagnóstico local: mesmo ID da imagem, `--network host --cpus 4 --memory 3g
--user 1000:1000 --read-only --tmpfs /tmp --cap-drop ALL
--security-opt no-new-privileges`, cliente com módulos atuais somente leitura
viaPYTHONPATH e httpx2 em volume separado. Usar o mesmo CLI remote_load com
endpoint https://localhost:8443, CA/token privados e parâmetros idênticos.
Resultados600linhas/opções por origem permanecem privados; agregados no Git.

339testes passaram sem skips antes da última opção de thread; depois dela,
os dois testes de propriedade/falha do paralelo passaram novamente. Lint,
documentação e diff conferidos. Predições reais acima complementam a
verificação dos operadores. Nenhum commit/push/merge nesta rodada.

## Orçamento e recomendação

Rodada CPU4: aproximadamenteUS$0.219 de VM/IP/disco; agregado das
rodadas aproximadamenteUS$0.537, antes de impostos/tráfego. Tempo agregado
3.078h de8h, tetoUS$15 incluindo créditos. Tráfego do host medido até
antes da última exportação; saldo/isenção mensal e fatura não conciliados.
[Cálculo e remoção auditada](issue-22-cpu4-cost.json).

**Manter CPU4+paralelo1 como candidato experimental. Próximo passo: repetir
HTTPS externo com rede estável e os mesmos parâmetros**, prolongando três600s
quando o piloto atingir o gate. A rede precisa ser validada antes da decisão
permanente da#23. Não há evidência que exija GPU, CPU maior ou novo treino.
Se necessário investigar compressão/transporte, registrar hipótese e conferir
qualidade antes de alterar o perfil congelado. Metas finais, capacidade por
óculos, avaliação independente e hardware continuam pendentes na#22.
O alerta tátil local permanece independente da VM; firmware não foi alterado.

Conferência global posterior não concluída: sessão CLI expirou depois da
remoção auditada em23:30UTC. Nenhum recurso criado desde a remoção. Para a
próxima rodada, renovar `aws login --profile sonar-vision` e repetir preflight.
