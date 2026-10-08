# Reproduzir o benchmark externo da #22

Data:08/10/2026. Um óculos simulado, JPEG pronto, HTTPS validado, geral+r21.
Perfil aprovado em [ADR0018](../decisions/0018-dimensionamento-cpu-um-oculos.md).
Este documento não exige caminhos absolutos de uma máquina nem executa provisionamento.

## Artefatos e responsabilidade

Obter checkout revisado desta entrega e instalar Python≥3.11/extras existentes:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[vision,api,api-dev]'
```

O servidor medido usouPython3.12/AMD64Ubuntu24.04; clientePython3.11/macOS.
Versões resolvidas e hashes estão no [relatório](issue-22-stable-aws-cpu.json).
Código-base da API `adb0d2bfd617e077801b98e20a74b375dcd23457`; os runners e cliente
experimental foram executados a partir do checkout modificado com hashes registrados.

Pesos fora do Git/imagem: geral oficial e especialistaR21 pelo responsável,
com instruções/hashes no [perfil](issue-22-r21-profile.json) e
[releases](../releases.md). Não substituirR21 pelo peso públicov3 e chamar a
medição de repetição equivalente. O handoff privado deve usar nomes relativos
`models/general.pt` e `models/stairs-r21.pt`, manifesto e origem/licença.
O responsável pode compartilhar legitimamente esse pacote com o grupo;
redistribuição pública deR21 não foi autorizada nesta entrega. Os vídeos não são
necessários para repetir o perfil sintético; clipes/casos conhecidos requerem
origem e autorização próprias, preservando conjuntos independentes fora do treino.

## Preparar endpoint temporário aprovado

Preparar conta/perfil conforme [primeiro acessoAWS](../aws-start.md). Antes de
novaVM, atualizar preço, autorização e ledger acumulado, conferir orçamento
US$15/8h, tipoCPU4, região e identidadeIAM. A instância deve ter IMDSv2 obrigatório,
root20GBgp3 criptografado eDeleteOnTermination, encerramento do SO emterminate,
SSH22/HTTPS8443 somente IP autorizado/32 e nenhum ingressoIPv6 irrestrito.
Registrar todos os recursos próprios e remover ao terminar. Administração nunca
fica aberta à internet inteira. Conferir host keySSH por canal confiável.

Instalar prazo100min antes de iniciar o serviço; verificar timer naVM e não
estender a janela por reboot. Configuração e histórico de encerramento no
[ADR0016](../decisions/0016-benchmark-remoto-temporario.md). O provisionador
compartilhado é entrega da#23; o benchmark não pede infraestrutura permanente.

NaVM, obter a imagem doDockerfile `api,vision`, base imutávelAMD64 registrada no
relatório e código escolhido. Registrar oID imutável da imagem e `pip freeze`.
Os builds não têm lockfile transitivo; imagem/conjunto de versões exatos são
parte da comparação, não garantia de rebuild idêntico pelo mesmo commit.

Diretório privado do operador (`umask077`) contémTLS, hashes de tokens, modelos
e runner. TLS deve terSAN localhost+endereço daVM, CA confiada explicitamente
pelo cliente e chave0600 legível somente pelo usuário numérico do contêiner.
A CA gerada por `dev_tls` é somente desenvolvimento/laboratório. Um token por
óculos, sem plaintext no Git/chat/logs; servidor armazena apenasSHA-256.

Exemplo de execução **naVM preparada**, com arquivos privados já obtidos:

```sh
export BENCH_PRIVATE="$PWD/.local/bench"
export BENCH_CONTAINER=sonar22-one-device
# BENCH_IMAGE_ID é sha256 completo da imagem já construída/carregada/verificada.
docker run -d --name "$BENCH_CONTAINER" --init --restart=no \
  --cpus=4 --memory=3g --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges \
  --user "$(id -u):$(id -g)" --publish 0.0.0.0:8443:8443 \
  --log-opt max-size=10m --log-opt max-file=3 \
  --mount "type=bind,src=$BENCH_PRIVATE/tls,dst=/run/sonar/tls,readonly" \
  --mount "type=bind,src=$BENCH_PRIVATE/tokens,dst=/run/sonar/tokens,readonly" \
  --mount "type=bind,src=$BENCH_PRIVATE/models,dst=/models,readonly" \
  --mount "type=bind,src=$PWD/scripts/benchmark_parallel_api.py,dst=/run/sonar/parallel.py,readonly" \
  --env SONAR_API_BACKEND=ultralytics \
  --env SONAR_API_TOKENS_FILE=/run/sonar/tokens \
  --env SONAR_API_WEIGHTS=/models/general.pt \
  --env SONAR_API_WEIGHTS_SHA256=f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36 \
  --env SONAR_API_STAIR_WEIGHTS=/models/stairs-r21.pt \
  --env SONAR_API_STAIR_WEIGHTS_SHA256=449aecd65557e18a982a4c3ab6a33c7a7e41020b7f368b4305db4a1823607813 \
  --entrypoint python "$BENCH_IMAGE_ID" /run/sonar/parallel.py --threads 1
```

A publicação0.0.0.0 é protegida peloSG/32, não autorização para abrir firewall.
Não usarroot no contêiner. O runner exige ambos os modelos e registra threads
efetivos. Aquecer os preditores antes da concorrência; API umprocesso/slotglobal.
Confiança0,35/imgsz640/IoU0,50; não alterar contrato, validade ou timeout.

## Coleta do servidor e cliente

NaVM, salvar identidade e iniciar coletor em terminal separado antes do piloto:

```sh
mkdir -p .local/bench-results
docker inspect "$BENCH_CONTAINER" > .local/bench-results/container-inspect.json
python scripts/sample_container.py --container "$BENCH_CONTAINER" \
  --duration 2400 --interval 1 --output .local/bench-results/resources.jsonl
```

Não remover/recriar o contêiner durante as rodadas. `docker stats` pode levar
cerca de1–2s; o relatório usa tempos efetivos, não promete amostragem1Hz.
CPU é dividida pela quota explícita; RAM Docker exclui cache, não éRSS dohost.

No cliente, configurar `BENCH_ENDPOINT` para o endpointHTTPS privado de operação.
`BENCH_TOKEN`/`BENCH_CA` são caminhos locais, não strings de segredo. Saída em
pasta privada existente. O comando abaixo usa JPEG preto original640×480 gerado
pelo executor, sem mídia pessoal. Verificar byte/hash contra o relatório.

```sh
mkdir -p .local/bench-results
PYTHONPATH=src python -m sonar_vision_integration.remote_load \
  --endpoint "$BENCH_ENDPOINT" --device-id glasses-01 \
  --token-file "$BENCH_TOKEN" --ca-file "$BENCH_CA" \
  --fps 10 --duration 60 --warmup 30 --output .local/bench-results/pilot.json
```

Continuar só se piloto atingir8admissões/s, zero falhas e continuidade true.
Executar o mesmo comando três vezes com `--duration 600 --warmup 30`, cada um com
arquivo novo `r1.json`, `r2.json`, `r3.json`. Não sobrescrever falhas, repetir
silenciosamente casos ou selecionar a melhor tentativa. Uma resposta drenada
após a janela não entra na taxa estrita dentro dos600s.

Mac: manter tampa aberta e `caffeinate -dimsu -t 2400` em terminal separado.
CompararUTC/monotônico; suspensão invalida carga nominal. Não executar testes
locais pesados durante a carga. A rede precisa ser registrada; falha de acesso
SSH não comprova queda da API. Conferir resultados remotos antes de duplicar testes.

Exportar naVM, após a carga e antes de remover o serviço:

```sh
docker logs "$BENCH_CONTAINER" > .local/bench-results/server.log 2>&1
docker logs --timestamps "$BENCH_CONTAINER" > .local/bench-results/server-timestamps.log 2>&1
docker inspect "$BENCH_CONTAINER" > .local/bench-results/container-inspect.json
```

Transferir pelo canal autenticado para a pasta privada do cliente. Não publicar
logs brutos: contêm identificadores de dispositivo/sessão/frame. Eles não devem
conter tokens ou imagens. Por padrão não ativar diário de predições.

## Agregação pública e verificação

```sh
PYTHONPATH=src python scripts/summarize_remote_benchmark.py \
  --report .local/bench-results/r1.json \
  --server-log .local/bench-results/server.log \
  --server-timestamps .local/bench-results/server-timestamps.log \
  --resources .local/bench-results/resources.jsonl \
  --container-inspect .local/bench-results/container-inspect.json \
  --output .local/bench-results/r1-public.json
```

RepetirR2/R3 e comparar o [perfil aprovado](issue-22-approved-profile.json).
O agregador não decide aceite global: exporta percentis, perdas e recursos,
sem endpoint/token/path/IDs privados. Excluiwarmup por timestamps **do servidor**
e duração registrada nele; não cruza relógios cliente/servidor. Rejeita
contêiner/imagem/limites incompatíveis, duplicatas ou conjuntos de requisições
diferentes entre log simples e timestampado. A métricaHTTPS inclui rede/TLS/
cliente/servidor; não éRTTpuro nem medição de captura/codificação doESP.

O agregador público foi conferido contra as três rodadas já executadas:
percentis do servidor e CPU/RAM reproduzidos exatamente. Dados de origem,
licenças, modelos e cenário devem acompanhar qualquer nova repetição.

## Encerramento e custos

Exportar, parar/remover o contêiner próprio e terminar aVM pelo operadorAWS.
ConferirDeleteOnTermination e remover apenas volumes, chavesSSH eSG identificados
pelas tags/ledger da rodada. Não basta stop; disco ocioso pode cobrar.
Registrar hora e resíduos; o timer não apaga chaveSSH/SG. Não tocar em recursos
alheios. [Auditoria final](issue-22-final-resource-audit.json) e
[custo consolidado](issue-22-final-cost.json) mostram a limpeza dos ensaios atuais.

Captura física, sensores, qualidade independente de tracking e feedback tátil
não são validados por esses comandos. A falha da VM não comanda ou bloqueia
vibração; confirmar a independência física na etapa de hardware.
