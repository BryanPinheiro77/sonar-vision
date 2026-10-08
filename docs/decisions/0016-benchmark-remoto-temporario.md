# ADR 0016 — benchmark remoto temporário da #22

- Data: 2026-10-07.
- Status: preparação autorizada; orçamento temporário aprovado por Bryan;
  escolha final de infraestrutura/protocolo ainda pendente de medidas.
- Responsável: Bryan, com apoio de IA.
- Issue: [#22](https://github.com/BryanPinheiro77/sonar-vision/issues/22).

## Contexto

A #52 entregou API executável com geral+R20. O PR50 mede carga em loopback,
com CPU/RAM compartilhada por cliente e servidor. A #22 precisa separar os
escopos para dimensionar. Conta Free plan e usuário IAM com MFA foram
preparados pelo proprietário; primeiro ensaio temporário iniciou em07/10/2026.

## Decisão

Reutilizar o executor de carga e cliente HTTPS para endpoint operado
separadamente, com TLS verificado, credenciais distintas, um envio ativo por
dispositivo e sem fila. Coletar recursos no host Docker e correlacionar os logs
existentes por dispositivo/sessão/frame, sem endpoint público novo. Não
subtrair clocks de máquinas distintas nem chamar recursos do cliente de VM.

Bryan aprovou atéUS$15 de consumo, inclusive créditos, até8horas somadas de
instâncias CPU no benchmark temporário, começando em São Paulo e removendo os
recursos ao terminar. Não aprova deploy permanente, GPU ou novas assinaturas.
Registrar recursos próprios, tempo/custo e conferir cobrança residual. Essa
aprovação substitui somente o estado pendente do teto anterior; outros limites
quantitativos/protocolo final continuam propostos.

Preparar acesso com conta protegida e identidade apropriada de operação;
credenciais permanecem fora do chat/Git. Preço/plano/elegibilidade/cotas serão
conferidos na conta antes de provisionar. Um túnel SSH pode transportar HTTPS
no ensaio inicial, com overhead identificado; a topologia permanente pertence
à #23. Sem abertura indiscriminada da API para a internet.

## Alternativas e consequências

Manter apenas benchmark in-process não mede recursos da VM; endpoint de debug
exporia dados sem necessidade. Mudar para broker/banco/GPU ou alterar políticas
não resolve a ausência de medidas e está fora do escopo. Docker local com quota
valida o procedimento, não reproduz Intel/EC2 ou o comportamento de CPU Flex.
Os primeiros resultados abaixo de8/s permanecem documentados, sem otimização
ou promoção de capacidade por suposição.

## Verificação

[Procedimento/resultados locais](../experiments/issue-22-remote.md) e
[primeiro acesso AWS](../aws-start.md). A inferência semântica remota nunca
comanda a vibração; o caminho tátil local segue independente. Testes de software
não equivalem a hardware, qualidade de tracking ou AWS validada.

## Ajuste do procedimento em07/10/2026

A rodada nominal inicial foi invalidada por suspensão do cliente. Com cliente
acordado, o túnel SSH encerrou por timeout: não concluir falta de CPU a partir
dos drops. O ensaio seguinte usa HTTPS direto com TLS/token e entrada limitada
aIPv4 do operador/32 na porta8443, sem regra aberta à internet inteira. Esse
ajuste está no escopo temporário da#22 e será removido ao terminar; não decide
o deploy permanente da#23. Continuidade do relógio é conferida no relatório.

Bryan autorizou r21 como candidato de escadas junto ao geral, preservando
r20 para rollback e os parâmetros0,35/640/IoU0,50.
[Perfil](../experiments/issue-22-r21-profile.json). Não altera API/contrato
nem promove produção ou aceita acurácia independente. Rodadas comr20/túnel
não são comparações nominais comr21/HTTPS direto.

## Comparação CPU planejada após a linha de base

A versão fixa do Ultralytics usa `NUM_THREADS = min(8, max(1, os.cpu_count()-1))`
e o caminho CPU chama `torch.set_num_threads(NUM_THREADS)`. Na VM2vCPU isso
resulta em1thread. Hipótese experimental: comparar2threads após o warmup,
com o mesmo builder/API da main, pesos geral+r21, TLS, áudio, confiança, imgsz
e associação. Runner privado de operador; não altera o padrão do produto
nem constitui promoção de configuração. Registrar before/after efetivos.

Teste curto de60s, com warmup30s; só prolongar600s se atingir8admissões/s
sem falhas e continuidade do relógio true. Esse gate controla o custo do
ensaio exploratório; não substitui a proposta de3repetições para aceite final.
Resultados e verificação semântica precisam ser analisados antes de selecionar
perfil permanente. Hardware/independência temporal continuam não validados.

## Resultado

[Primeiro ensaio concluído](../experiments/issue-22-aws-results.md): r21
reproduziu169/177casos conhecidos, sem treino/API/contrato alterados. A CPU2
medida entregou4,94–5,00admissões/s sustentadas no perfil sintético;2threads
não melhoraram. Recursos temporários removidos e remoção auditada. Manter
a escolha permanente pendente; próxima comparação CPU4 depende de plano
e permissão apropriados, não de necessidade de GPU assumida.

## Investigação adicional no Free plan

Antes de ampliar a máquina ou mudar o plano, comparar duas predições de
modelos independentes em paralelo, com uma thread interna por modelo, na
mesma CPU2. A seleção desta hipótese é experimental: o ganho local no Mac
não demonstra ganho na EC2. Pesos, confiança, resolução, associação e API
continuam fixos. Tracking e associação continuam sequenciais; apenas um
frame global pode estar ativo, sem fila. Em falha, a propriedade dos modelos
só é liberada após ambas as tarefas terminarem.

O runner explícito `scripts/benchmark_parallel_api.py` preserva o padrão da
API. Comparar com a execução original na mesma nova VM e conferir as
predições dos casos conhecidos. O teste curto decide se vale prolongar a
medição; não aprova produção. A nova VM temporária usa Free plan e o mesmo
tipo já autorizado, teto de duas horas, dentro das oito horas agregadas e
US$15 aprovados. Bryan autorizou continuar a investigação; Paid plan e CPU4
continuam sem aprovação. Remover os recursos ao concluir.

Hipótese adicional de execução: comparar o formato de memória `channels_last`
do PyTorch existente, mantendo tensores float32 e verificando que todos os
valores dos parâmetros permanecem iguais. Primeiro sondar inferência nativa
pareada na mesma EC2, depois medir HTTPS somente se houver ganho. Conversão
inicial dos pesos fica fora da janela; conversão da entrada faz parte da
inferência. Documentar diferenças numéricas/detecções e não promover um
formato que apresente regressão. Referência: [PyTorch memory format](https://docs.pytorch.org/tutorials/intermediate/memory_format_tutorial.html).

## Resultado da investigação adicional

[Ensaios concluídos e recursos removidos](../experiments/issue-22-cpu-investigation.md).
Paralelo:4,23→4,48admissões/s no piloto pareado, abaixo do gate8/s;
sem prolongamento. Memória channels_last:sem ganho nativo, rejeitada para
seleção. Critério congelado169/177, mesmas oito falhas, em todos os modos
avaliados. Não promover ajustes nem alterar o padrão da API. Recomendação
CPU4 continua pendente de permissão/elegibilidade e medidas; Free plan mantido.

## Autorização da comparação CPU4

Após a recomendação, Bryan respondeu “vamos fazer isso entao”: autoriza
preparar/executar a comparação CPU4 dentro do orçamento temporário existente.
Não autoriza mudar a conta para Paid plan. Consumo anterior estimado2,267h
 eUS$0,317, antes de impostos/tráfego; comparação proposta até2h/US$0,54.
[Proposta atualizada](../experiments/issue-22-cpu4-proposal.json).

[Preflight](../experiments/issue-22-cpu4-preflight.json): quota16vCPU,
c7i-flex.xlarge4vCPU/8GiB, FreeTierEligible=false. DryRun retornou
UnauthorizedOperation por ausência de Allow para a instância CPU4; não criou
recursos nem demonstrou restrição de plano. Proprietário precisa acrescentar
somente esse tipo à política IAM do benchmark no console. Documento privado
preparado e diferença verificada. Após a edição, repetir DryRun e verificar a
restrição real da conta; qualquer mudança de plano depende de autorização
específica. Preservar os parâmetros e distinguir auto threads da configuração
CPU2 ao comparar medidas. Não concluir ganho nem escolher deploy antecipadamente.

## Restrição de plano confirmada no lançamento real

Bryan confirmou a edição IAM; DryRun agora retorna DryRunOperation. A tentativa
real de lançar c7i-flex.xlarge retornou InvalidParameterCombination:
“The specified instance type is not eligible for Free Tier.”
[Registro](../experiments/issue-22-cpu4-preflight.json). Nenhuma VM/disco criado;
chave/grupo temporários removidos e zero recursos próprios residuais auditados.
O DryRun validou IAM, mas não essa restrição tardia de plano.

Para comparar essa CPU4 na conta atual, é necessária decisão do proprietário
sobre Paid plan. Free plan permanece ativo; não inferir autorização de upgrade
a partir da edição IAM ou do teto de benchmark. O consumo projetado segue
US$0,54/até2h antes de impostos/tráfego dentro deUS$15/8h agregados. Não há
medição CPU4 nem decisão de dimensionamento concluída.

## Upgrade para Paid autorizado pelo proprietário

Bryan respondeu “pode mudar”, autorizando o upgrade para Paid após a rejeição
real de CPU4 no Free plan. Teto de benchmark permaneceUS$15/8h agregados;
esta autorização não aprova deploy permanente ou serviços adicionais.
A tentativa explícita `freetier:UpgradeAccountPlan` comPAID foi negada:
AccessDeniedException, usuário IAM do benchmark não possui essa ação.
O plano não foi alterado pelo agente. Proprietário concluirá o upgrade já
aprovado no console; não ampliar a política operacional com administração de
billing para contornar esse acesso. Revalidar antes de iniciar nova instância.

## CPU4 iniciada após upgrade informado

Bryan informou concluir o upgrade e confirmouUS$120 ainda visíveis no console.
Saldo é relato do proprietário; API de créditos não foi acessível pela rede
local e não validou esse valor. Nova tentativa c7i-flex.xlarge foi aceita e
iniciada em São Paulo. Tags,20GB gp3 criptografado/DeleteOnTermination,
IMDSv2, IPv4 do operador/32,100min de expiração após bootstrap e remoção
manual ao terminar. Perfil geral+r21 fixo, r20 local para rollback.

Comparar pilotos60s com warmup30s: threads automáticas, serial com1thread,
paralelo com1thread por modelo. Registrar threads efetivas no builder e
worker: o runner de operador observa o contador no processo real; processo
separado `docker exec python` não prova o valor da API. Não muda a API padrão.
Selecionar maior FPS válido, preferindo auto se ficar até0,2FPS do melhor;
somente prolongar três600s se atingir8admissões/s sem falhas e clocks contínuos.
Essa seleção decide qual hipótese prolongar, não promove produção. Comparar
casos conhecidos no modo selecionado e controle distinto; manter falhas de
transporte separadas de falhas do modelo. Limite2h e orçamento já aprovados.

Após pilotos CPU4 abaixo do gate, sondar também paralelismo com2threads
internas por modelo, usando os mesmos dois modelos independentes e slot
único, sem mudar o padrão do produto. Hipótese: distribuir trabalho nas4vCPU;
mais threads podem aumentar overhead, portanto não presumir ganho. Mesmo
gate60s/8admissões/s para prolongar e conferência dos177JPEGs congelados.
O runner explícito aceita `--threads 1|2` (padrão1), confere o contador no
worker antes de cada predição e mantém a propriedade até ambas terminarem.
Pesos, precisão, confiança, resolução, associação, API e contrato preservados.

## Resultado CPU4

[Rodada encerrada, exportação e remoção auditadas](../experiments/issue-22-cpu4-results.md).
Paralelo1:6,95admissões/s externo no piloto,9,92–10/s porHTTPS dentro daVM,
sem aceite externo sustentado. Upload mostrou leitura de corpo1,53/1,61s
em dois casos rejeitados antes de inferir; Bryan informou internet intermitente.
Não inferir GPU/CPU maior por essa demora. Controle/paralelo1 mantêm169/177
predições corretas nos diagnósticos, mesmas oito falhas; respostas tardias
continuam descartadas e não viram entregas válidas. Paralelo2 não selecionado;
duas imagens não avaliadas por rejeição antes do modelo.

CPU4+paralelo1 fica como candidato experimental, sem mudar padrão/protocolo;
repetir externo com rede estável e fechar critérios antes do deploy#23.
O diagnóstico local60s não substitui três600s ou hardware. Consumo agregado
estimadoUS$0,537/3,078h deVM/IP/disco antes de impostos/tráfego, dentro do teto
US$15/8h. Firmware e independência tátil local preservados; sem commit/push/merge.

## Reteste externo solicitado com rede estável

Bryan informou estar com rede estável e autorizou seguir o reteste. Reutilizar
CPU4/paralelo1, perfil geral+r21 congelado e o mesmo protocolo externo:
piloto60s/warmup30s, três600s somente após8admissões/s sem falhas e clocks
contínuos. Sem alterar compressão, validade, filas, contrato ou classes.
Consumo anterior3,078h/US$0,537 estimados deVM/IP/disco; próximo teto2h,
dentro de8h/US$15 agregados. Nova rodada isolada e remoção ao terminar.
Sessão CLI anterior expirou; login do usuário IAM com MFA precisa concluir
antes de qualquer recurso novo. Preparação local não criou infraestrutura.

Bryan esclareceu uso de somente um óculos. Reteste atual passa a incluir
apenas um dispositivo: remover a sondagem de dois clientes desta rodada,
preservando as repetições de600s e os clipes. Ensaios anteriores de dois
clientes continuam como evidência histórica de hipótese, não requisito de
uso confirmado. Protocolo inicial envia JPEGs individuais pela API; vídeos
pré-gravados servem como fonte de frames na bancada, não upload deMP4 pelaESP.
Captura, codificação e cadência reais daOV2640/ESP ainda dependem de hardware.

## Reteste concluído e continuação autorizada em 08/10/2026

Três repetições de600s com um dispositivo atingiram8,29/8,39/8,43admissões/s,
sem falhas por tentativa. Metas propostas deP95 não foram todas atendidas;
não declarar aceite global da#22. Conjunto conhecido169/177, mesmas oito
falhas. [Evidência e limpeza](../experiments/issue-22-stable-results.md).

Bryan autorizou continuar pendências, novas issues e testes enquanto ausente,
com encerramento manual deVMs ociosas e prazo automático em cada novaVM.
Manter o teto temporárioUS$15/8horas somadas. Isso não cria orçamento mensal
permanente. Preparação local da#23 pode avançar; dependências dehardware,
dados independentes e participação humana devem ficar explícitas.
