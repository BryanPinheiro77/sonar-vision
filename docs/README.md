# Documentacao

Esta pasta concentra documentos que precisam acompanhar o projeto e permitir que suas decisoes e experimentos sejam compreendidos pelo grupo.

## Documentos atuais

- [Escopo da entrega acadêmica](ESCOPO.md)
- [Arquitetura inicial](ARCHITECTURE.md)
- [Módulo de visão: interface, execução e testes](vision.md)
- [API de inferência HTTPS — experimental](api.md)
- [Distribuição do catálogo de áudio — experimental](catalog-distribution.md)
- [CI e marcos de software](ci.md)
- [Contrato de eventos semânticos — experimental](protocol/README.md)
- [Interface de áudio local e catálogo de vozes — proposta](protocol/audio-local.md)
- [Roadmap](ROADMAP.md)
- [Primeiros passos](PRIMEIROS_PASSOS.md)
- [Experimentos e métricas](experiments/README.md)
- [Perfil local e plano de dimensionamento da #22](experiments/issue-22.md)
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
