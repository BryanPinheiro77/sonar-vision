# Changelog

Todas as mudanças relevantes do Sonar Vision serão documentadas neste arquivo.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto pretende adotar [Versionamento Semântico](https://semver.org/lang/pt-BR/)
quando houver entregas executáveis.

## [Unreleased]

### Added

- Trajetória aparente por timestamps e visualização com caixas/IDs (#11),
  condicionadas ao contexto da câmera; avaliação real independente pendente.

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
