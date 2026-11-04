# ADR 0027 — deploy preservado e senha de visualização

- Data: 04/11/2026.
- Responsável: Bryan, frente de modelo/cloud; #23/#73 e integração #17/#19.
- Decisão de Bryan: preservar a instância do deploy, parando quando ociosa;
  permitir redes móveis para envios autenticados; painel com senha de visualização
  separada do token ESP. Domínio informado: `bryandev.com.br`, DNS no Registro.br.
- Status: decisão aprovada nesta conversa, implementada/testada localmente e
  implantação inicial em 04/11. IP fixo, DNS e certificado público verificados.
  Bryan aprovou o formulário local e solicitou revisão/merge/publicação.

## Contexto e alteração do escopo anterior

A implantação anterior era efêmera: desligar a VM a destruía. Bryan pediu para
reutilizar a mesma VM e URL nos ensaios e apresentação. Os clientes móveis
podem mudar o IP de origem. O painel anônimo da ADR 0024 exigia allowlist;
uma porta aberta na AWS não substitui o controle de leitura na aplicação.

Esta decisão altera explicitamente a operação de destruição por rodada e a
exigência anterior de acesso sem login da #73. Não autoriza um painel anônimo
com imagens públicas, orçamento renovável ou funcionamento contínuo.

## Decisão

- Preservar EC2 e EBS; parar quando ociosa. Antes de ligar novamente, mudar o
  comportamento de desligamento para `stop` e preparar prazo de parada para cada
  janela, sem os antigos mecanismos que terminam/apagam os recursos.
- O agregado aprovado de horas de CPU/consumo continua vigente. Disco e IP
  reservado também consomem orçamento enquanto a VM está parada. Reconciliar
  essas despesas e definir encerramento da operação após a apresentação.
- Permitir HTTPS dos produtores de qualquer IPv4, mantendo Bearer individual,
  TLS validado, limites de corpo/cadência e isolamento por dispositivo/sessão.
  SSH permanece restrito ao operador. Não alterar inferência 0.1 nem ToF.
- Acrescentar modo optativo de leitura por senha, com usuário `sonar` em formulário
  HTTPS e sessão de navegador. Ele protege GET/HEAD dos dados do painel,
  snapshots, JPEGs, histórico e downloads. Assets de marca/CSS/login são públicos;
  nenhuma senha é colocada em URL, JavaScript ou mensagens do ESP.
- Servidor guarda somente verificador PBKDF2-SHA256 com salt aleatório e
  600.000 iterações. Uma entrada em memória evita refazer o KDF para a mesma
  credencial válida; tentativas de verificação novas são limitadas a 2/s por
  processo e executadas fora do event loop. Cache e contadores têm tamanho fixo.
- Senha de visualização não autoriza POST/DELETE; Bearer do ESP não autoriza
  leitura nesse modo. Configuração ausente mantém o modo anterior por IP;
  configuração inválida impede startup. Troca do verificador exige recriar API.
- Proposta de endereço: `sonar-vision.bryandev.com.br`, preservando raiz/www da
  Vercel. Caminho `/sonar-vision` no domínio principal exige redirecionamento ou
  proxy no site atual, não um registro DNS. IP fixo e certificado do hostname
  foram verificados para `sonar-vision.bryandev.com.br`.

## Alternativas e limites

Manter allowlist reduz alteração de código, mas depende de atualizar IPs móveis.
Abrir o painel sem autenticação exporia as imagens. Contas individuais/SSO e
banco não são necessários para a demonstração com senha compartilhada. Não há
auditoria individual, recuperação de conta ou revogação por espectador.

Domínio com DNS atualizado a cada start evita reservar IP, mas requer atualização
e propagação. Elastic IP estabiliza o destino e custa enquanto reservado.
Bryan aplicou as permissões limitadas e o operador confirmou modificação para
`stop` e associação de um único endereço etiquetado; não usar administrador no
dia a dia. O timer absoluto agora apenas para e desabilita a própria ativação
antes do shutdown. Ao ligar de novo, há até dez minutos para o operador armar
uma janela autorizada; sem ela o guard bloqueia Docker e para a VM. Reboot
dentro de uma janela não estende seu prazo absoluto.

O caminho tátil continua local. Autenticação não valida hardware, detecção,
tracking, compreensão de áudio ou risco físico. Uso físico, HTTPS público do
hostname e desempenho após a mudança precisam de ensaio próprio.


## Formulário e aprovação da publicação

Em 04/11 Bryan pediu formulário com a identidade do Sonar Vision e favicon
próprio. A navegação sem sessão redireciona a `/demo/login`, em vez de acionar
um desafio Basic do navegador. A credencial compartilhada permanece separada
do Bearer. A sessão usa cookie Secure, HttpOnly, SameSite=Strict, válido até
8h; chave aleatória em memória por processo invalida sessões ao reiniciar.
Login e saída conferem Origin. Apenas assets sem dados e a tela de acesso
são públicos; dados/imagens continuam autenticados. Basic não é aceito para leitura. Sair remove o cookie local; não revoga cópias
em outro cliente. A tela foi auditada localmente e aprovada por Bryan, que
autorizou commit/push/PR, revisão pela conta secundária e merge se aprovado,
seguido de publicação na mesma VM com prazo automático. Não altera contrato ESP, orçamento ou tátil.


### Entrada canônica e compartilhamento

Bryan pediu que o domínio puro permaneça na raiz inclusive antes do login.
A raiz entrega o formulário público ou o painel privado conforme a sessão;
login/saída não mudam o endereço visível. Os caminhos antigos de navegação
encaminham à raiz. Um card estático Open Graph de marca fica público para
prévia de links, sem capturas ou telemetria. A proteção de dados e os contratos
de escrita continuam iguais.


### Início automático aprovado — 04/11/2026

Bryan pediu que Iniciar no console EC2 também inicie a aplicação. A janela
passa a ser preparada automaticamente antes do Docker, com saldo persistido e
reserva limitada. Janela válida mantém o prazo; reboot não renova prazo vencido.
O teto de horas foi ampliado explicitamente de 8h para 8h30, mantendo US$15.
A janela atual continua tendo parada automática; não há serviço permanente.
Procedimento e limites: [início preservado](../aws-preserved-start.md).
