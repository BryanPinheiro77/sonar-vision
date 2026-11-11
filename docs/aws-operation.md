# Operação experimental AWS — #23

Data: 08/10/2026. Responsável técnico: Bryan, com apoio de IA.
Status: implementação operacional em andamento, sem implantação permanente.
A [issue #23](https://github.com/BryanPinheiro77/sonar-vision/issues/23)
autoriza o primeiro artefato operacional. A continuação foi autorizada por Bryan. [ADR0017](decisions/0017-preparacao-operacao-aws.md).

## Continuação operacional de09/10/2026

[Diagnóstico, reboot real, prazo automático e limpeza](experiments/issue-23-cadence-results.md).
As pendências operacionais de reboot/expiração foram ensaiadas; reteste longo
JPEG95/cadência padrão ficou dentro das metas desta entrada. Preservar JPEG95,
R21 e padrão periódico. Não afirmar qualidade independente ou capturaESP.
Handoff ao grupo e entrega/revisão da continuação aguardam seus critérios.

## Escopo e decisões

Reutilizar EC2, Docker Compose e API HTTPS, sem banco, dashboard, broker,
load balancer, nova dependência Python ou placa Edge. O caminho tátil local
não lê mensagens remotas para calcular risco nem depende deste serviço.

A [#22 foi concluída](experiments/issue-22-conclusao.md) com aceite
experimental aprovado: CPU4 em São Paulo, um óculos, ≥8 frames/s,
P95 de trabalho ≤80 ms e JPEG pronto até admissão P95≤150/P99≤250 ms.
As propostas anteriores de 70/100 ms continuam no histórico. Geral+R21
usam execução paralela optativa, intraop=1; o padrão serial da API não muda.
R20 continua disponível para rollback.
- `compose.aws.yaml`: execução a partir de ID imutável de imagem local,
  `pull_policy: never`, bind inicial em loopback, 4 vCPU/3 GiB, sem root,
  somente leitura, reinício limitado e logs rotacionados.
- `compose.aws.parallel.yaml`: opt-in do runner experimental da #22,
  somente para ambos os modelos, intraop=1 e hash obrigatório no preflight.
- `scripts/check_aws_release.py`: valida entradas locais sem criar recursos.
- `sonar_vision_api.token_ops`: provisão, rotação e revogação offline.
- `scripts/smoke_aws_operation.py`: ensaio operacional Docker local.

O Compose é **standalone**: use `-f compose.aws.yaml`, não acrescente à
configuração local padrão. A escolha evita mesclar publicações de portas e
build automático com a operação de uma imagem já verificada.

## Acesso e custo antes de criar qualquer VM

O perfil IAM de benchmark era limitado à etiqueta `issue-22`. O proprietário
aplica a proposta que também permite `issue-23` e leitura do console apenas
destas instâncias, para autenticar a chave SSH. O operador não edita IAM.

1. Autenticar o perfil aprovado via `aws login --profile sonar-vision` no
   navegador com o usuário IAM e MFA. Operação diária não usa root ou chaves
   permanentes. Conferir `aws sts get-caller-identity --profile sonar-vision`.
2. Conferir região `sa-east-1`, plano, saldo, cota, preço atual e orçamento.
   Até este registro, uso acumulado dos experimentos é 3,751 h; estimativa de
   compute/IP/disco US$0,719, excluindo impostos/tráfego. Autorização vigente:
   **US$15 de consumo, inclusive créditos, e oito horas somadas de instâncias**.
   Não há autorização de serviço mensal permanente.
3. Registrar ID da rodada, dono, finalidade, recursos e prazo em arquivo privado
   antes de lançar. Pré-verificar a política com DryRun; isso não garante
   disponibilidade, elegibilidade ou custo. Não repetir lançamento sem conferir
   se a tentativa anterior criou uma instância.
4. Uma única VM temporária CPU4, Ubuntu AMD64 confiável, root gp3 criptografado
   de até 20 GB, IMDSv2 obrigatório, `DeleteOnTermination=true` e
   `InstanceInitiatedShutdownBehavior=terminate`. Sem snapshots, Elastic IP,
   GPU ou serviços adicionais. Modelo de tags: Project/Experiment/RunId,
   coerentes com a política efetivamente autorizada; não reutilizar tags para
   contornar permissões de outra issue.
5. Security group próprio: SSH22 e HTTPS8443 somente IPv4 autorizado `/32`;
   nenhuma entrada IPv6 ou regra `0.0.0.0/0`. A administração não recebe acesso
   indiscriminado. SSH com chave privada local0600 e host key verificada no
   console/canal confiável. Nunca desligar StrictHostKeyChecking para recuperar
   uma conexão. Se o IP mudar, conferir o novo endereço e remover a regra antiga.
6. Instalar o prazo **antes** do serviço e confirmar a unidade/timer ativos.
   Na #23, o prazo absoluto é de 100 minutos desde a criação do ledger,
   sem renovação após reboot. A reserva conservadora é de duas horas por rodada;
   a soma autorizada prevalece.

## Provisionamento temporário compartilhado

`scripts/aws_temporary_vm.py` reutiliza AWS CLI e biblioteca padrão, sem SDK ou
Terraform adicionais. Subcomandos: `plan` (somente leitura), `launch`, `pin`
(chave SSH verificada pelo console EC2 autenticado) e `destroy`.

Arquivo de configuração **privado** (substituir placeholders; não versionar):

```json
{
  "account_id": "SEU_ID_12_DIGITOS",
  "iam_user": "sonar-vision",
  "profile": "sonar-vision",
  "region": "sa-east-1",
  "instance_type": "c7i-flex.xlarge",
  "ami_id": "AMI_CANONICAL_UBUNTU24_AMD64_VERIFICADA",
  "vpc_id": "VPC_JA_AUTORIZADA",
  "subnet_id": "SUBNET_DESSA_VPC",
  "operator_cidr": "SEU_IPV4_PUBLICO/32",
  "maximum_minutes": 100,
  "previous_instance_hours": 3.750962938333333,
  "previous_consumption_estimate_usd": 1.3186362061072463,
  "compute_usd_per_hour": 0.26135,
  "gp3_usd_per_gb_month": 0.152
}
```

Os números são o estado anterior à primeira rodada da#23, incluindo a
sensibilidade de tráfego sem franquia. **Atualizar ledger, preço e consumo antes
de cada nova rodada**, sem tratar essa configuração como cota renovável. O
provisionador reserva2h e1GB de egress para verificar os limites8h/US$15;
isso é estimativa conservadora de cenário, não teto automático da fatura.

```sh
python scripts/aws_temporary_vm.py plan --config .local/operator.json --run-dir .local/aws23-run1
python scripts/aws_temporary_vm.py launch --config .local/operator.json --run-dir .local/aws23-run1
python scripts/aws_temporary_vm.py pin --config .local/operator.json --run-dir .local/aws23-run1
```

O comando valida identidade IAM (recusa root/conta divergente), AMI oficial,
subnet/VPC, ausência de outraVM de experimento ativa/parada, orçamento e
IPv4/32. Cria uma instância com ClientToken da rodada; preserva o ledger para
não duplicar lançamento após falha. Só remove recursos com Project/Experiment/
RunId exatos e confirma que nenhum recurso residual próprio restou.

O prazo é **absoluto desde o início da rodada**, salvo em timer systemd persistente
com `OnCalendar` e `Persistent=true`. Reboot não renova os100min. Docker possui
verificação anterior à inicialização, que recusa prazo ausente/inválido/vencido.
Confirmar timer/guard na VM antes de iniciar a API. Data/hora dohost e entrega do
shutdown ainda exigem acompanhamento; o operador termina a VM ao acabar.

`pin` compara a chave ed25519 lida pelo canal AWS autenticado com o resultado
doSSH keyscan; grava `known_hosts` privado e recusa divergência. Não há fallback
para aceitar a primeira chave sem verificação. A chamada `GetConsoleOutput`
precisa da permissão de leitura restrita preparada para o proprietário.
Referência: [AWS CLI console output](https://docs.aws.amazon.com/cli/latest/reference/ec2/get-console-output.html).

Se lançamento falhar, o comando tenta limpar os recursos próprios. Se uma
etapa posterior falhar, executar `destroy` imediatamente e conferir o ledger;
não deixar VM ociosa esperando o timer. A sessão IAM precisa continuar válida
para limpeza; em falha de autenticação, reautenticar e retomar destruição.
Não apagar manualmente locks sem conferir se o operador ainda está ativo.

## Imagem e artefatos reproduzíveis

Usar um checkout revisado ou arquivo `git archive` de commit escolhido. Para
mudanças ainda não publicadas, identificar explicitamente checkout sujo e hashes;
não afirmar que o commit da main contém este procedimento ou o runner.

```sh
# No checkout aprovado; Python da máquina hospedeira não entra no contêiner.
# IMAGE_BASE é o digest AMD64 verificado da base, obtido pelo operador.
docker build --platform linux/amd64 \
  --build-arg PYTHON_IMAGE="$IMAGE_BASE" --build-arg EXTRAS=api,vision \
  --label org.opencontainers.image.revision="$SOURCE_COMMIT" \
  --iidfile .local/aws-image.id -t sonar-vision-api:aws-candidate .
export SONAR_AWS_IMAGE_ID=$(cat .local/aws-image.id)
docker image inspect "$SONAR_AWS_IMAGE_ID"
docker image save "$SONAR_AWS_IMAGE_ID" -o .local/aws-image.tar
```

Transferir o arquivo pelo canal SSH autenticado e verificar SHA-256 antes de
`docker image load`. Registrar ID, plataforma, digest da base e `pip freeze`
resolvido. O ID é imutável; rebuild com mesmo commit pode resolver dependências
transitivas diferentes, pois não existe lockfile. Não afirmar builds bit a bit
idênticos. A atualização usa um arquivo de imagem verificado, sem registry novo.
Imagem real contém Ultralytics/AGPL: disponibilizar código correspondente.

Pesos não entram na imagem ou Git. Obter geral pela origem documentada em
[visão](vision.md) e escadas pelo handoff privado do responsável; registrar
manifesto, licença/permissão e hashes do [perfil r21](experiments/issue-22-r21-profile.json).
R21 ainda não tem distribuição pública autorizada. Membros do grupo precisam
receber acesso legítimo ao artefato para reprodução; caminho privado de uma
máquina não é instrução suficiente. Guardar R20 separado, sem sobrescrevê-lo.

## Arquivos privados e preflight

Criar pasta privada fora do Git, TLS com SAN localhost e o host/IP de acesso,
chave0600 e hashes de credenciais. Uma CA privada provisionada e confiada pelo
cliente permite laboratório; o gerador `dev_tls` é somente desenvolvimento,
não emissão de certificado público. Conferir cadeia, hostname e validade no
endpoint com o cliente; o preflight só verifica par chave/certificado e CA legível.

```sh
umask 077
mkdir -p .local/aws/tls .local/aws/models
python -m sonar_vision_api.token_ops provision glasses-01 .local/aws/tokens \
  --token-file .local/aws/glasses-01.token
export SONAR_HOST_TLS_DIR="$PWD/.local/aws/tls"
export SONAR_HOST_TOKENS_FILE="$PWD/.local/aws/tokens"
export SONAR_HOST_MODELS_DIR="$PWD/.local/aws/models"
export SONAR_UID=$(id -u)
export SONAR_GID=$(id -g)
export SONAR_API_BACKEND=ultralytics
export SONAR_API_WEIGHTS_IN_CONTAINER=/models/general.pt
export SONAR_API_WEIGHTS_SHA256=f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36
export SONAR_API_STAIR_WEIGHTS_IN_CONTAINER=/models/stairs-r21.pt
export SONAR_API_STAIR_WEIGHTS_SHA256=449aecd65557e18a982a4c3ab6a33c7a7e41020b7f368b4305db4a1823607813
PYTHONPATH=src python scripts/check_aws_release.py
```

Não rodar contêiner como UID0; usar operador Linux não root com arquivos0600.
`SONAR_AWS_IMAGE_ID` deve ser ID completo `sha256:…`, não tag `latest`. A plataforma padrão exigida é Linux/AMD64;
Linux/ARM64 só é permitido explicitamente no smoke Docker local.
O comando acima exige TLS já provisionado e pesos já obtidos/verificados.
Preflight não chama AWS nem certifica a configuração do SG, IAM ou timer.

Para manter a política de sugestões usada na#22, há overlay optativo
`compose.aws.audio.yaml`: montar JSON revisado em `SONAR_HOST_AUDIO_CONFIG`,
registrar `SONAR_AUDIO_CONFIG_SHA256` e executar preflight com `--audio`.
Esse overlay não instala vozes, reproduz áudio ou controla vibração.

Para o paralelo medido, montar `scripts/benchmark_parallel_api.py` fora da
imagem, conferir SHA-256 do runner medido no relatório e definir
`SONAR_HOST_PARALLEL_RUNNER` e `SONAR_PARALLEL_RUNNER_SHA256`. Executar
`python scripts/check_aws_release.py --parallel` e acrescentar
`-f compose.aws.parallel.yaml` **em todos** os comandos Compose seguintes.
Não apresentar a performance paralela como performance do backend serial.

## Transferir um release para a VM

Após `launch`/`pin`, copiar do ledger privado `public_ip` para a variável
`SONAR_VM_IP`; conferir o prazo restante. A pasta `~/sonar23` é criada pelo
bootstrap. Trabalhar a partir do commit revisado da#23, mantendo o manifesto
local da versão e os hashes dos arquivos adicionais.

```sh
# No computador do operador, com o commit da entrega disponível:
git archive --format=tar --output=.local/source.tar "$RELEASE_COMMIT"
ssh -i .local/aws23-run1/operator-key \
  -o UserKnownHostsFile=.local/aws23-run1/known_hosts \
  -o StrictHostKeyChecking=yes "ubuntu@$SONAR_VM_IP" \
  'mkdir -p ~/sonar23/source ~/sonar23/private'
scp -i .local/aws23-run1/operator-key \
  -o UserKnownHostsFile=.local/aws23-run1/known_hosts \
  -o StrictHostKeyChecking=yes .local/source.tar \
  "ubuntu@$SONAR_VM_IP:sonar23/"
```

Gerar o certificado com SAN para o IP atual no computador, usando o extra
`api-dev` já existente. A chave da CA criada por este helper não é persistida;
um novo certificado exige nova CA e atualização explícita da confiança do cliente.

```sh
export SONAR_VM_IP
PYTHONPATH=src python - <<'CERT'
import os
from pathlib import Path
from sonar_vision_api.dev_tls import create
create(Path('.local/aws/tls'), names=('localhost', '127.0.0.1', os.environ['SONAR_VM_IP']))
CERT
chmod 600 .local/aws/tls/server-key.pem .local/aws/tokens
```

Transferir TLS, **hash snapshot** de tokens, pesos verificados e JSON de áudio
revisado por esse mesmo SSH autenticado, para `~/sonar23/private`. O plaintext
do token e `ca.pem` ficam com o cliente; a chave TLS fica no servidor.
Nunca copiar o plaintext para a imagem, argumentos, Git ou relatórios.
Na VM, `chmod -R go-rwx ~/sonar23/private`; operador Ubuntu éUID/GID1000.

Extrair source.tar em `~/sonar23/source`. Construir a imagem nessa pasta com
os argumentos/digest descritos acima; guardar `baseline.iid` fora do contexto.
Criar `.env` privado nesse diretório com o ID resultante, UID/GID1000,
`SONAR_HOST_TLS_DIR=/home/ubuntu/sonar23/private/tls`,
`SONAR_HOST_TOKENS_FILE=/home/ubuntu/sonar23/private/tokens`,
`SONAR_HOST_MODELS_DIR=/home/ubuntu/sonar23/private/models` e os caminhos/hashes
de pesos já definidos. Para paralelo/áudio, incluir caminhos absolutos e hashes
do runner/JSON revisado. Carregar `.env` no shell do preflight e usar os mesmos
três arquivos Compose em preflight, start, stop, logs e rollback:

```sh
cd ~/sonar23/source
set -a
. .env
set +a
PYTHONPATH=src python3 scripts/check_aws_release.py --parallel --audio
docker compose -p sonar23 -f compose.aws.yaml -f compose.aws.parallel.yaml \
  -f compose.aws.audio.yaml up -d --wait --wait-timeout 120
```

O bootstrap instala Python do Ubuntu/Docker; a aplicação usa Python da imagem.
Modelos devem usar nomes `general.pt`, `stairs-r21.pt`, `stairs-r20.pt` ou
ajustar explicitamente caminho **e hash**. Obter o peso geral conforme
[origem documentada](vision.md); especialistas pelo responsável do treinamento,
com manifesto/permissão e hashes do [handoff registrado](experiments/issue-22-r21-profile.json).
O relatório público e código são compartilháveis; pesos de escadas exigem esse
handoff legítimo antes de reprodução real por outro integrante. Sem ele, somente
o smoke simulado é reproduzível. Distribuição pública dos pesos não está autorizada.

Validar o endpoint a partir do cliente com CA explícita, token privado e JPEG
sintético ou autorizado:

```sh
PYTHONPATH=src python scripts/check_aws_endpoint.py \
  --endpoint "https://$SONAR_VM_IP:8443" \
  --token-file .local/aws/glasses-01.token --ca-file .local/aws/tls/ca.pem \
  --output .local/endpoint-report.json
```

Esse probe verifica saúde HTTPS, admissão,401 e CA errada; não mede percentis,
qualidade do detector ou segurança física. Para latência/erros/CPU/RAM usar o
[benchmark separado e agregação da#22](experiments/issue-22-reproduce.md).

## Iniciar, observar e recuperar

```sh
docker compose -p sonar-aws -f compose.aws.yaml up -d --wait --wait-timeout 120
docker compose -p sonar-aws -f compose.aws.yaml ps
docker compose -p sonar-aws -f compose.aws.yaml logs --tail 20 api
python -m sonar_vision_api.healthcheck --cafile .local/aws/tls/ca.pem
```

O bind permanece `127.0.0.1`. Depois de conferir SG, identidade, prazo e TLS,
`SONAR_AWS_BIND_IP=0.0.0.0` publica HTTPS para os clientes permitidos pelo SG;
o endereço de bind não significa regra de firewall irrestrita. Registrar essa
mudança e recriar o serviço. Um só óculos no perfil atual; MP4 serve como fonte
de JPEGs no computador, não payload enviado pela ESP.

O healthcheck mede HTTPS/saúde do processo, não capacidade de detecção, prazo,
tracking ou sensores. `on-failure:3` limita reinícios por saída com erro;
healthcheck unhealthy sozinho **não reinicia** o contêiner. Parada pelo operador
ou reinício do daemon exige conferir estado e executar `up -d --wait` manualmente.
Conferir causa antes
de reinício manual; não criar loop de recuperação que prolongue o prazo da VM.

Limites: 4 vCPU, 3 GiB, 256 PIDs, tmpfs128MiB. São parâmetros operacionais,
não limiares de risco. Logs JSON sem imagens/tokens; dispositivo/sessão/frame
são pseudônimos de experimento. Rotação3×10MB, sem retenção por dias. Exportar
somente agregados para docs; logs brutos ficam privados e são apagados com os
recursos ao final. Diagnóstico de predições está desativado por padrão.

Coletar Docker CPU/RAM com `scripts/sample_container.py` conforme
[procedimento #22](experiments/issue-22-remote.md), e percentis/erros pelos logs
correlacionados com dispositivo/sessão/frame. CPU do cliente não é CPU da VM;
RAM Docker sem cache não é RSS; não subtrair clocks de máquinas diferentes.

## Rotação e revogação

```sh
python -m sonar_vision_api.token_ops rotate glasses-01 .local/aws/tokens \
  --token-file .local/aws/glasses-01-next.token
docker compose -p sonar-aws -f compose.aws.yaml up -d --force-recreate --wait
# Instalar a nova credencial no cliente e verificar nova=200 / anterior=401.
python -m sonar_vision_api.token_ops revoke glasses-01 .local/aws/tokens
docker compose -p sonar-aws -f compose.aws.yaml up -d --force-recreate --wait
```

Não imprimir tokens no chat, logs, argumentos ou histórico. O arquivo plaintext
novo nunca sobrescreve um existente. Hash snapshot atualizado por rename atômico,
lock exclusivo por operação; falha normal preserva o snapshot anterior. Se o
operador morrer durante escrita, verificar arquivos e processos antes de remover
lock abandonado; não apagar automaticamente lock de outro operador.

`restart` sozinho não garante ler o inode substituído num bind mount de arquivo:
**recriar** o contêiner. Processos anteriores mantêm o TokenStore carregado até
recriação. Revogar o último dispositivo deixa arquivo vazio e bloqueia startup;
para suspensão total, derrubar o serviço/VM. Para recuperar após revogar o
último dispositivo, usar `provision` com novo arquivo/token, nunca restaurar
snapshot revogado. Rollback de imagem nunca restaura
credencial revogada, chaves comprometidas ou sessão antiga do cliente.

## Atualização e rollback

1. Exportar agregados, registrar imagem atual e hashes dos pesos/configuração.
2. Carregar nova imagem verificada; executar preflight antes de mudar ID.
3. Definir novo `SONAR_AWS_IMAGE_ID`, executar `up -d --wait`, verificar ID
   real via `docker inspect`, HTTPS autenticado e um JPEG autorizado.
4. Se falhar, restaurar ID anterior e configuração/runner anteriores
   compatíveis, executar `up -d --wait` e repetir a verificação.
5. Para R21→R20, trocar caminho **e hash** pelo rollback do perfil, confirmar
   manifestos/parâmetros e executar avaliação. Não misturar pesos silenciosamente.
6. Sessões/tracks vivem em memória: restart/update cria novo tracker epoch.
   Cliente reabre sessão; não reenviar capturas velhas.

O smoke local abaixo prova mecanismo de atualização por IDs de duas imagens
simuladas com labels distintas; não é comparação de modelos ou mudança de código
funcional entre releases. A comparação por labels verifica o mecanismo, sem demonstrar migração funcional
de versões da aplicação. O ensaio cloud usa também os checkpoints reais R21/R20;
resultados e limitações ficam na evidência vinculada abaixo.

## Encerrar e auditar

Preferir a limpeza que reconcilia todos os recursos próprios e salva a auditoria:

```sh
python scripts/aws_temporary_vm.py destroy --config .local/operator.json --run-dir .local/aws23-run1
```

A auditoria usa exatamente `Experiment=issue-23`; a#22 usa `issue-22`.
Um filtro sem hífen não verifica esses recursos. O operador é único e serializa
as rodadas: o lock é local ao run-dir, sem transação global entre computadores.


```sh
docker compose -p sonar-aws -f compose.aws.yaml down
# No computador do operador, IDs obtidos do ledger privado desta rodada:
aws ec2 terminate-instances --profile sonar-vision --region sa-east-1 \
  --instance-ids "$OWNED_INSTANCE_ID"
aws ec2 wait instance-terminated --profile sonar-vision --region sa-east-1 \
  --instance-ids "$OWNED_INSTANCE_ID"
```

Antes de qualquer delete, validar tags, conta/região e ausência de recursos de
outras tarefas. Conferir volumes disponíveis com tags próprias, chaves SSH e SG
sem interfaces associadas; remover somente os dessa rodada. Não basta stop:
disco retido pode cobrar. Atualizar ledger com tempo, custo e auditagem residual;
conferir cobrança posteriormente. Destruição não restaura dados não exportados.
A #22 documenta auditorias reais; o smoke só remove contêineres/redes locais.

## Alertas de custo — confirmação do proprietário

O IAM de operação não tem administração de cobrança. Não ampliar suas permissões
para ler e-mails/alterar billing. O proprietário deve configurar AWS Budgets no
console, usando destinatário privado escolhido por ele; nenhuma notificação foi
enviada por este trabalho.

Sugestão para esta janela: orçamento de custo US$15, alertas de consumo em50/80/100%,
sem ações automáticas adicionais. **Excluir créditos/reembolsos do cálculo**
(`IncludeCredit=false`, `IncludeRefund=false`) para que abatimentos não ocultem
consumo de catálogo; manter impostos incluídos. Conferir período e custos já
consumidos, sem duplicar o teto por rodada. Bryan confirmou em08/10/2026 que aplicou a política e criou o orçamento com
alertas após o passo a passo. Não houve verificação via API de cobrança nem
teste de entrega do e-mail. Esse orçamento mensal não renova a autorização
agregada US$15/8h nem autoriza implantação permanente.

[AWS CostTypes](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_budgets_CostTypes.html)
e [boas práticas de Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-best-practices.html)
documentam opções de custo e atualização. Dados/alertas têm atraso de cobrança;
não são teto automático. A proteção operacional continua sendo prazo, ledger,
remoção e limite agregado, com reconciliação humana de fatura.

## Validação e o que falta

[Resultado AWS, custo, limpeza e pendências](experiments/issue-23-results.md).

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_token_ops.py -v
PYTHONPATH=src python -m unittest discover -s tests -p test_aws_release.py -v
PYTHONPATH=src python scripts/smoke_aws_operation.py \
  --report .local/issue23-local-operation.json
```

[Evidência local](experiments/issue-23-local-operation.json): HTTPS autorizado,
401, CA errada recusada, rotação com recreação, update/rollback por imagem,
limites, parada graciosa, falha de conectividade e recuperação; contêineres próprios
removidos. Não usa vídeos de participantes, pesos reais, VM ou AWS.

A entrega da #23 ainda depende de PR revisável e revisão. O aceite cobre a
operação temporária; serviço mensal permanente exige orçamento próprio.
Hardware, captura ESP, tracking independente e segurança física permanecem
fora desta validação. O caminho tátil local permanece independente da nuvem.
