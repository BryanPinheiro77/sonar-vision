# Reprodução por outro integrante — #34

Organização: Matheus. Preparação do roteiro: Bryan. Atualização: 2026-10-16.
Este roteiro verifica instalação e execução de software no computador.
Não precisa de placa, vídeo, modelo, AWS, token ou provedor de voz.

## O que falta para fechar a issue

A #34 pede execução por **outra pessoa**, em checkout limpo. A verificação
automatizada preparada aqui não substitui esse aceite. Um integrante diferente
do autor do guia deve executar os passos e relatar o que observou. Matheus
consolida o retorno; não há resultado humano preenchido antecipadamente.

## 1. Obter a revisão publicada

Usar diretório novo. Git e Python >=3.11 com pip/venv precisam estar instalados.
Internet é usada para clone e ferramentas de build; os cenários depois da
instalação são sintéticos e locais.

Revisão de software congelada para esta reprodução:
`6943e82e47a5b4e2f41d68393c32fb6557d2c131`, na main após PR #62.
O roteiro pode ser atualizado em PR documental posterior; registrar sempre
o SHA efetivamente executado, sem chamá-lo de modelo ou firmware validado.

```sh
git clone https://github.com/BryanPinheiro77/sonar-vision.git sonar-vision-review
cd sonar-vision-review
git checkout --detach 6943e82e47a5b4e2f41d68393c32fb6557d2c131
git status --short
git rev-parse HEAD
```

Os comandos Git também funcionam no PowerShell; usar `Set-Location` se preferir.
O status deve estar vazio antes de criar o ambiente. Não copiar .venv, pesos,
vídeos ou credenciais de outro computador. Checkout detached é intencional:
esta pasta serve para revisar uma versão fixa, sem modificar branches de trabalho.

## 2. Instalar e verificar

### macOS/Linux — shell POSIX

```sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip check
.venv/bin/python -B scripts/run_tests.py --report-dir results/issue-34/tests-01
.venv/bin/python -B -m sonar_vision.smoke --output results/issue-34/smoke-01.json
```

### Windows — PowerShell

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B scripts/run_tests.py --report-dir results/issue-34/tests-01
.\.venv\Scripts\python.exe -B -m sonar_vision.smoke --output results/issue-34/smoke-01.json
```

Usar o executável explícito evita ativação de scripts e mistura de ambientes.
O caminho POSIX foi exercitado em macOS; esta atualização não representa uma
nova execução Windows/Linux. Se a instalação falhar, registrar a etapa e a
dificuldade; não contornar silenciosamente com Python global ou ambiente alheio.
Ao repetir, usar novos nomes de output; não sobrescrever evidências anteriores.

## 3. Conferir o resultado

- `pip check`: sem dependências quebradas.
- `results/issue-34/tests-01/report.json`: passed=true, failures=errors=0;
  examinar a lista de skipped e seus motivos. Sem extras, API/ByteTrack e
  detector real podem ser ignorados; não interpretar isso como validação real.
- `results/issue-34/smoke-01.json`: passed=true, 16 checks aprovados e
  human_checkout_review=pending. Os campos real_vision_validated,
  network_validated e hardware_validated devem continuar false nesse smoke.
- Entender os resultados: sucesso roteirizado, descarte por timeout/expiração,
  orientação/urgência simuladas e catálogo sem voz. Não houve captura real,
  fala ou motor. Contagens de TP/FP/FN da fixture não são acurácia de YOLO.

O campo human_checkout_review do smoke permanece pending por projeto; não
editá-lo para simular uma confirmação. A confirmação humana é registrada
separadamente no formulário abaixo, após a pessoa executar e conferir.

## 4. Exercício opcional: avaliação de movimento

Usar o mesmo Python do ambiente; o exemplo abaixo é POSIX:

```sh
.venv/bin/python -B -m sonar_vision.evaluate_motion \
  --snapshot docs/experiments/issue-33-fixture.json \
  --motion docs/experiments/issue-11-motion-fixture.json \
  --output results/issue-34/motion-01.json
```

No PowerShell, usar `.\.venv\Scripts\python.exe` e colocar os argumentos em
uma linha. Resultado esperado: known_truth=6, correct=2 e
acceptance_evaluated=false. Erros/abstenções são intencionais da fixture,
não falha de instalação. Não precisa de vídeos para esse exercício.

## 5. Retorno do integrante

Preencher após executar, sem tokens, endereços, logs completos ou caminhos
pessoais. Guardar relatórios detalhados localmente; encaminhar só síntese
revisada por canal autorizado. Este roteiro não envia mensagens a colegas.

| Campo | Preenchimento |
|---|---|
| Integrante responsável e data | Pendente |
| SHA conferido e status inicialmente vazio | Pendente |
| Sistema e versão Python | Pendente |
| Instalação e pip check | Pendente |
| Testes: total/falhas/erros/skips e motivos | Pendente |
| Smoke: passed e 16 checks | Pendente |
| Etapa que exigiu ajuda ou divergiu | Pendente |
| O que foi entendido sobre sintético/real/hardware | Pendente |
| Conclusão sobre reprodução do guia | Pendente |

Referências: [guia completo](execution.md), [demonstração](demo.md),
[evidência automatizada atual](experiments/issue-34-clean-checkout.md).
Com confirmação humana revisada e demais critérios conferidos, a #34 poderá
ser encerrada. Hardware permanece nas #17/#18/#19, com Mathias, Tarcísio e Weslley.
