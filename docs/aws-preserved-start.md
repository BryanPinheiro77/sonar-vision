# Ligar a instância preservada — #23/#73

Bryan autorizou iniciar a aplicação ao ligar a EC2 pelo console em 04/11/2026.
O fluxo anterior exigia armar um prazo via operador antes do Docker; sem isso,
StartInstances deixava o serviço bloqueado. A alteração não cria outra VM,
IP, banco, credencial AWS ou serviço pago.

## Para usar

No console AWS, selecionar São Paulo e a instância preservada; usar **Iniciar**.
Aguardar a inicialização e abrir `https://sonar-vision.bryandev.com.br/`.
A própria raiz mostra o login ou o painel, conforme a sessão. Reiniciar a API
invalida a sessão do navegador; usuário e senha de leitura permanecem os mesmos.
Não é necessário executar Compose ou provisionamento por SSH depois de Iniciar.
Para terminar antes do prazo, usar **Parar**, preservando a VM e o endereço.

Cada janela tem até 20 minutos, limitada ao saldo de tempo explicitamente
aprovado. O teto acumulado foi ampliado de 8h para **8h30** por Bryan, mantendo
**US$15**. Isso não autoriza operação contínua ou renovações ilimitadas. Quando
o saldo se esgotar, o sistema recusa outra janela; ampliar exige autorização.
Disco/IP reservado continuam tendo custo com a VM parada; o AWS Budget é alerta,
não bloqueio de cobrança.

## Como funciona

- `sonar23-auto-window.service`, antes do Docker, executa
  [aws_preserved_boot.py](../scripts/aws_preserved_boot.py) na própria EC2.
  Usa IMDSv2 local, sem chave IAM, para identificar a ativação (`pendingTime`).
- `/var/lib/sonar23/auto-start.json`, root/0600, guarda instância, ativação,
  prazo absoluto e saldo restante em segundos. O operador inicializa esse saldo
  descontando a janela atual; não gravar segredos nesse arquivo.
- Uma janela ainda válida continua com o mesmo prazo, mesmo em reboot ou
  Stop/Start antecipado. Reboot da mesma ativação não renova janela vencida.
- Uma ativação EC2 nova com prazo vencido reserva o menor valor entre 20 minutos
  e o saldo; o prazo conta desde o horário da ativação. A reserva acontece antes
  de armar o timer, evitando crédito duplicado numa falha/repetição.
- O timer absoluto depende da preparação da janela. O Docker depende de ambos
  e mantém sua verificação prévia. `sonar23-application.service` executa Compose
  com os seis arquivos da implantação atual, inclusive o healthcheck do domínio.
- Falha na preparação/aplicação aciona a parada da instância. O guard de boot
  anterior continua como proteção adicional. Nenhum caminho termina a instância.

As unidades são instaladas por [install_preserved_autostart.sh](../scripts/install_preserved_autostart.sh).
O operador fornece o saldo inicial aprovado em arquivo privado; reinstalar não
sobrescreve um saldo já existente. A configuração concreta e o backup ficam no
registro operacional privado do deploy. O saldo do servidor passa a ser a fonte operacional para
inícios pelo console; não rearmar o timer usando o antigo helper de janelas,
que desconhece reservas posteriores feitas automaticamente.

## Validação e limites

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_aws_preserved_boot.py -v
```

Os testes puros cobrem preservação do prazo, ativação nova, reserva limitada,
quota vazia, repetição idempotente e identidade/estado inválidos. Não alteram
AWS ou arquivos de sistema. O procedimento de instalação exige backup,
`systemd-analyze verify`, verificação do timer e um Stop/Start real sem comandos
de provisionamento depois do Start. O ensaio real de 04/11 passou: depois de StopInstances/StartInstances, HTTPS
voltou sem provisionamento posterior por SSH; a ativação mudou e o prazo/saldo
permaneceram iguais porque a janela ainda era válida. Evidência privada
`STOP-START-RESULT.json`. A reserva de uma nova janela vencida foi validada nos
testes puros; não se gastou outra janela para simular esgotamento real.

Um erro de rede/IMDS ou configuração impede o início; conferir os journals das
unidades via SSH. Não afirmar que a bancada ESP, modelo ou tátil foram validados
por esse teste. O caminho tátil local permanece independente da VM.
