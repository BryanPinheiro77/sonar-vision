# Primeiros passos do grupo

## Semana 1: alinhar antes de implementar

- [ ] Escrever uma frase unica de escopo para o MVP.
- [ ] Fechar os cenarios internos e as classes prioritarias; `pessoa` deve ser a primeira classe visual.
- [ ] Confirmar o modelo exato do ESP32-S3, PSRAM, camera e interfaces.
- [ ] Revisar a licenca do detector e registrar a escolha.
- [ ] Definir responsaveis por firmware/hardware, nuvem/telemetria, ML/tracking e experimento/documentacao.
- [ ] Transformar as primeiras entregas em issues com criterios de aceitacao.
- [ ] Criar um GitHub Project com `Backlog`, `Pronto`, `Em andamento`, `Em revisao` e `Concluido`.
- [ ] Comprar primeiro ESP32-S3, VL53L5CX e BNO085; nao comprar Edge.
- [ ] Consultar cedo as exigencias do comite de etica antes de testes formais com participantes.

## Primeiras discussoes tecnicas

### Firmware e bancada

- Definir quais componentes serao testados isoladamente e em qual ordem.
- Confirmar a placa antes de escolher configuracoes do PlatformIO.
- Definir como a latencia tatil sera medida; a meta inicial e abaixo de 100 ms.
- Manter geometria, risco e TTC testaveis sem depender do hardware fisico.

### Nuvem e telemetria

- Definir quais dados realmente precisam sair do dispositivo.
- Escolher o formato inicial das mensagens e os topicos MQTT.
- Planejar testes com mensagens simuladas antes da integracao com o firmware.
- Definir desde o inicio como credenciais e configuracoes locais serao protegidas.

### Visao computacional

- Comecar com a classe `pessoa` de um detector pre-treinado.
- Definir os videos e cenarios que serao usados na avaliacao inicial.
- Registrar desde o primeiro teste FPS, latencia, confianca e falhas observadas.
- Adicionar tracking somente depois que a deteccao estiver medida.

### Hardware, experimento e documentacao

- Manter uma tabela unica de componentes e, futuramente, de pinos.
- Definir como latencia, TTC, falsos alertas e ID switches serao medidos.
- Planejar um diario de bancada contendo data, versao, configuracao, procedimento e resultado.
- Avaliar consentimento, supervisao e requisitos eticos antes de envolver participantes.

## Primeiro marco

O primeiro marco nao e ter IA. E demonstrar um wearable local que:

- comunica lado e proximidade por vibracao;
- evita interpretar o piso como obstaculo durante inclinacoes da cabeca;
- mantem o alerta tatil abaixo de 100 ms;
- envia telemetria para o broker;
- continua funcionando em modo seguro quando Wi-Fi e VM sao desligados.
