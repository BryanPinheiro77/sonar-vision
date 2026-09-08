# Experimentos e métricas

Todo experimento deve registrar data, versão do código, configuração, cenário,
procedimento, resultado e limitações. Resultados sem contexto não devem ser
comparados diretamente.

## Visão computacional

- classes observadas e confiança;
- precision, recall e mAP quando houver dados anotados;
- FPS efetivo;
- latência média e percentis de inferência;
- falsos positivos e falsos negativos observados.

## Tracking

- estabilidade do `track_id`;
- perdas de rastreamento;
- trocas de ID;
- duração das trilhas;
- comportamento durante oclusões e cruzamento de pessoas.

Os cenários controlados iniciais incluem aproximação, travessia lateral, duas
pessoas cruzando em sentidos opostos e fluxo livre com múltiplas pessoas.

## Camada local

- latência do sensor ao alerta;
- frequência efetiva do laço;
- erro de distância e TTC;
- precisão do setor indicado;
- falsos alertas;
- comportamento com diferentes inclinações da cabeça.

## Comunicação e sistema

- latência ESP32 → VM → ESP32;
- taxa de frames e volume transmitido;
- perda e descarte de frames;
- tempo de antecipação do alerta;
- comportamento durante perda de rede ou VM;
- manutenção do feedback tátil local durante falhas externas.

## Dados e privacidade

Vídeos de participantes, datasets brutos e resultados volumosos não devem ser
enviados ao Git. Antes de gravar pessoas identificáveis, o grupo deve verificar
consentimento, supervisão e exigências éticas da instituição.

O repositório deve guardar scripts, metadados não identificáveis, configurações
e instruções suficientes para reproduzir a avaliação. Se armazenamento externo
for necessário, sua política de acesso e retenção deverá ser documentada antes
do uso.
