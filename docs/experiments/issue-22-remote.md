# #22 — cliente separado e preparação do benchmark AWS

Data: 2026-10-07. Responsável: Bryan, com apoio de IA. Procedimento experimental,
sem aceite final de capacidade. Decisão: [ADR 0016](../decisions/0016-benchmark-remoto-temporario.md).
Orçamento temporário aprovado; conta Free plan criada, IAM autenticado e VM temporária provisionada.
Veja o [guia de primeiro acesso](../aws-start.md).

## Dependências e objetivo

A #52/PR53 está na main e integra YOLO geral + R20/áudio explícito. O PR50
contém o executor de carga oferecida e ainda não foi mergeado. A preparação
foi feita em checkout separado, combinando localmente `adb0d2b` (main/PR53)
e `2a58ed3` (PR50), sem commit do merge local. Relatórios marcam checkout dirty;
não apresentar essa combinação como versão já entregue à main.

O executor antigo cria servidor e cliente no mesmo processo. O novo
`sonar_vision_integration.remote_load` reutiliza `run_load` e `DeviceClient`
contra uma API HTTPS operada separadamente. Não provisiona recursos nem muda
fila, timeouts, contrato, limiares ou modelos. CPU/RAM do cliente não são
CPU/RAM da VM. Entrada preencodificada não mede câmera/encode nem acurácia.

## Perfil para preparar a medição

- YOLOv8n geral e especialista R20 congelados/hash conferido; confiança0,35,
  imgsz640 e CPU preservados conforme [perfil da #52](integration-52-r20.json).
- Áudio habilitado por configuração explícita da #52; diagnóstico de caixas
  desligado na sondagem de desempenho, registrar essa escolha.
- Oferta de trabalho autorizada:10/s e ≥8 admissões/s por dispositivo como meta
  de trabalho local. Os demais percentis/limites e o protocolo final de três
  repetições de dez minutos permanecem propostas, não aceite físico.
- Um envio ativo por credencial; dois dispositivos exigem tokens distintos,
  com fases alinhadas/espaçadas e resultados por dispositivo. Não ocultar busy
  sob uma taxa agregada.

## Execução do cliente fora do servidor

Na máquina do cliente, instalar os extras de API/dev. A geração de imagem
preta exige também `vision`; com JPEG autorizado já preencodificado via
`--image`, não carrega modelos no cliente.

```sh
python -m pip install -e '.[vision,api,api-dev]'
mkdir -p .local/benchmark
chmod 700 .local/benchmark
# Operador fornece arquivo privado só com o token, sem compartilhar pelo chat.
PYTHONPATH=src python -m sonar_vision_integration.remote_load \
  --endpoint https://localhost:8443 --ca-file .local/tls/ca.pem \
  --device-id bench-01 --token-file .local/bench-01.token \
  --fps 10 --warmup 30 --duration 600 --output .local/benchmark/one.json
```

O endpoint é a URL base, sem `/v1/inference`, query, fragmento ou senha. CA
pública usa trust store padrão omitindo `--ca-file`; não há opção insecure.
Para a VM, `localhost` representa um túnel montado pelo operador ou use o
endpoint HTTPS real. Registre qual caminho foi usado.

Duas credenciais:

```sh
PYTHONPATH=src python -m sonar_vision_integration.remote_load \
  --endpoint https://localhost:8443 --ca-file .local/tls/ca.pem \
  --device-id bench-01 --token-file .local/bench-01.token \
  --device-id bench-02 --token-file .local/bench-02.token \
  --fps 10 --warmup 30 --duration 600 --phase staggered \
  --output .local/benchmark/two.json
```

Warmup é separado e serial por dispositivo, seguido de sessão nova; não mede
carga concorrente do aquecimento. `--image` repetido e `--source-id` permitem
corpus privado autorizado. Nenhum JPEG/token/URL/caminho do corpus entra no
JSON; recibos e identificadores de sessão continuam privados (modo600).
O relatório conserva tentativas, oportunidades não capturadas, erros, respostas
concluídas dentro da oferta, taxas incluindo espera final e recursos do cliente.
`acceptance_evaluated=false` permanece até aprovar o protocolo final.

## Coleta no servidor e correlação

No host Docker da API, amostrar apenas o contêiner alvo:

```sh
python scripts/sample_container.py --container CONTAINER_ID \
  --duration 700 --output .local/server-resources.jsonl
```

CPU de100% equivale a um núcleo; dividir pelo limite explícito `NanoCpus` do
contêiner para percentual da capacidade. Sem limite conhecido, esse percentual
fica null. RAM reportada por
[`docker stats`](https://docs.docker.com/reference/cli/docker/container/stats/)
no Linux exclui cache: não é RSS do processo. Registrar também RAM do host,
OOM/restarts e início em AWS, não concluir margem de memória só pelo ensaio curto.
A frequência efetiva depende do tempo do coletor e é registrada; não prometer
uma amostra exata por segundo.

Exportar `docker logs CONTAINER_ID > server.log 2>&1` pelo operador. O
`--server-log` opcional no cliente associa somente as linhas JSON
`inference_request` que coincidam em dispositivo autenticado/sessão/frame.
Mostra registros ausentes; rejeita duplicados. Os tempos de decode/inferência/
política/encode/work/total são durações do servidor, não timestamps subtraídos
entre máquinas. Esse arquivo pode ser associado depois da carga pela função
`attach_server_log(report, Path(...))`; não precisa copiar log durante cada frame.

Não chamar a diferença entre duração HTTPS e trabalho do servidor de RTT puro:
elas têm escopos distintos e incluem transferência/TLS/validação/escalonamento.
Guardaremos hashes/configuração/versões do servidor por acesso de operador,
sem criar endpoint público de debug.

## Sondagem local executada

API CPU em Docker Desktop, imagem da #52 com geral+R20, limite de2 CPUs e4GiB;
cliente em outro processo macOS, HTTPS loopback; entrada preta640×480. Três
cargas de15s a10/s, warmup2s por dispositivo. Não representam EC2/Intel/Flex,
Wi-Fi, sustentação de10 minutos ou custos reais de cenas com objetos. Docker
com quota pode expor mais CPUs lógicas que a quota e não simula uma VM de2vCPUs.

| Dispositivos/fase | Admitidas/s dentro da oferta, por cliente | P95 inferência servidor | Tentativas busy |
|---|---|---|---:|
| 1/alinhada | 4,93 | 194,26ms | 0 |
| 2/alinhada | 2,13 / 2,73 | 193,24ms | 149 |
| 2/espaçada | 2,93 / 0,93 | 468,98ms | 140 |

75/223/198 tentativas foram correlacionadas aos logs sem ausências. Os valores
não cumprem a meta de trabalho8/s por cliente. Espalhar os inícios não demonstrou
divisão justa. Não reduzir confiança/timeouts nem assumir GPU com esse resultado.

As séries de27s tiveram14 amostras cada e incluem warmup/trechos ociosos; não
são CPU média sustentada da janela. Máximos observados da capacidade2CPUs:
64,945% /66,675% /61,015%; uso Docker de RAM máximo:9,25–9,36% dos4GiB.
Isso não comprova margem de início nem adequação do host AWS. Relatórios,
logs e séries completos estão em `.local/remote-smoke/`, privados.

## Estado da verificação

336 testes locais passaram com extras de visão/API e peso geral real, zero
skips. Novos testes cobrem HTTPS externo, destinos inválidos, credenciais
separadas, relatórios sem segredos e associação de logs com ausências/duplicados.
Docs/Ruff passaram na preparação. A primeira VM CPU foi criada na AWS; resultado
e remoção serão registrados após a execução. A coleta de métricas não controla vibração; independência tátil simulada
continua nos testes, hardware não validado.

## Primeiro ensaio AWS em andamento

`c7i-flex.large`, sa-east-1, Ubuntu24.04 oficial, 2vCPUs/4GiB, root20GB gp3
criptografado com exclusão na terminação. Container limitado a2CPUs/3GiB,
reservando memória para o sistema operacional; esse limite difere dos4GiB
da sondagem Docker Desktop. Fonte da API: main/PR53 `adb0d2b`, sem alterações
do cliente experimental no servidor. Imagem construída na VM com o Dockerfile
do projeto e extras `api,vision`. TLS de teste confiado explicitamente sobre
túnel SSH, porta da API publicada somente em loopback. Chave SSH de host aceita
na primeira conexão e fixada em arquivo privado (TOFU), sem verificação
independente por console. Não desabilitar verificação nas conexões seguintes.

O temporizador de120min foi verificado no sistema, e shutdown da instância
está configurado para terminate. A limpeza manual ao terminar continua
necessária para chave pública e security group; o temporizador não os remove.
Nenhum certificado, token, endereço de operador ou identificador da conta
entra nos relatórios públicos.

### Suspensão do cliente — rodada inválida

A primeira rodada de600s monotônicos atravessou suspensão do Mac: os logs
de energia confirmaram Sleep/DarkWake e a série do cliente mostrou uma pausa
de115s de UTC com menos de2s monotônicos. Seus1,49fps,178timeouts e13expirações
não são evidência de capacidade em rede nominal; relatório privado foi
separado como inválido. A rodada seguinte foi interrompida pelo mesmo motivo.
A VM permaneceu saudável, sem OOM/restart; não atribuir os atrasos à CPU.

A repetição usa `caffeinate -dims -t 2400` no cliente macOS, com tampa aberta.
Isso impede suspensão por inatividade durante o ensaio, mas não garante
operação com tampa fechada. O relatório compara os intervalos UTC/monotônicos
das amostras locais: diferença maior que1s marca `continuous=false`; sem
duas amostras marca null. Suspensão e ajuste do relógio são indistinguíveis
por esse controle. Trata-se de integridade experimental, sem alterar os
timeouts, validade dos frames ou contrato da API.

## Atualização autorizada: R21 e HTTPS direto

Bryan selecionou explicitamente o r21 como candidato de escadas para a AWS,
com geral preservado, r20 para rollback e sem mudança de API/contrato.
[Perfil e hashes](issue-22-r21-profile.json); manifesto privado conferido.
O169/177 informado pelo handoff é avaliação local conhecida/de desenvolvimento,
não resultado AWS nem aceite independente. Novos vídeos entram primeiro na
avaliação do candidato fixo; classificar falhas de modelo, compressão, tracking,
rede ou latência. Novo treino exige falhas de modelo e exemplos aprovados;
cenas reservadas para avaliação independente ficam fora do treino.

Após corrigir suspensão, uma rodada r20 de600s teve590admissões,64timeouts,
2expirações e3315falhas de conexão. Continuidade do relógio foi true
(diferença máxima0,037s), mas o túnel SSH encerrou por timeout. Essa é evidência
de falha de transporte, não capacidade nominal nem comparação r20/r21.
A repetição seguinte foi impedida pela checagem de saúde antes da carga.

Para isolar o túnel, o ensaio r21 passou a HTTPS direto na porta8443:
security group permite apenas IPv4 do operador/32, e TLS valida certificado
com SAN do endereço da VM e CA privada confiada explicitamente. Tokens seguem
obrigatórios; nenhuma regra0.0.0.0/0 de entrada. O Compose da VM publica a porta
em0.0.0.0, limitado externamente por esse grupo. Isso é configuração temporária
do benchmark, sem entrega da topologia permanente da#23. API/fonte/contrato
continuam `adb0d2b`; só pesos, TLS e publicação da porta foram reconfigurados.

Contêiner recriado, samplers reiniciados com ID concreto do novo contêiner.
Não combinar a identidade/CPU/RAM do contêiner anterior com as séries r21.
O r20 e a CA/relatórios anteriores foram preservados privadamente. A limpeza
remove também a regra8443 ao excluir o grupo próprio do benchmark.

## Encerramento

Ensaios e limpeza concluídos: [resultado consolidado](issue-22-aws-results.md).
Não selecionar esta capacidade para o deploy permanente: a meta8/s não foi
atingida. 337testes passaram, zero skips; hardware/avaliação independente
continuam pendentes. Sem recursos próprios ativos após reconsulta AWS.

## Conclusão atual em08/10/2026

O encerramento acima descreve a CPU2 histórica. A CPU4 posterior atingiu
≥8/s em três600s; Bryan aprovou o perfil experimental revisado80/150ms.
[Conclusão atual](issue-22-conclusao.md), [ADR0018](../decisions/0018-dimensionamento-cpu-um-oculos.md)
e [reprodução sem caminhos privados](issue-22-reproduce.md). O histórico
permanece identificado; aceite não valida captura física outracking independente.
