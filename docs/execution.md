# Guia consolidado de execução — #34

Responsável pela organização: Matheus (@Matheus-xz), com apoio de IA.
Status: guia e verificação offline implementados; revisão por outro integrante,
análise com artefatos reais e demonstração física ainda pendentes.
Referência: [issue #34](https://github.com/BryanPinheiro77/sonar-vision/issues/34).

## Fontes, módulos e responsabilidade

Este guia reúne os comandos dos módulos existentes. Os guias de cada autor
continuam sendo a referência para configuração, interfaces e testes.
Consultar [README](../README.md), [regras dos agentes](../AGENTS.md),
[contribuição](../CONTRIBUTING.md), [escopo](ESCOPO.md) e
[decisões](decisions/README.md) antes de modificar o projeto.

| Componente | Estado executável neste branch | Documento/autor de referência |
|---|---|---|
| Visão #21 | Núcleo, backend opcional e benchmark local | [Visão](vision.md), Bryan |
| Política de áudio #5/#31 | Seletor determinístico puro; sem TTS/reprodução | [Áudio](audio.md), responsável registrado nesse guia |
| Coleta #7 | Validador de manifesto; coleta/aprovação pendentes | [Protocolo](experiments/protocolo-visual.md), responsáveis desse protocolo |
| Cliente #30 | Fixtures offline e integração HTTPS com backend simulado | [Simulador](simulator.md), Matheus |
| Catálogo #32 | Proposta textual, validação e pacote silencioso de teste | [Catálogo](audio-catalog.md), Matheus |
| Avaliação #33 | Cálculo offline contra anotações, fixture própria | [Avaliação](evaluation.md), Matheus; apoio de Bryan na revisão |
| API #24 | HTTPS incorporado da #43, backend simulado/real optativo | [API](api.md), Julio |
| Serviços #28 | Empacotamento ainda fora deste checkout | PR #47, não incorporado |
| Interface #25 e distribuição #26 | Modelos de referência e rotas disponíveis; sem firmware | [Interface](protocol/audio-local.md), [distribuição](catalog-distribution.md) |
| Firmware/hardware | Sem execução física integrada | Roteiro físico depende da #19 |

Matheus mantém a organização e os links; cada autor mantém as instruções/testes
do próprio módulo. Ao integrar #24/#28/#25/#26, revisar esta tabela e o
[roteiro](demo.md), acrescentar apenas comandos executados, evidência e limites.
Há servidor FastAPI HTTPS conforme [API](api.md). Não há Docker Compose, broker provisionado ou build
de firmware incluído aqui. A baseline planejada não significa serviço entregue.

## Checkout e pré-requisitos

Git e Python >=3.11 com pip/venv. A demonstração offline não exige câmera,
ESP32, GPU, credencial, pesos, vídeo, provedor de voz ou dependências de visão.
Internet é necessária para obter o código e, se ausentes, ferramentas de build;
após preparar o ambiente, os comandos sintéticos funcionam offline.

Para um colega, em uma pasta nova, após publicar a revisão por PR:

```powershell
git clone https://github.com/BryanPinheiro77/sonar-vision.git sonar-vision-review
Set-Location sonar-vision-review
git checkout REVISAO_PUBLICADA
git status --short
git rev-parse HEAD
```

REVISAO_PUBLICADA é o SHA/branch indicado no PR, a ser substituído. A #34 ainda
não estará em main antes da publicação. Não usar arquivos copiados do computador
de outro integrante. O status inicial deve estar vazio; registrar a revisão
antes de executar. Este guia não autoriza commit, push, merge ou publicação.

## Instalação: PowerShell

Executar da raiz. O caminho explícito evita necessidade de ativação de scripts
ou alteração da política do PowerShell:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m sonar_vision.smoke --output results/issue-34/smoke-01.json
```

O build requer setuptools>=77, conforme pyproject.toml; pip resolve isso no
ambiente isolado. Não há dependência de runtime no núcleo. Repetições usam
output novo (smoke-02.json etc.). Resultados anteriores não são sobrescritos.

Alternativa sem instalação, para desenvolver/testar o código-fonte:

```powershell
$env:PYTHONPATH = 'src'
python -B -m unittest discover -s tests -v
python -B -m sonar_vision.smoke --output results/issue-34/source-01.json
```

Essa alternativa valida execução por fonte; não comprova instalação do pacote.
Não misturar Python global e Python de .venv ao interpretar os resultados.

## Instalação: shell POSIX

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip check
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B -m sonar_vision.smoke --output results/issue-34/smoke-01.json
```

Alternativa por fonte: `PYTHONPATH=src python3 -B -m unittest discover -s tests -v`.
Os comandos POSIX são equivalentes aos interfaces existentes; execução local
desta entrega foi em Windows, sem validação em Linux/macOS.
Para detalhes de venv, consultar a [documentação Python](https://docs.python.org/3/library/venv.html).

## Verificação offline da implementação

`src/sonar_vision/smoke.py` executa 16 comandos/cenários reais dos CLIs já
existentes em subprocessos do mesmo Python, sem shell. Usa os dados sintéticos
versionados, diretório temporário sob results/, PYTHONPATH absoluto para src/
e remove SONAR_VISION_TOKEN do ambiente dos filhos. Não abre câmera, acessa API,
baixa modelo ou gera voz. Arquivos temporários são removidos ao terminar.

Valida códigos de retorno **e** campos de JSON; em benchmark/avaliação lê o
artefato produzido. Falhas esperadas, como release não aprovado, precisam
retornar 2. Um CLI do simulador retornar 0 sozinho não prova aceitação da resposta:
a verificação também exige outcome/reason/audio e tempos virtuais conhecidos.

| Verificação | Resultado esperado |
|---|---|
| Sucesso simulado | Observação/áudio aceitos; 100 ms virtuais |
| Expiração/timeout | Descarte em 1000/2000 ms virtuais |
| Desconexão/sessão anterior | network_error/session_mismatch |
| Orientação 16 graus/urgência sintética | Áudio orientation_changed/local_urgent |
| Frames zero | Retorno 2 |
| Manifesto da #7 | recorded=0, synthetic=1, approval_status=pending |
| Catálogo textual | 179 frases, 179 áudios ausentes; não distribuível |
| Tentativa de release | Retorno 2 |
| Fixture/pacote #32 | 179 WAVs silenciosos; ZIP fixture com 183 arquivos |
| Benchmark scripted | Três amostras; sem modelo ou evidência de acurácia |
| Avaliação anotada sintética | TP=5, FP=2, FN=2; acceptance_evaluated=false |
| Output já existente | Retorno 2; não sobrescrever |

Saída: `passed=true` somente se todos os cenários atenderem à expectativa.
Retorno do smoke: 0 = expectativas satisfeitas, 1 = cenário divergiu ou subprocesso
falhou, 2 = checkout/configuração/output inválido. O JSON registra apenas nomes
fixos, resultado e motivos; não publica stdout/stderr de filhos, paths, token
ou ambiente. `--timeout` aceita 1..60 segundos por subprocesso (padrão 30),
limite de supervisão do roteiro, sem mudar o timeout de 2000 ms do protocolo.
`--root` aponta para checkout completo (padrão diretório atual); docs/fixtures
são necessários, portanto esta ferramenta não se propõe a operar com wheel
isolado. Outputs opcionais ficam sob results/ do diretório atual, sem sobrescrita.
Máximo de 16 subprocessos sequenciais; no pior caso, cada um pode atingir o limite.

Testes próprios:

```powershell
$env:PYTHONPATH = 'src'
python -B -m unittest discover -s tests -p test_smoke.py -v
git diff --check
git check-ignore results/issue-34/smoke-01.json
```

Cobrem o roteiro completo, respostas divergentes/JSON inválido, artefato ausente,
código inesperado, erro de processo, timeout/limites, modo sintético, remoção
de token, limpeza temporária, output privado e proteção contra sobrescrita.
Nenhuma dependência, serviço ou decisão arquitetural nova: reutilização dos
CLIs existentes, conforme ADRs atuais. Não requer ADR adicional de arquitetura.

## Visão real e configuração de rede

Somente quando os artefatos autorizados estiverem disponíveis, instalar o extra
no mesmo ambiente:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[vision]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m sonar_vision.benchmark --weights models/yolov8n.pt --video videos/cenario-autorizado.mp4 --frames 100 --output results/real-video-01.json
```

Os caminhos acima são convenções relativas, não arquivos incluídos. O extra
vision fixa Ultralytics/OpenCV/lap no pyproject.toml; transitivas/plataforma
devem ser registradas com `python -m pip freeze` em arquivo privado de results/.
Sem extra, quatro testes ByteTrack aparecem skipped: isso não valida tracker real.
Não escolher GPU nem ajustar limiares automaticamente. Configuração inicial CPU,
imagem 640 e confiança 0.35 segue [visão](vision.md); não é validação de risco.
Benchmark real mede processamento/FPS, sem referência anotada ou acurácia.
Para TP/FP/FN, preparar snapshot/anotações privados no formato da [#33](evaluation.md).

HTTPS requer a API #24 disponível, endpoint real/certificado válido e credencial
individual provisionada fora do Git. Usar os exemplos de prompt oculto,
SONAR_VISION_TOKEN, remoção da variável e CA externa do [simulador](simulator.md).
HOST-DA-API é placeholder, não endereço operacional. Não existe opção insecure.
Yaw/urgência do CLI continuam sintéticos mesmo ao capturar vídeo/webcam.
Não registrar token, URL autenticada ou dados pessoais nas evidências.

## Obtenção autorizada e registro de artefatos

| Artefato | Obtenção | Registro/local privado |
|---|---|---|
| Pesos | Página oficial [YOLOv8](https://docs.ultralytics.com/models/yolov8/) e [releases oficiais](https://github.com/ultralytics/assets/releases); selecionar pesos de detecção yolov8n.pt e conferir os termos do artefato | models/; URL exata de origem, release/versão, licença, data e SHA-256 |
| Vídeo/anotação | Coleta própria autorizada ou fonte com licença e permissão verificadas; seguir protocolo #7 | videos/ e datasets/; origem, responsável, licença, permissão/consentimento/ética, SHA-256 e referência de anotação |
| Voz final | Geração/gravação autorizada após aprovar provedor/plano/voz/formato/frases e direitos de distribuição | results/catalog-release-VERSION/; manifesto com origem, direitos, configuração, hash e revisão auditiva |
| Fixtures | Já versionadas; originais do projeto AGPL-3.0-only | Manifesto e entrada #33; silêncio #32 gerado localmente; JPEG/respostas #30 incorporados |

Não há vídeo real ou voz final públicos aprovados nesta entrega. Não criar URL
de download fictícia nem reaproveitar arquivo pessoal do Bryan. Nenhum provedor
de TTS foi escolhido pela #34; seguir [preparação do catálogo](audio-catalog.md).
Não presumir que a licença principal cobre pesos, imagens ou áudios externos.
A documentação oficial [YOLOv8](https://docs.ultralytics.com/models/yolov8/)
descreve modelos sob AGPL-3.0 e licença Enterprise; conferir os termos concretos
do arquivo escolhido e preservar avisos antes de distribuir. Não carregar .pt
de origem desconhecida. Hash identifica bytes, não comprova autenticidade/direitos.

Exemplos de inspeção local, depois de obter os arquivos autorizados:

```powershell
Get-FileHash models/yolov8n.pt -Algorithm SHA256
Get-FileHash videos/cenario-autorizado.mp4 -Algorithm SHA256
git check-ignore models/yolov8n.pt videos/cenario-autorizado.mp4 results/catalog-release-VERSION/manifest.json
git status --short
```

Registrar as evidências de origem num diário privado; compartilhar somente por
canal aprovado pelo grupo. .gitignore não controla acesso nem aprova retenção.
Revisar sínteses agregadas antes de publicar, principalmente grupos pequenos.

## Falhas e limites

| Sintoma | Ação |
|---|---|
| No module named sonar_vision | Executar da raiz, instalar no Python usado ou configurar PYTHONPATH=src |
| Build exige setuptools ou não acessa índice | Conferir rede/índice de pacotes; usar alternativa por fonte para núcleo e registrar que instalação não foi validada |
| Quatro skips ByteTrack | Instalar extra somente na etapa real; registrar skips como pendência |
| Output indisponível | Usar nome novo sob results/, conferir permissões; não remover resultados anteriores automaticamente |
| Smoke retorna 1 | Identificar case/reason fixos no JSON e repetir comando correspondente do guia do autor em ambiente privado |
| Timeout/decode/TLS/autenticação na captura real | Seguir diagnóstico do simulador; não expor exceções/credenciais ou flexibilizar TLS |
| Catálogo não distribuível | Completar aprovações/direitos/revisões reais; silêncio nunca é release |

O alerta tátil imediato deve continuar local no ESP32-S3, independente de VM,
rede, câmera e ML. Este software não aciona motores, testa sensores ou prova
essa propriedade fisicamente. A demonstração de rede desligada **com hardware**
fica com #19. Ausência de detecção não significa caminho livre. Protótipo
acadêmico, sem validação médica ou substituição de bengala/orientação profissional.

## Revisão por colega e entrega

Usar o [roteiro e formulário de revisão](demo.md) em checkout novo, após
disponibilizar a revisão por PR. Registrar SHA, sistema, Python, comandos,
contagens passed/skipped, smoke, dificuldades e conclusão do revisor.
Evidência local: [registro #34](experiments/issue-34.md).
Até outra pessoa executar e confirmar, este critério permanece **pendente**.
Não usar Closes #34 antes de cumprir o aceite humano e entregar o PR revisável.

## Integração acrescentada na revisão do PR #42

A branch já incorpora origin/main após fetch em 2026-10-05 (zero commits
pendentes; HEAD 2d88e26, main 4f0017b). Para repetir a execução sem câmera, use
os comandos e cenários de [integração HTTPS do simulador](simulator.md#integração-reproduzível-com-a-api-da-43--revisão-do-pr-42).
O teste conecta o cliente deste PR à API real de loopback com TLS/CA validado e
credencial por dispositivo, porém **o detector é explicitamente simulado**.

O smoke offline continua sem acessar a API. Testes #27 permanecem responsáveis
pelos cenários completos; detector real é optativo e não foi substituído por
fixtures. Não há validação física, fonte vídeo/webcam identificada, voz final,
aceite experimental ou reprodução por colega nesta integração.

### Evidência executada — 2026-10-05

Windows/PowerShell, Python 3.13.15, ambiente .venv criado nesta revisão;
instalação editable `.[api,api-dev]` concluída, Ruff 0.16.10. Dependências diretas:
FastAPI 0.142.2, uvicorn 0.54.0, python-multipart 0.0.32, httpx2 2.13.1,
trustme 1.2.1. Sem extra vision, pesos, câmera ou vídeo.

- `python -B -m unittest discover -s tests -p test_simulator_https.py -v`:
  8 testes aprovados, zero skips, 5.623 s; cliente deste PR → API HTTPS validada.
- `python -B -m unittest discover -s tests -v`: 244 testes, 239 aprovados,
  5 skipped, 67.888 s; inclui os cenários existentes da #27. Quatro skips são
  ByteTrack sem extra vision; um é detector real sem SONAR_E2E_WEIGHTS.
  Nenhum teste de API/HTTPS foi ignorado.
- `python -B -m sonar_vision.smoke`: passed=true, 16 cenários sintéticos
  aprovados; human_checkout_review=pending, real_vision_validated=false,
  network_validated=false e hardware_validated=false **nesse roteiro offline**.
  A evidência HTTPS está nos testes acima, não no smoke.
- `python -m ruff check --no-cache --select E4,E7,E9,F src tests`,
  `python -m compileall -q src tests`, `python -m pip check` e
  `git diff --check`: aprovados (Git apenas avisou normalização LF/CRLF).

Use o executável `.venv/Scripts/python.exe` conforme comandos acima. Tempos são
duração dos testes nesta máquina, não benchmark de inferência ou segurança.
A configuração optativa e testes novos são alterações locais sobre 2d88e26;
sem commit/push nesta execução. Publicar a revisão exige solicitação explícita.

A descrição completa foi preparada em `.local/pr-42-body.md` (ignorado pelo
Git). A atualização remota do PR #42 não foi concluída: GitHub respondeu
HTTP 500 no endpoint de pull request e HTTP 422 no endpoint de issue.
Autenticação existente identificou Matheus-xz; nenhum token foi registrado.
O template remoto ainda precisa ser substituído pela descrição preparada.
