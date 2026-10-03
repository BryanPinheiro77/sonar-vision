# Documentacao

Esta pasta concentra documentos que precisam acompanhar o projeto e permitir que suas decisoes e experimentos sejam compreendidos pelo grupo.

## Documentos atuais

- [Escopo da entrega acadêmica](ESCOPO.md)
- [Arquitetura inicial](ARCHITECTURE.md)
- [Catálogo versionado de frases e voz — #32](audio-catalog.md)
- [Política determinística de áudio — #5/#31](audio.md)
- [Cliente simulador dos óculos — #30](simulator.md)
- [Módulo de visão: interface, execução e testes](vision.md)
- [Contrato de eventos semânticos — experimental](protocol/README.md)
- [Roadmap](ROADMAP.md)
- [Primeiros passos](PRIMEIROS_PASSOS.md)
- [Experimentos e métricas](experiments/README.md)
- [Avaliação automatizada de visão e latência — #33](evaluation.md)
- [Protocolo de coleta e avaliação visual — #7](experiments/protocolo-visual.md)
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
