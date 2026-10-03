# Changelog

Todas as mudanças relevantes do Sonar Vision serão documentadas neste arquivo.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto pretende adotar [Versionamento Semântico](https://semver.org/lang/pt-BR/)
quando houver entregas executáveis.

## [Unreleased]

### Added

- Guia consolidado de instalação/execução e roteiro demonstrativo (#34),
  verificação offline dos comandos existentes, testes de sucesso/limites/falhas
  e formulário de reprodução por colega; rede e hardware reais não validados.

- Avaliação offline anotada (#33), métricas por classe/iluminação/cenário,
  revisão de tracking, escadas e latência, comparação e síntese agregada;
  fixtures/testes próprios, sem avaliação real ou aprovação de segurança.

- Catálogo proposto de frases (#32), manifesto versionado, validador de WAV/
  integridade e empacotamento offline com fixtures silenciosas e testes;
  aprovação, provedor/formato e lote final de voz pendentes.

- Cliente simulador dos óculos (#30), transporte HTTPS com certificado validado,
  fixtures determinísticas de falha, testes unitários e guia de execução;
  integração com API e hardware pendente.

- Protocolo proposto de avaliação visual (#7), manifesto sintético e validador
  de metadados com testes; coleta e aprovação experimental pendentes.

- Proposta de política de áudio (#5), seletor determinístico experimental (#31),
  testes sintéticos e roteiro de compreensão; integração e aprovação pendentes.

- Módulo experimental de detecção/tracking com isolamento por sessão, interface
  independente de HTTP, testes automatizados e benchmark sem publicação de mídia (#21).

- Licença AGPL-3.0-only e decisão de licenciamento.
- Política de segurança, Código de Conduta e metadados de citação.
- Regras iniciais para ignorar credenciais, mídia, datasets, modelos e artefatos
  de build.
- Documentos separados de arquitetura, roadmap e avaliação experimental.

### Changed

- README reorganizado para apresentar claramente o estágio experimental,
  limitações, segurança e caminhos para a documentação detalhada.
- Primeiros passos atualizados para refletir o fluxo atual do Kanban e a
  avaliação visual multiclasse.

## Política de versões

- Mudanças ainda não publicadas permanecem em `Unreleased`.
- Marcos experimentais podem ser publicados como pre-releases, por exemplo
  `v0.1.0-alpha.1`.
- A primeira versão estável somente será publicada quando existir uma entrega
  reproduzível, documentada e validada conforme seu escopo.

[Unreleased]: https://github.com/BryanPinheiro77/sonar-vision/commits/main
