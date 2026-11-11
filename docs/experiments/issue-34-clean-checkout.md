# #34 — reprodução automatizada em checkout limpo

Data: 2026-10-16. Preparação: Bryan. Organização da issue: Matheus.
**Confirmação por outro integrante continua pendente.**

[Roteiro curto](../checkout-review.md) · [guia completo](../execution.md) ·
[resultado agregado](issue-34-clean-checkout.json).

## Execução

Clone novo do repositório público, checkout detached da revisão publicada
`6943e82e47a5b4e2f41d68393c32fb6557d2c131`, status inicialmente vazio.
macOS/Python 3.11.16, novo venv sem site-packages compartilhados, instalação
editable sem extras. PYTHONPATH e variáveis de token/peso/API não foram
herdados para a execução; importação conferida dentro do clone novo.
Nenhum .venv, segredo, peso, mídia ou resultado privado anterior foi copiado.

| Etapa | Resultado |
|---|---|
| Clone público e checkout da revisão publicada | Sucesso; git status inicial vazio |
| Criação de venv e pip install -e . | Sucesso |
| pip check | Sem dependências quebradas |
| scripts/run_tests.py | 389 encontrados; 312 aprovados, 77 skipped; 0 falhas/erros |
| sonar_vision.smoke | Retorno0,passed=true, 16 checks satisfeitos |
| sonar_vision.evaluate_motion | Retorno 0 com fixture sintética, 6 verdades conhecidas/2 estados corretos |
| Origem do pacote importado | Clone novo, sem importar o workspace anterior |

Os skips correspondem a extras de API/visão e detector real não instalados/não
configurados. Motivos e quantidades constam no JSON agregado. Não são falhas,
mas também não comprovam HTTPS ou ByteTrack reais nesta execução mínima.
Os cenários do smoke são sintéticos/em memória; network_validated e
hardware_validated permanecem false. O smoke não mede latência de rede ou
qualidade do modelo. As falhas de movimento da fixture são respostas conhecidas
intencionais, não resultado visual real ou falha de instalação.

## Comandos reproduzidos

Na raiz do clone novo, após escolher o commit publicado:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip check
.venv/bin/python -B scripts/run_tests.py --report-dir results/issue-34/tests-01
.venv/bin/python -B -m sonar_vision.smoke --output results/issue-34/smoke-01.json
.venv/bin/python -B -m sonar_vision.evaluate_motion --snapshot docs/experiments/issue-33-fixture.json --motion docs/experiments/issue-11-motion-fixture.json --output results/issue-34/motion-01.json
```

Os nomes 01 são de uma execução nova; usar outro nome ao repetir. Logs de
instalação/importação e relatórios detalhados permanecem privados sob .local/.
O repositório publica somente síntese sem caminhos pessoais, tokens ou mídia.

## O que esta entrega resolve

- Atualiza guias que ainda afirmavam ausência de Docker/Compose e não integração
  da API/cliente, apesar dos PRs já mergeados.
- Acrescenta o roteiro curto de revisão por colega, com SHA fixo e resultados
  esperados, incluindo distinção explícita entre mínimos/extras e sintético/real.
- Mantém dados históricos datados sem usá-los como retrato do estado atual.

Nenhum código, dependência, contrato, modelo ou configuração de execução foi
alterado por esta atualização. Não exige novo ADR de arquitetura.

## Pendência de aceite

A execução automatizada não se apresenta como outra pessoa. Um integrante
diferente do autor do guia precisa executar e preencher o retorno, relatando
dificuldades e interpretação. Não fechar #34 nem alterar o campo humano do
smoke para simular essa confirmação. Guia de apoio ao trio de modelo/cloud;
firmware e bancada continuam com Mathias, Tarcísio e Weslley.
