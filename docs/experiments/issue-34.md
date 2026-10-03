# Evidência de execução do guia — #34

- Data: 2026-10-02.
- Responsável pela organização: Matheus (@Matheus-xz), com apoio de IA.
- Execução automatizada local; **não houve revisão independente por colega**.
- Branch: anuncios-por-audio.
- Base: d3059ead63ab3eb48aebdb18ea90a6f0bb335743 mais alterações locais da #34.
- Ambiente: Windows/PowerShell, Python 3.12.7, pip 24.2.
- Código/documentação/fixtures próprios: AGPL-3.0-only.
- Guias: [execução](../execution.md), [demonstração](../demo.md).

## Resultados observados

| Verificação | Resultado |
|---|---|
| Testes próprios test_smoke.py | 10 aprovados, 8,911 s |
| Suíte completa no branch | 134 encontrados, 130 aprovados, quatro skipped; 24,978 s |
| Smoke por código-fonte | 16 expectativas satisfeitas; retorno 0; passed=true |
| Criação de venv e instalação -e . em cópia isolada | sonar-vision 0.1.0a1 instalado; build isolado concluído |
| pip check no venv isolado | No broken requirements found |
| Suíte completa no venv isolado, sem PYTHONPATH | 134 encontrados, 130 aprovados, quatro skipped; 24,414 s |
| Smoke no venv isolado, sem PYTHONPATH | 16 expectativas satisfeitas; retorno 0; passed=true |
| Controle de saídas | results/ ignorado; não sobrescrever verificado pelos testes |

Os quatro skips são os testes que exigem o ByteTrack real; o extra vision não
foi instalado. Skips não equivalem a validação de tracking/inferência reais.
O teste end-to-end próprio executa os CLIs reais, porém somente com dados
sintéticos; testes adicionais injetam JSON incorreto, erro/timeout de subprocesso
e saída ausente/divergente para verificar diagnóstico e retorno de falha.

Smoke confirmou sucesso, expiração, timeout, desconexão, sessão antiga,
orientação/urgência sintéticas, frames inválidos, manifesto #7, catálogo draft,
release bloqueado, fixture silenciosa/pacote #32, benchmark scripted,
avaliação anotada sintética e bloqueio de sobrescrita. Resultados esperados:
success=100 ms virtuais; expired=1000; timeout=2000; TP=5, FP=2, FN=2;
catálogo=179 frases, três essenciais, sem release operacional.
Não são números de desempenho real ou evidência física de segurança.

## Como foi preparada a execução isolada

Uma exportação de `git archive --format=zip HEAD` foi extraída numa pasta nova
sob results/issue-34/review-snapshot-01. Sobre ela foram copiados **apenas** os
dez arquivos de implementação/documentação da #34 presentes no workspace:

- README.md, CHANGELOG.md;
- docs/README.md, docs/PRIMEIROS_PASSOS.md, docs/experiments/README.md;
- docs/execution.md, docs/demo.md;
- src/sonar_vision/README.md, src/sonar_vision/smoke.py;
- tests/test_smoke.py.

Este registro de evidência foi acrescentado depois da execução. Não foram
copiados .venv, results, dados ignorados, vídeos, pesos ou configurações pessoais
do workspace. A cópia não contém .git e não é um git clone de uma revisão já
publicada: trata-se de ensaio local de fontes isoladas. O critério de checkout
limpo **com outra pessoa** permanece pendente, sem substituir essa evidência.

Na raiz dessa cópia, os comandos executados foram:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip check
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -B -c "import sonar_vision; print(sonar_vision.__file__)"
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m sonar_vision.smoke --output results/issue-34/installed-smoke-01.json
```

O caminho importado foi conferido: src/sonar_vision da cópia isolada, não o
workspace original. O mesmo Python de .venv executou instalação, testes e smoke.
Ferramentas de build foram obtidas pelo pip conforme pyproject.toml; nenhum
modelo, vídeo, dependência vision ou áudio externo foi obtido.
O sandbox do Windows impediu inicialmente acesso aos diretórios temporários e
ensurepip. As verificações foram repetidas com execução autorizada fora desse
sandbox; isso é uma limitação do ambiente do agente, não uma alteração do projeto.

Relatórios privados, ignorados:
results/issue-34/smoke-01.json e
results/issue-34/review-snapshot-01/results/issue-34/installed-smoke-01.json.
O smoke remove seus artefatos temporários de teste; mantém somente o relatório
opcional solicitado. O venv/cópia de revisão são artefatos locais em results/.

## Verificação documental e manutenção

Links locais das páginas novas e índices alterados foram conferidos; arquivos
novos foram verificados quanto a whitespace e caracteres inválidos. git diff
--check não apresentou erros; avisos de conversão LF/CRLF do Git são apenas
configuração do checkout, sem divergência de conteúdo do catálogo canônico.
As páginas oficiais de Python venv, YOLOv8 e releases Ultralytics foram abertas
para conferir as referências de instalação/origem; não houve download de pesos.

Escolha: biblioteca padrão, comandos dos próprios módulos e dados originais
versionados. Alternativas consideradas: somente checklist manual (não verifica
automaticamente respostas), framework de automação adicional (desnecessário
para 16 comandos) ou servidor demonstrativo novo (fora do escopo da #34).
Sem novo serviço, contrato, dependência, threshold de risco ou tecnologia; ADRs
atuais preservados. A demonstração tátil local continua independente por desenho;
não existe motor/sensor acessado por esse roteiro.

## Pendências para aceite final

- Outro integrante precisa seguir o guia em git clone novo da revisão publicada
  e preencher o formulário de [revisão](../demo.md).
- PR revisável, revisão humana e explicação da pessoa responsável ainda pendentes;
  não houve commit, push, PR ou merge nesta execução.
- Etapa real: pesos/licenças, vídeos/anotações autorizados, instalação vision,
  análise/benchmark e conferência independente de tracking não validados.
- API, TLS/rede reais, serviços, firmware, reprodução sonora, hardware e teste
  físico sem Wi-Fi/VM não executados; dependem das issues dos respectivos autores.
- POSIX/Linux/macOS não executados. Não houve teste com participantes ou aprovação
  ética nova. O guia não conclui validação da #19 ou aceita o protótipo como seguro.

A #34 tem implementação/documentação/testes locais preparados, mas não deve
ser encerrada antes do aceite de reprodução por colega e entrega por PR.
