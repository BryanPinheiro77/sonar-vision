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
exclusão da branch estão bloqueados. Os checks do CI só devem virar obrigatórios
na proteção depois que o workflow entrar na `main` e os nomes dos jobs forem
confirmados em uma execução real. Até lá, revisão humana continua obrigatória.

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

O CI não demonstra precisão visual, compreensão de áudio, comportamento no
hardware nem independência tátil sob falha da VM. Essas verificações precisam
dos protocolos, testes de bancada e revisões das issues correspondentes.
