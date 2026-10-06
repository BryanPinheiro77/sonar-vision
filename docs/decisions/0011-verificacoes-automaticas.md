# 0011 — Verificações automáticas de testes e documentação no CI (proposta)

- Status: proposta da #29, para revisão do grupo.
- Data: 2026-10-03.
- Responsável: Julio.
- Relacionadas: #29, #38 (CI base), #24, #27, #28.

> Numeração: 0005 e 0006 não existem na `main`. O ADR 0010 da #28 foi
> incorporado pelo PR #47; este documento mantém o número 0011.

## Contexto

O CI da #38 já roda Ruff, testes e revisão de dependências, mas não verificava
a documentação, não publicava relatórios, aceitava testes ignorados por
dependência ausente como se fossem validação, e não tinha um check único para
a proteção da `main`. A #29 pede verificações reproduzíveis, com retorno claro,
sem segredos, câmera ou hardware.

## Decisão proposta

1. Manter o workflow `ci.yml` e os nomes dos checks existentes (a proteção da
   `main` depende deles) e acrescentar `Docs and contracts` e `CI result`.
2. Verificar a documentação com `scripts/check_docs.py`, só biblioteca padrão e
   sem rede: links e âncoras relativas, JSON de `docs/` sem chave duplicada,
   índice de ADRs e índice de `docs/`. Os exemplos dos contratos já são
   validados por testes existentes, que passam a rodar também nesse job.
3. Executar a suíte por `scripts/run_tests.py`, que gera `report.json` e
   `report.md` (contagens, skips com motivo, primeira linha de cada falha) e
   permite `--fail-on-skip` para que um job não passe com o teste que o
   justifica ignorado. O resumo vai para a aba do job e o relatório vira
   artefato por 14 dias.
4. Permissões `contents: read`, gatilho `pull_request` (nunca
   `pull_request_target`), `persist-credentials: false`, actions fixadas por
   hash, `timeout-minutes` por job, cancelamento de execuções antigas e cache
   do pip chaveado em `pyproject.toml`.
5. O benchmark continua fora do caminho de PR: workflow manual
   (`workflow_dispatch`), com backend simulado, que anexa o relatório.
6. Testes de contrato do próprio workflow (`tests/test_ci_tools.py`) impedem
   regressão dessas regras sem revisão.
7. O job `Container smoke` da #28 participa de `gate.needs`, tem timeout de
   25 minutos e checkout sem credenciais persistidas. Sua falha ou cancelamento
   reprova também `CI result`, sem exigir pesos ou câmera no smoke.

## Alternativas consideradas

- **Verificador de links de terceiros (por exemplo, lychee, markdownlint):**
  exigiria nova action ou dependência, e verificar links externos dependeria
  da rede. Fica como evolução, se o grupo quiser.
- **`pytest` com `junit-xml`:** mudaria o executor de testes do projeto sem
  necessidade; o `unittest` atual cobre o que é preciso.
- **Comentário automático no PR com o relatório:** exigiria permissão de
  escrita em `pull-requests`, que não é concedida a PRs de fork e ampliaria a
  superfície; o resumo na aba do job e o artefato bastam.
- **Executar o benchmark em todo PR:** números dependem do runner e gerariam
  falhas intermitentes sem relação com o código.

## Consequências

- Os checks `Docs and contracts`, `API tests` e `CI result` só bloqueiam o
  merge depois que um administrador os incluir na proteção da `main`.
- O CI continua sem validar acurácia visual, hardware, firmware ou latência.
- Links externos podem quebrar sem que o CI perceba.
- A cobertura de skips depende dos textos de motivo dos testes (`install .[api`,
  `real ByteTrack`); quem mudar essas mensagens deve atualizar o workflow.
