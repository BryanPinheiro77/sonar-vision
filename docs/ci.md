# CI e marcos de software — #38

O workflow [CI](../.github/workflows/ci.yml) roda em PRs para `main` e em
commits integrados à `main`. Ele não executa firmware, API, deploy, câmera ou
inferência com pesos. Nenhum segredo ou mídia é necessário.
As actions externas estão fixadas por hash de commit, com versão indicada no
arquivo, para que uma atualização de tag não altere o CI sem revisão.

| Verificação | O que cobre | Limite |
| --- | --- | --- |
| Quality | Ruff para erros de importação/sintaxe e compilação de Python | Não prova comportamento nem segurança física |
| Unit tests | Suíte `unittest` em Python 3.11 e 3.13, sem extras | Testes do ByteTrack aparecem como skipped |
| Vision integration | Instala `.[vision]`, confirma os módulos e roda testes reais do ByteTrack e suíte completa | Usa caixas fabricadas; não baixa pesos nem mede acurácia |
| API tests | Instala `.[api,api-dev]`, confirma os módulos e roda os testes da #24, incluindo HTTPS real com CA local temporária | Backend simulado; não mede latência nem integra o detector real. Ainda não é check obrigatório da `main` até um administrador incluí-lo |
| Dependency review | Bloqueia dependências novas/alteradas com vulnerabilidade conhecida de severidade alta ou crítica em PRs | Depende do Dependency Graph e dos avisos disponíveis no GitHub; não audita automaticamente todo o histórico |

Os testes do ByteTrack são ignorados quando faltam dependências opcionais.
Por isso, o job Vision integration instala o extra fixado em `pyproject.toml` e
confirma os imports antes dos testes. Um resultado verde apenas do job Unit
tests não é validação do tracker real. O projeto não tem lockfile universal;
versões transitivas podem variar e o CI não substitui revisão de dependências.

Comandos correspondentes para reproduzir localmente, na raiz:

```sh
python -m pip install -e .
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip install -e '.[vision]'
PYTHONPATH=src python -m unittest discover -s tests -v
```

Ruff é ferramenta exclusiva do CI nesta etapa, fixada no workflow. O perfil
seleciona `E4,E7,E9,F`; ampliar as regras exige verificar primeiro a base atual
e revisar os ajustes resultantes. A revisão de dependências usa o serviço do
GitHub em PRs; não precisa de credencial adicionada ao repositório.

## Proteção da `main`

A `main` exige PR, uma aprovação de outro colaborador e resolução das conversas.
Novos commits invalidam aprovações anteriores; o último envio precisa de uma
aprovação independente. Administradores seguem a mesma regra. Force push e
exclusão da branch estão bloqueados. Os cinco checks anteriores à #24 (Quality,
os dois Unit tests, Vision integration e Dependency review) são obrigatórios
e a branch do PR deve estar atualizada com `main`. Eles passaram pela primeira
vez no PR #39; branches antigas precisam incorporar esse CI para poder receber
merge após revisão humana.

## Releases de software

O workflow [Release software](../.github/workflows/release.yml) só reage a tags
`vX.Y.Z` ou `vX.Y.Z-sufixo`. Antes de publicar, confirma que o commit da tag
pertence à história de `main`, instala `.[vision]` e executa a suíte. Uma tag
inválida ou teste com falha não cria release. O job de publicação recebe apenas
`contents: write` do token automático do GitHub; os outros jobs usam leitura.
Merge de PR sozinho não cria release.

Após revisão do grupo, escolha um commit já integrado e uma versão ainda livre.
Exemplo de procedimento manual, executado por pessoa autorizada:

```sh
git fetch origin main
git tag -a v0.1.0-alpha.1 origin/main -m "Sonar Vision v0.1.0-alpha.1"
git push origin v0.1.0-alpha.1
```

Esse exemplo mostra o formato, não autoriza publicar essa versão agora. Confira
as notas geradas, os testes e as limitações antes de divulgar o marco. Sufixo
como `-alpha.1` gera pré-release. Tags `model-*` não acionam este workflow;
pesos são artefatos separados, com origem, licença, hash e limitações próprias.
Não anexar imagens, vídeos, datasets, credenciais ou pesos ao release de software.

### Primeiro marco proposto

Proposta para revisão do grupo: `v0.1.0-alpha.1`, correspondente à versão
`0.1.0a1` já declarada em `pyproject.toml`. O escopo inclui o módulo visual
experimental da #21, o perfil local da #22 integrado pelo PR #40 e o CI e
procedimento de releases da #38, com sua documentação e testes. O perfil local
não conclui o dimensionamento da infraestrutura. A entrega não inclui o sistema
vestível integrado, API, firmware ou modelo de escadas da #16.

Antes de enviar a tag, revisar e integrar o PR deste procedimento, escolher o
commit da `main`, conferir seu CI e obter a aprovação do grupo para publicar o
marco. A tag ainda não foi enviada e a publicação automática por tag continua
sem validação real. Os comandos de exemplo abaixo não autorizam publicação.

### Conferir publicação e download do software

Depois do envio autorizado da tag:

1. No GitHub Actions, abrir a execução de **Release software** da tag e
   confirmar sucesso de **Verify software tag** e **Create GitHub Release**.
   Conferir que o commit corresponde ao marco escolhido e que os testes reais
   do ByteTrack executaram, sem skips por dependências ausentes.
2. Conferir a Release, o indicador de pré-release e as notas geradas. Completar
   manualmente as notas com escopo, instruções de execução, resultado dos testes
   e limitações; não anunciar funcionalidades ainda ausentes ou não validadas.
3. Baixar o código-fonte do marco em uma pasta nova, extrair e executar os
   comandos reais do módulo. O workflow atual publica notas e os arquivos de
   código-fonte oferecidos pelo GitHub; não produz wheel, executável ou pacote
   para instalação do sistema completo.

Exemplo de verificação após publicar `v0.1.0-alpha.1`, em pasta temporária nova,
com GitHub CLI autenticado e Python 3.11 disponível:

```sh
gh release view v0.1.0-alpha.1 --repo BryanPinheiro77/sonar-vision
gh api repos/BryanPinheiro77/sonar-vision/tarball/v0.1.0-alpha.1 > software.tar.gz
tar -tzf software.tar.gz
mkdir software
tar -xzf software.tar.gz -C software --strip-components=1
cd software
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[vision]'
python -m unittest discover -s tests -v
```

Conferir também `README.md`, `LICENSE` e a versão em `pyproject.toml` no
conteúdo extraído. Registrar na #38 a tag, o commit, o link da execução e o
resultado do download/testes. Falhas de publicação ou download deixam esse
critério pendente, mesmo com CI verde nos PRs.

## Releases de modelos

As tags `model-*` não disparam **Release software**. Pesos são publicados
manualmente como assets de uma pré-release própria, após revisão humana.
Para uma próxima publicação:

1. Escolher a pessoa responsável, uma tag nova `model-...` e um commit revisado
   ao qual a documentação do artefato corresponda.
2. Revisar a origem e a permissão de distribuição do peso e do material de
   treino; preservar licenças e atribuições de terceiros. Preparar o arquivo
   final sem caminhos pessoais, credenciais ou metadados privados.
3. Registrar nas notas: issue/PR, origem, licença, peso base, classes, versão da
   ferramenta, procedimento de treino, avaliação conhecida e limitações.
   Calcular SHA-256 **após** a preparação final e registrar nome e tamanho.
4. Criar uma Release em rascunho com a tag `model-...`, marcar como pré-release
   e anexar o peso como asset. Revisar arquivo, notas e hash antes de publicar.
   Não anexar fotos, vídeos ou datasets brutos.
5. Após publicar, baixar o asset numa pasta nova e comparar seu SHA-256 com as
   notas **antes de carregar o checkpoint**. Atualizar links e instruções de
   obtenção; registrar a verificação na issue correspondente.

### Evidência disponível

A [pré-release de escadas v3](https://github.com/BryanPinheiro77/sonar-vision/releases/tag/model-stairs-v3-preview)
contém `stairs-up-down-v3.pt`, com origem, licença AGPL-3.0, SHA-256 e limitações
nas notas. Em 2026-10-02, o download para uma pasta temporária nova foi
conferido, sem carregar o checkpoint; o SHA-256 coincidiu com
`8949d163cab5bfe429a5b4c5d68f683d24a8291a468591f6f719488144d8fec4`.
As instruções de integração do modelo continuam no PR #37 da #16.

Para repetir a verificação do asset, numa pasta nova:

```sh
gh release download model-stairs-v3-preview --repo BryanPinheiro77/sonar-vision \
  --pattern stairs-up-down-v3.pt --dir .
python - <<'PY'
import hashlib
from pathlib import Path

expected = "8949d163cab5bfe429a5b4c5d68f683d24a8291a468591f6f719488144d8fec4"
actual = hashlib.sha256(Path("stairs-up-down-v3.pt").read_bytes()).hexdigest()
if actual != expected:
    raise SystemExit("SHA-256 incorreto; não carregar o checkpoint")
print("Download verificado:", actual)
PY
```

Essa release de modelo é evidência do fluxo de artefatos e não conclui a
avaliação visual da #16/#7.

O CI não demonstra precisão visual, compreensão de áudio, comportamento no
hardware nem independência tátil sob falha da VM. Essas verificações precisam
dos protocolos, testes de bancada e revisões das issues correspondentes.
