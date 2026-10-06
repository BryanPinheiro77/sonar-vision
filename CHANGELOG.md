# Changelog

Todas as mudanças relevantes do Sonar Vision serão documentadas neste arquivo.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto pretende adotar [Versionamento Semântico](https://semver.org/lang/pt-BR/)
quando houver entregas executáveis.

## [Unreleased]

### Added

- Trajetória aparente por timestamps e visualização com caixas/IDs (#11),
  condicionadas ao contexto da câmera; avaliação real independente pendente.
- Integração optativa da AudioPolicy com a API e testes do simulador #30 contra HTTPS real da #43, reutilizando a #27 com backend simulado; evidências e escopo parcial do PR #42 atualizados.

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
- API experimental `POST /v1/inference` somente em HTTPS, com credencial por
  dispositivo, validação estrita do contrato 0.1, backend simulado explícito,
  controle de concorrência/timeout sem fila e interface para a política de
  anúncios (#24).
- Proposta da interface de áudio local (#25): prioridades, urgência genérica
  sem rede, validade visual separada do estado local, catálogo instalado com
  avisos essenciais, comportamento em falhas, modelo de referência e exemplos
  verificáveis, sem alterar o contrato 0.1.
- Distribuição autenticada do catálogo de áudio (#26): validação do pacote na
  publicação (caminhos, integridade, formato, origem e licença), rotas
  `/v1/catalog/*` com ETag e `no-store`, e modelo de atualização no aparelho
  que não baixa durante urgência e mantém o catálogo anterior em falhas.
- Testes de integração e ponta a ponta (#27) sobre HTTPS real: credenciais,
  certificados, limites, sessões, timeout, `busy` sem acúmulo, cancelamento,
  respostas duplicadas/vencidas/fora de ordem, áudio até a arbitragem local,
  independência do caminho tátil simulado e benchmark opcional.
- Empacotamento da API (#28): `Dockerfile` e `compose.yaml` sem segredos nem
  pesos, usuário sem privilégios, porta somente em loopback, probe de saúde com
  validação de certificado, smoke test e documentação de execução reproduzível.
- Verificações automáticas de testes e documentação (#29): job `Docs and contracts`
  (links, JSON, índices de ADRs e docs), job final `CI result`, relatórios de teste
  com resumo e artefato, `--fail-on-skip` para impedir skips indevidos, cache do
  pip, cancelamento de execuções antigas e benchmark simulado apenas manual.

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
