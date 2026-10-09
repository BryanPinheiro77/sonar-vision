# Documentacao

Esta pasta concentra documentos que precisam acompanhar o projeto e permitir que suas decisoes e experimentos sejam compreendidos pelo grupo.

## Documentos atuais

- [#4: perfil experimental aprovado de feedback háptico e latência local](protocol/haptic-local.md)

- [Guia consolidado de execução e instalação — #34](execution.md)
- [Roteiro demonstrativo e revisão por colega — #34](demo.md)
- [Escopo da entrega acadêmica](ESCOPO.md)
- [Arquitetura inicial](ARCHITECTURE.md)
- [Catálogo versionado de frases e voz — #32](audio-catalog.md)
- [Política determinística de áudio — #5/#31](audio.md)
- [Cliente simulador dos óculos — #30](simulator.md)
- [Módulo de visão: interface, execução e testes](vision.md)
- [Trajetória aparente e janela com caixas/IDs](trajectory.md)
- [Releases e obtenção dos modelos treinados](releases.md)
- [API de inferência HTTPS — experimental](api.md)
- [Distribuição do catálogo de áudio — experimental](catalog-distribution.md)
- [Testes de integração e ponta a ponta](integration.md)
- [Empacotamento e execução reproduzível (Docker)](packaging.md)
- [CI e marcos de software](ci.md)
- [Contrato de eventos semânticos — experimental](protocol/README.md)
- [Interface de áudio local e catálogo de vozes — proposta](protocol/audio-local.md)
- [Roadmap](ROADMAP.md)
- [Primeiros passos](PRIMEIROS_PASSOS.md)
- [Experimentos e métricas](experiments/README.md)
- [Investigação de escadas e sentido — #16](experiments/issue-16.md)
- [Avaliação automatizada de visão e latência — #33](evaluation.md)
- [Protocolo de coleta e avaliação visual — #7](experiments/protocolo-visual.md)
- [Perfil local e plano de dimensionamento da #22](experiments/issue-22.md)
- [Proposta de metas, carga e orçamento — #22](experiments/issue-22-proposta.md)
- [Comparação controlada de threads de CPU — #22](experiments/issue-22-cpu.md)
- [Decisões de arquitetura](decisions/README.md)

## Organização prevista

- `reference/`: documentos tecnicos aprovados pelo grupo;
- `decisions/`: decisoes de arquitetura (ADRs);
- `protocol/`: contratos ESP32 ↔ VM e topicos MQTT;
- `experiments/`: roteiros, critérios e planos de medição;
- `assembly/`: diagramas eletricos e instrucoes de montagem.

As subpastas devem ser criadas somente quando receberem o primeiro arquivo real.

Os seis PDFs tecnicos iniciais devem ser adicionados em `docs/reference/` depois que o grupo confirmar quais copias representam a versao oficial. Evitem manter versoes divergentes em computadores pessoais.

Qualquer decisao que contradiga um documento de referencia deve gerar um ADR e, depois, a revisao do documento afetado.

- [Serviço real e avaliação integrada (#52)](integrated-service.md).

- [Classes de detecção e limites atuais](detections.md).

- [Primeiro acesso AWS](aws-start.md).

- [Resultado AWS com r21: desempenho, qualidade conhecida e limpeza](experiments/issue-22-aws-results.md).

- [Investigação CPU no Free plan (#22)](experiments/issue-22-cpu-investigation.md).

- [Comparação CPU4 e diagnóstico de rede (#22)](experiments/issue-22-cpu4-results.md).

- [Reteste AWS com rede estável (#22)](experiments/issue-22-stable-results.md).



- [Conclusão experimental aprovada da #22](experiments/issue-22-conclusao.md).
- [Reprodução do benchmark e agregação pública](experiments/issue-22-reproduce.md).

- [Operação experimental AWS (#23)](aws-operation.md).

- [Resultado operacional AWS da #23](experiments/issue-23-results.md).

- [#23: diagnóstico, reboot/prazo real e limpeza](experiments/issue-23-cadence-results.md).
