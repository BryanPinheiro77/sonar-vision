# ADR0017 — preparar a operação AWS sem implantar serviço permanente

- Data: 08/10/2026.
- Status: preparação autorizada por Bryan; validação local concluída;
  ensaio cloud temporário concluído; PR/aceite e operação permanente pendentes.
- Responsável: Bryan, com apoio de IA.
- Issue: [#23](https://github.com/BryanPinheiro77/sonar-vision/issues/23).

## Contexto

O reteste da#22 atingiu a meta de trabalho de8admissões/s em três rodadas,
mas excedeu alguns P95 propostos. Bryan autorizou continuidade de issues e
ensaios temporários durante sua ausência, com prazo e remoção de toda VM ociosa.
Não há orçamento mensal de operação. A#22 foi concluída peloPR54, com metas experimentais revisadas aprovadas
pelo responsável; a#23 reutiliza esse perfil. A base#28 e o contrato#12 já existem.

## Decisão operacional nesta preparação

Reutilizar EC2/Docker Compose/API HTTPS. Criar Compose standalone para imagem
local imutável, sem build/pull automático, bind inicial em loopback, recursos
limitados, usuário não root, volumes privados somente leitura e logs rotacionados.
Validar hashes/plataforma/credenciais/TLS localmente antes de iniciar.

Manter runner paralelo da#22 em overlay optativo e verificado, sem alterar
backend ou contratos do produto. Medidas do runner não se aplicam ao padrão
serial. CPU4/São Paulo são perfil temporário medido, não promoção permanente.

Credenciais individuais continuam no formato já usado pela API. Adicionar
manutenção offline com snapshot atômico, lock exclusivo e plaintext somente em
arquivo novo0600. Recriar o contêiner após rotação/revogação, pois o TokenStore
é carregado na inicialização e um bind de arquivo pode preservar inode anterior.
Não criar endpoint administrativo, reload remoto ou worker adicional.

## Alternativas e consequências

Mesclar portas com o Compose local poderia manter publicações conflitantes.
Tag mutável não fixa a imagem executada. Serviço de secrets, registry, IaC com
novas dependências, banco, dashboards ou orquestração não são necessários para
essa preparação. CLI offline reutiliza biblioteca padrão e formato existente.

Atualização interrompe o serviço brevemente e reinicia sessões/tracking; o
caminho tátil local permanece independente. CA de desenvolvimento não equivale
a certificado público. Lock abandonado exige inspeção do operador. Falha no
último dispositivo deixa startup sem credenciais, bloqueado de forma explícita.
Não restaurar tokens revogados ao fazer rollback de imagem.

## Verificação e limites

[Runbook, artefatos e comandos](../aws-operation.md). Smoke local com backend
simulado verifica HTTPS, revogação/rotação, update/rollback por IDs, limites,
parada e recuperação, removendo contêineres próprios. Não prova performance
AWS, rollback de pesos reais, hardware ou segurança física.

A operação temporária foi ensaiada na AWS e os recursos removidos; há
[manifesto e resultados](../experiments/issue-23-results.md). Alertas de custo
foram confirmados pelo proprietário, sem teste de entrega. A#23 ainda depende
dePR/revisão/aceite e handoff legítimo dos especialistas para reprodução pelo
grupo. O JPEG de cadeira alcançou7,08fps, abaixo da meta; esse diagnóstico fica
pendente, sem alegar capacidade geral. Os limitesUS$15/8h somadas continuam
válidos somente para ensaios temporários. Implantação mensal não autorizada.

## Continuação de09/10/2026

Reboot e expiração absoluta reais concluídos, mantendo a mesma instância,
imagem e configurações; recursos removidos. Reteste longo da cadeira emJPEG95
atingiu9,89FPS, sem mudança de padrão. Alternativa de cadência não mostrou
vantagem eJPEG85 não foi aprovado por qualidade. [Resultados, custos e limites](../experiments/issue-23-cadence-results.md).
Esse resultado não isola a causa dos7,08FPS antigos ou conclui tracking/hardware.
