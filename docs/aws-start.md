# Primeiro acesso à AWS para o Sonar Vision

Responsável: Bryan, com apoio de IA. A #22 mede antes de escolher o deploy da
#23. **Orçamento do benchmark aprovado por Bryan em 07/10/2026:** até US$15 de
consumo, inclusive créditos, até oito horas somadas de instâncias CPU,
começando em São Paulo e removendo os recursos ao terminar. Isso não autoriza
serviço permanente, GPU ou assinatura adicional.

## O que cada parte faz

| Termo | Papel neste projeto |
|---|---|
| Conta AWS / root | Proprietário da conta, recuperação e tarefas administrativas especiais |
| IAM | Define quem acessa e quais ações essa identidade pode executar |
| MFA | Segundo fator para proteger o login |
| AWS CLI / perfil | Acesso pelo terminal; o perfil separa o Sonar Vision do LocalStack |
| Região | Local dos recursos; `sa-east-1` é São Paulo, ponto inicial do ensaio |
| EC2 | Computador temporário que executará Docker, API e modelos |
| EBS | Disco da VM; pode continuar existindo após parar uma instância |
| Security Group | Regras de rede para entrar/sair da VM |
| Créditos / orçamento | Créditos pagam consumo elegível; nosso teto continua US$15 consumidos |

## 1. Criar a conta

Bryan cria a conta no [site oficial](https://aws.amazon.com/free/), preenchendo
seus dados diretamente. Não enviar senha, documentos, cartão, access keys ou
códigos de autenticação pelo chat/Git. Escolha **Free plan**, se apresentado,
para este início; confirme plano, créditos e elegibilidade depois do cadastro.

O [Free plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
é limitado a serviços/funcionalidades elegíveis e termina em seis meses ou no
fim dos créditos. Não equivale a deploy permanente. Migração para Paid plan
ou uso de serviços que alterem o plano exige uma decisão específica. Entrar em
AWS Organizations pode converter automaticamente o plano; não é requisito
para o ensaio.

## 2. Proteger e preparar o acesso

Ative MFA na conta root e preserve a recuperação. Root é a conta proprietária;
o [uso cotidiano](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_root-user.html)
deve ocorrer por outra identidade apropriada. Bryan confirmou cadastro e MFA em 07/10/2026.
Prepararemos a identidade de trabalho e as permissões necessárias ao
benchmark, conferindo a compatibilidade com o plano escolhido.

IAM não é uma chave a enviar ao agente. O nome do perfil e a confirmação de
login são suficientes para iniciar as verificações locais. Não é necessário
começar gerando credenciais permanentes.

## 3. Autenticar a CLI depois de preparar a identidade

CLI local conferida: **2.35.17**, compatível com
[`aws login`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
(mínimo 2.32.0). O fluxo abre o navegador e gera credenciais temporárias. Para
uma identidade IAM, a AWS documenta a política `SignInLocalDevelopmentAccess`;
as permissões para operar EC2 são uma escolha separada. Não usar root como
identidade de operação habitual da VM.

Depois de preparado o acesso, os comandos são:

```sh
aws login --profile sonar-vision --region sa-east-1
aws sts get-caller-identity --profile sonar-vision
```

O segundo comando só verifica a identidade; não cria recursos. O perfil
`localstack` encontrado inicialmente é um emulador local, não comprova acesso
à AWS real. Não copiar arquivos de credenciais para este repositório.

## 4. Conferir a conta antes do primeiro recurso

Vamos verificar juntos: conta/plano e saldo, região habilitada, elegibilidade
da instância/imagem, cotas, preços atuais, permissões e acompanhamento de
consumo. Alertas de orçamento não são trava automática de gastos; a execução
precisa de limite de duração e limpeza dos recursos próprios. A escolha
permanente de máquina/região fica para depois dos resultados.

## 5. Criar, medir e remover — explicando cada etapa

Antes de executar, explicar o recurso, custo, efeito e forma de desfazer:

1. Uma VM CPU candidata, disco e regras de rede restritas ao operador.
2. Certificado/credenciais e pesos privados por volumes; nenhum modelo ou vídeo
   público incorporado à imagem Docker.
3. API em loopback. Um túnel SSH pode transportar o HTTPS na etapa inicial;
   esse caminho inclui overhead do túnel, que deve ser registrado. Não é a
   topologia final da #23 nem autoriza abrir a API para toda a internet.
4. Cliente separado na conexão prevista para o teste; um e dois dispositivos,
   taxas e repetições, coletando tempos e recursos no servidor.
5. Exportar agregados/logs privados, encerrar a VM e conferir volumes,
   endereços e demais recursos criados pelo ensaio. Limpar somente os recursos
   identificados como nossos; parar a VM sozinho não encerra todas as cobranças.

Os comandos do cliente/coleta estão no [procedimento remoto](experiments/issue-22-remote.md).
Conta e perfil IAM autenticados; primeiro lançamento temporário realizado
em07/10/2026. Estado, medidas e limpeza são registrados no procedimento remoto.

## Primeiro usuário de trabalho: acesso de consulta

Para iniciar a verificação sem conceder criação de recursos, criar usuário
IAM `sonar-vision`, com acesso ao console, senha privada e MFA próprio. Na
etapa de permissões, anexar inicialmente apenas:

- `SignInLocalDevelopmentAccess`: autoriza o fluxo temporário de login local.
- `AmazonEC2ReadOnlyAccess`: permite consultar EC2 e os metadados relacionados;
  não concede criação de VM.

A conta root com MFA pode atribuir MFA ao usuário pelo detalhe do usuário no
IAM. Depois, usar o login desse usuário no navegador e autenticar o perfil
`sonar-vision` na CLI. A permissão de operar os recursos temporários será
preparada separadamente, após conferir identidade/plano/cotas, com escopo
adequado ao experimento. Não criar access keys nem conceder AdministratorAccess
para esta primeira consulta. Criação do usuário não conclui o acesso da CLI.

## Liberação da operação temporária (após consulta da conta)

Consultas executadas com IAM `sonar-vision`: quota padrãoOn-Demand de5vCPUs
em São Paulo; nenhuma instância existente na região. `c7i-flex.large` e
`m7i-flex.large` estão oferecidas e marcadas FreeTierEligible. O perfil agora
usa `sa-east-1` como região padrão.

Política específica preparada em arquivo privado nos Downloads,
`Sonar-Vision-AWS-Benchmark-22-Policy.json`, com ARNs da conta, para revisão
e criação pelo proprietário no console. Não usar esse arquivo como política
genérica de outra conta. Sintaxe JSON conferida; validação IAM ainda depende
do console/AWS. Nenhuma permissão de operação foi anexada pelo agente.

Escopo: lançamento apenas c7i-flex.large/m7i-flex.large emsa-east-1, instâncias
e volumes marcados Project=sonar-vision/Experiment=issue-22, volumegp3 até20GB,
IMDSv2 obrigatório nas instâncias. Permite criar acessoSSH por chave pública/
security group e alterar/remover recursos marcados do benchmark. Não inclui
IAM admin, PassRole, GPU, snapshots ou criação de VPC. Regras de firewall são
limitadas ao grupo marcado; o CIDR/porta concretos precisam ser restritos pelo
procedimento de operação. A política não impõe um teto monetário ou de horas.

O proprietário anexará a política ao usuário pelo console root. Após isso,
verificaremos autorização com DryRun antes do primeiro lançamento; DryRun
não cria a VM e não valida todos os efeitos tardios, cotas ou saldo de crédito.

### Correção da autorização de CreateSecurityGroup

DryRun de RunInstances foi autorizado, mas a tentativa de criar o security
group falhou antes de criar recursos: a autorização também avalia a VPC
existente, que não tem o contexto de tags do novo grupo. O arquivo privado
da política foi atualizado com um Allow de CreateSecurityGroup somente no
ARN da VPC padrão, condicionado à região. Não concede criação/alteração da
VPC nem acesso geral de administrador. O proprietário confirmou a atualização; criação do grupo e lançamento da VM
funcionaram em seguida. A política não foi aplicada via identidade de trabalho.

## Repetir o preparo do servidor

O primeiro ensaio usou a API de `adb0d2b` (main/PR53), não o merge local do
PR50. Na VM Ubuntu24.04, instalar Docker conforme o
[procedimento oficial](https://docs.docker.com/engine/install/ubuntu/) e copiar
apenas Dockerfile, pyproject.toml, src, compose.yaml e LICENSE dessa revisão.
Não copiar .git, .local, credenciais AWS nem o diretório inteiro de Downloads.
Registrar AMI/versões na evidência privada. Pesos geral e candidato de escadas entram em volume
privado. O perfil atual é [r21 com rollback r20](experiments/issue-22-r21-profile.json),
selecionado explicitamente por Bryan. Ambos exigem obtenção privada com o
responsável: não são o peso v3 publicado; ausência do candidato impede
reproduzir o perfil integrado.

Usar o [preparo TLS/tokens e build real](packaging.md), usuário do host para
ler os arquivos modo600, backend ultralytics e ambos os hashes configurados.
Publicar8443 somente em127.0.0.1. Override específico do ensaio:

```yaml
services:
  api:
    cpus: 2
    mem_limit: 3g
    restart: "no"
    environment:
      SONAR_API_AUDIO_CONFIG: /run/sonar/audio.json
    volumes:
      - ../private/audio.json:/run/sonar/audio.json:ro
```

O caminho relativo acima pressupõe `source/compose.yaml` e `private/audio.json`
como diretórios irmãos. A política de áudio é a do [smoke real](../scripts/smoke_vision.py),
sem diagnóstico de caixas. O build efetivo usa `EXTRAS=api,vision`; registrar
`python -m pip freeze` dentro do contêiner. Dependências transitivas podem mudar.

No cliente, abrir um túnel com chave própria e verificação do host SSH.
Substituir `HOST_DA_VM` pelo endereço obtido na consulta autenticada do EC2:

```sh
ssh -N -i .local/operator-key \
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 -L 18443:127.0.0.1:8443 ubuntu@HOST_DA_VM
curl --max-time 5 --cacert .local/tls/ca.pem https://localhost:18443/healthz
```

O túnel ocupa esse terminal: executar curl/carga em outro. Validar saúde e
autenticação antes de iniciar, e manter o túnel ativo. Após uma interrupção,
conferir novamente; não assumir que processos anteriores sobreviveram.
No macOS, manter tampa aberta e envolver o comando do cliente com
`caffeinate -dims -t 2400`. Esse comando expira após40min; não protege de
fechamento da tampa. Conferir `measurement_continuity.continuous=true` no
relatório antes de usar a rodada para capacidade.

Ao encerrar, exportar logs/métricas privados antes de terminar a VM. Confirmar
`terminated` e exclusão do root com DeleteOnTermination, conferir volumes
marcados do RunId, remover chave pública e security group do mesmo RunId.
Conferir tags Project/Experiment/RunId antes de remover qualquer recurso.
Não excluir VPC/subnets padrão ou recursos de outros experimentos.
O primeiro ensaio não criou Elastic IP, NAT Gateway, load balancer ou snapshot.

### Caminho atual do ensaio: HTTPS direto restrito

O túnel acima descreve a primeira tentativa. Após seus timeouts, a repetição
r21 usa HTTPS direto: publicar8443 em0.0.0.0 no Compose da VM e liberar somente
TCP8443 do IPv4 atual do operador/32 no security group próprio. Não usar
0.0.0.0/0 como origem de entrada. Gerar certificado de teste com SAN do
endereço da VM, localhost e127.0.0.1, usando a função `dev_tls.create`; cliente
confia explicitamente na CA desse certificado. O certificado anterior do
túnel não valida um endereço que não esteja no SAN.

Configurar `SONAR_API_STAIR_WEIGHTS_IN_CONTAINER` para o arquivo r21 e
`SONAR_API_STAIR_WEIGHTS_SHA256` conforme o perfil. Preservar r20 como arquivo
separado; rollback restaura caminho/hash r20 e recria o contêiner. Não reduzir
confiança, imgsz ou critérios de validade para melhorar a contagem de FPS.

Usar `remote_load --endpoint https://ENDERECO_DA_VM:8443` com CA/token privados
no lugar do endpoint do túnel. `ENDERECO_DA_VM` é um marcador a substituir, não
um host existente. O cliente não escreve esse endereço nos relatórios.
Reiniciar o coletor de recursos com o novo ID concreto do contêiner após
recriação; não reaproveitar o cabeçalho de outro contêiner. A regra temporária
é removida na limpeza do security group. Essa configuração não é o deploy
permanente da#23.

## Créditos e decisão sobre Paid plan

A AWS permite ganhar até maisUS$100 por atividades elegíveis em ambos os planos:
[regras de atividades](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans-activities.html).
Upgrade normal preserva créditos existentes, e o Paid plan permite cobranças
além do saldo ou em serviços sem cobertura de créditos:
[comparação de planos](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).
Não é necessário migrar para continuar os ensaios com os recursos já permitidos.

A propostaCPU4 é opção preparada, sem aprovação da mudança de plano. A consulta
marca c7i-flex.xlarge como não elegível e a IAM atual não autoriza esse tipo.
Isso não é uma tentativa de lançamento que comprove o erro de plano na conta:
validar o acesso específico antes de apresentar o upgrade como condição
confirmada. Continuar análise local/Free plan enquanto essa decisão permanece
pendente. Ganhar créditos não exige criar serviços extras automaticamente.

## Estado após os ensaiosCPU4 — 08/10/2026

As instruções iniciais acima registram a contaFree plan e o primeiro acesso.
Depois, Bryan autorizou a mudança paraPaid plan; o tipoCPU4 foi executado e
removido após os testes. O [ledger consolidado](experiments/issue-22-final-cost.json)
e [perfil aprovado](experiments/issue-22-approved-profile.json) são o estado
atual. Os créditos continuam contando como consumo; serviço mensal permanente
ainda não foi autorizado.
