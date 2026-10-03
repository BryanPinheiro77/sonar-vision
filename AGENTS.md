# Instrucoes para agentes de IA

## Contexto

O Sonar Vision e um projeto academico de tecnologia assistiva. Antes de realizar qualquer tarefa, leia o `README.md`, este arquivo e os documentos relacionados ao trabalho solicitado.

## Fontes de verdade

- `README.md`: visao geral, arquitetura e roadmap atual do projeto.
- `docs/decisions/`: decisoes de arquitetura ja aceitas e suas justificativas.
- Issue em andamento: objetivo e criterios de aceitacao da tarefa.
- PDFs em `docs/reference/`, quando essa pasta existir: detalhamento tecnico aprovado pelo grupo.
- Se essas fontes divergirem, nao escolha silenciosamente. Aponte o conflito e solicite uma decisao do grupo antes de implementar.

## Arquitetura

- O alerta imediato de seguranca deve funcionar localmente no ESP32-S3, sem depender de internet, VM, camera ou inferencia probabilistica.
- A VM adiciona semantica, tracking e telemetria; sua indisponibilidade nunca pode interromper o feedback tatil local.
- Nao introduza uma placa Edge como requisito. Essa opcao so pode ser adotada depois de um benchmark que demonstre sua necessidade.
- Quando o firmware existir, mantenha a logica de geometria, risco e TTC independente de hardware e testavel no computador.
- Nao altere silenciosamente pinos, limiares de risco, contratos de mensagens ou criterios experimentais. Registre decisoes relevantes em `docs/decisions/`.

## Stack e limites atuais

### Definido para o firmware

- Microcontrolador: ESP32-S3-WROOM-1 N16R8.
- Framework e build: Arduino-ESP32 com PlatformIO.
- Concorrencia: FreeRTOS.
- Linguagem: C++17.
- Sensores e atuadores previstos: VL53L5CX, BNO085, OV2640, DRV2605L com dois LRA, MAX98357A e transdutor de conducao ossea.
- Organizacao: logica pura em `core/`, acesso ao hardware em `drivers/` e orquestracao em `tasks/`.

### Baseline prevista para VM e visao computacional

- Python 3.11 ou superior.
- OpenCV, YOLOv8n e ByteTrack.
- FastAPI para a API de inferencia.
- MQTT com Mosquitto para telemetria e eventos.
- HTTP/TCP para o caminho inicial de frames e respostas.
- Docker Compose para executar os servicos.

Essa baseline ainda sera validada por benchmarks. Banco de dados, dashboard, provedor de nuvem e eventual hardware Edge continuam em avaliacao. Nao escolha, substitua ou adicione tecnologia sem uma necessidade registrada em issue e, quando afetar a arquitetura, em ADR.

## Licenciamento

- O código e a documentação próprios do projeto usam `AGPL-3.0-only`.
- Preserve avisos e licenças de dependências de terceiros.
- Não presuma que datasets, vídeos, pesos de modelos ou artefatos de hardware
  estão cobertos pela licença principal; verifique e documente cada origem.
- Antes de adicionar uma dependência, confira sua compatibilidade com a licença
  do projeto.

## Estado do repositorio

- Existe o módulo visual experimental da #21 em `src/sonar_vision/`, sem API
  ou hardware integrados. Consulte `docs/vision.md` antes de alterá-lo.
- Testes do núcleo: `PYTHONPATH=src python -m unittest discover -s tests -v`.
  Os testes do ByteTrack real exigem `python -m pip install -e '.[vision]'`;
  sem dependências opcionais, aparecem como skipped, não como validação real.
- API experimental da #24 em `src/sonar_vision_api/`, separada do módulo
  visual; consulte `docs/api.md`. Testes HTTP/HTTPS exigem
  `python -m pip install -e '.[api,api-dev]'`; sem esses extras aparecem
  como skipped.
- Proposta da interface de áudio local (#25) em `docs/protocol/audio-local.md`,
  com modelo de referência em `src/sonar_vision_local_audio/` (não é
  firmware). Exemplos: `PYTHONPATH=src python -m sonar_vision_local_audio.examples docs/protocol/exemplos-audio-local.json`.
- Não invente comandos de build, teste ou deploy dos demais módulos.
- Crie pastas de firmware, nuvem, ML, hardware, analise ou testes apenas quando uma issue autorizar o primeiro artefato real daquele modulo.
- Quando os comandos reais passarem a existir, documente-os no README do modulo e atualize este arquivo apenas com os comandos que todos os agentes precisam executar.

## Forma de trabalhar

- Nao crie codigo, dependencias ou infraestrutura antes de uma issue definir objetivo e criterio de aceitacao.
- Prefira mudancas pequenas, revisaveis e associadas a uma issue.
- Diferencie explicitamente requisito confirmado, hipotese e sugestao. Nunca apresente uma escolha inventada pela IA como decisao do grupo.
- Explique no pull request por que a solucao foi escolhida, quais alternativas foram consideradas e como ela foi validada.
- Evite abstracoes, servicos, dependencias e configuracoes para necessidades futuras ainda nao demonstradas.
- Toda contribuicao apoiada por IA deve ter uma pessoa responsavel capaz de explicar o funcionamento, os riscos e o teste realizado.
- Nunca versione credenciais, chaves, dados pessoais, videos de participantes, datasets brutos ou pesos grandes de modelos.
- Testes com participantes exigem consentimento, supervisao e avaliacao das exigencias eticas da instituicao.
- Nao apresente o prototipo como dispositivo medico ou substituto de bengala, cao-guia ou orientacao profissional.
- Nao faca commit, push ou merge sem solicitacao explicita de uma pessoa do grupo.

## Antes de concluir uma tarefa

- Execute as verificacoes aplicaveis e informe seus resultados.
- Verifique que o modo tatil local continua independente da nuvem.
- Atualize a documentacao quando houver mudanca de arquitetura, contrato ou procedimento.
- Informe claramente tudo que nao foi validado, especialmente quando depender de hardware.
