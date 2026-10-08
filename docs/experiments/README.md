# Experimentos e métricas

- [Execução reproduzível e evidência offline — #34](issue-34.md)

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
## Módulo visual — evidência disponível

- [Issue #21: testes, benchmark e síntese do laboratório](issue-21.md).
- [Issue #11: trajetória, câmera e avaliação pendente](issue-11.md).
- [Issue #16: investigação de escadas e sentido](issue-16.md).
- [Issue #22: perfil local e plano de dimensionamento](issue-22.md).
- [Issue #22: proposta de metas, carga oferecida e orçamento](issue-22-proposta.md).
- [Issue #22: ensaio sintético de um/dois clientes e dois pesos](issue-22-load-synthetic.md).
- [Issue #22/#11: correção de cadência e ensaio com oferta de 10/s](issue-22-cadence.md).
- [Issue #22: comparação controlada de threads de CPU](issue-22-cpu.md).
- [Proposta de próxima avaliação — #11/#16/#7](proposta-avaliacao-11-16.md).

## Áudio — evidência sintética

- [Issues #5/#31: procedimento, resultados e limitações](issue-5-31.md).

## Avaliação visual — protocolo #7

- [Cenários, coleta, anotação, métricas e verificação](protocolo-visual.md).
- [Exemplo sintético de manifesto; sem vídeos reais](manifest-example.json).

## Avaliação automatizada — #33

- [Formato, cálculos, comandos e limitações](../evaluation.md).
- [Fixture anotada sintética, sem vídeo real](issue-33-fixture.json).
- [Síntese agregada da fixture e evidências locais](issue-33-sintese.md).
- [Issue #27: integração e ponta a ponta](issue-27.md).

- [Benchmark com cliente/servidor separados (#22)](issue-22-remote.md).

- [Perfil r21 autorizado para AWS e rollback r20](issue-22-r21-profile.json).

- [Resultado AWS com r21: desempenho, qualidade conhecida e limpeza](issue-22-aws-results.md).

- [Proposta histórica CPU4 e pré-verificação](issue-22-cpu4-proposal.json).
- [Perfil por modelo no Mac: diagnóstico local, não capacidade EC2](issue-22-native-model-profile.json).
- [Investigação CPU no Free plan: paralelo, memória e remoção](issue-22-cpu-investigation.md).
- [Paralelo local no Mac: resultados e limitações](issue-22-parallel-local.json).
- [CPU4: diagnóstico da rede, HTTPS local, qualidade e remoção](issue-22-cpu4-results.md).

- [Reteste CPU4 com rede estável: três rodadas, um óculos e remoção](issue-22-stable-results.md).


- [Conclusão experimental aprovada da #22](issue-22-conclusao.md).
- [Reprodução do benchmark e agregação pública](issue-22-reproduce.md).
