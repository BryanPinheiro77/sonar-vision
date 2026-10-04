# Empacotamento e execução reproduzível — #28

Imagem Docker e Compose da [API de inferência](api.md), para rodar a partir de
um clone limpo sem acesso a arquivos privados de ninguém. Responsável: Julio
(empacotamento); operação na AWS é de Bryan e fica para a #23. Decisão:
[ADR 0010](decisions/0010-empacotamento.md).

Fora do escopo: deploy, Kubernetes, banco, broker, dashboard, firmware e
política de anúncios. O alerta tátil local do ESP32 não depende deste serviço;
parar ou reiniciar o contêiner nunca interrompe o feedback local.

## O que existe

| Arquivo | Papel |
|---|---|
| `Dockerfile` | Build em dois estágios, usuário sem privilégios (uid 10001), `HEALTHCHECK` |
| `compose.yaml` | Um serviço (`api`), porta só em `127.0.0.1`, volumes `:ro`, sistema de arquivos somente leitura |
| `compose.catalog.yaml` | Opcional: monta o pacote de vozes (#26) |
| `.dockerignore` | Impede segredos, pesos, mídia e resultados de entrarem no contexto de build |
| `src/sonar_vision_api/healthcheck.py` | Probe HTTPS com validação de certificado |
| `scripts/smoke.py` | Smoke test automatizado da imagem |
| `.env.example` | Variáveis com valores de exemplo, sem segredo |

A imagem **não contém** token, certificado, chave, pesos, vídeo, imagem de
participante nem resultado de experimento. Tudo isso entra por volume.

## Pré-requisitos

- Docker com Compose v2 (testado com Docker 29 e Compose 5 no Windows/WSL2).
- Para gerar certificado e token locais e rodar o smoke test: Python 3.11 ou
  superior e `python -m pip install -e '.[api,api-dev]'`.

## Execução a partir de um clone limpo

Na raiz do repositório (comandos em shell POSIX; no PowerShell troque
`export VAR=valor` por `$env:VAR="valor"` e `source` pelo `Activate.ps1`):

```sh
python -m venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
python -m pip install -e '.[api,api-dev]'

# 1. CA local e certificado para localhost (pasta ignorada pelo Git)
python -m sonar_vision_api.dev_tls .local/tls

# 2. Credencial do dispositivo: o token aparece UMA vez; o arquivo guarda só o hash
python -m sonar_vision_api.tokens glasses-01 .local/tokens > .local/glasses-01.token

# 3. Construir e subir (backend simulado)
docker compose up -d --build --wait

# 4. Conferir (a CA local precisa ser confiada explicitamente; nunca use -k)
python -m sonar_vision_api.healthcheck --cafile .local/tls/ca.pem
docker compose ps
docker compose logs --tail 20 api

# 5. Encerrar
docker compose down
```

`--wait` espera o healthcheck ficar saudável (até o limite do Compose). O
backend `simulated` devolve detecções roteirizadas; não é resultado de modelo
nem de tracking, e o `/healthz` informa isso.

**Linux:** a chave TLS criada pelo `trustme` tem modo 600 e o contêiner roda
como uid 10001. Execute o contêiner com o seu id,
`SONAR_UID=$(id -u) SONAR_GID=$(id -g) docker compose up -d`, em vez de afrouxar
o modo da chave. No Docker Desktop (Windows/macOS) isso não é necessário.

### Smoke test automatizado

```sh
python scripts/smoke.py
```

Gera CA, certificado e token temporários em `.local/smoke`, constrói a imagem,
sobe o serviço numa porta livre e verifica: healthcheck com a CA local, 401 sem
token, inferência sintética autenticada (200), processo sem root e parada
graciosa por SIGTERM. Sempre derruba o serviço e apaga os temporários. Não usa
imagens reais, pesos nem rede externa. É o ponto de partida para o deploy da
#23.

## Configuração

Valores específicos de cada ambiente ficam em `.env` (nunca versionado; copie
de `.env.example`). Segredos, certificados e pesos ficam **fora** da imagem e
do Git, em volumes somente leitura:

| Variável do Compose | Padrão | Uso |
|---|---|---|
| `SONAR_HOST_TLS_DIR` | `./.local/tls` | Pasta com `server.pem`, `server-key.pem` e `ca.pem` |
| `SONAR_HOST_TOKENS_FILE` | `./.local/tokens` | Arquivo `device_id sha256` |
| `SONAR_HOST_MODELS_DIR` | `./models` | Pesos locais (variante com detector real) |
| `SONAR_API_PORT` | `8443` | Porta publicada em `127.0.0.1` |
| `SONAR_BUILD_EXTRAS` | `api` | `api` ou `api,vision` |
| `SONAR_API_WEIGHTS_IN_CONTAINER` | vazio | Ex.: `/models/yolov8n.pt` |
| `SONAR_UID` / `SONAR_GID` | `10001` | Usuário do contêiner (Linux) |
| `SONAR_API_*` | como em [api.md](api.md) | Limites e backend; valor inválido impede o start |

Em produção, certificado, chave e tokens devem ser provisionados fora do
repositório pelo operador (#23); os exemplos deste documento servem apenas para
desenvolvimento. O Compose publica só em loopback; abrir a porta para a rede é
decisão do deploy, com TLS de verdade e sem desligar verificação.

### Catálogo de vozes (#26)

```sh
export SONAR_HOST_CATALOG_DIR=/caminho/do/pacote/1.0.0   # fora do Git
docker compose -f compose.yaml -f compose.catalog.yaml up -d --build --wait
```

O pacote é validado na inicialização; um pacote rejeitado impede o serviço de
subir. A montagem e a publicação seguem o
[guia de distribuição](catalog-distribution.md).

## Detector real, pesos e CPU/GPU

A imagem padrão usa o backend simulado e não instala PyTorch. Para o detector
real:

1. Obtenha os pesos pelas páginas oficiais, conferindo origem e licença, como
   descrito no [guia de visão](vision.md#modelos-artefatos-e-licenças). Eles
   **não** são versionados e **não** entram na imagem. Nada depende do
   computador de outra pessoa: cada integrante baixa pela fonte oficial e
   registra origem, versão e hash localmente.
2. Coloque o `.pt` em `models/` (ignorado pelo Git).
3. Construa e suba:

```sh
export SONAR_BUILD_EXTRAS=api,vision
export SONAR_API_BACKEND=ultralytics
export SONAR_API_WEIGHTS_IN_CONTAINER=/models/yolov8n.pt
docker compose up -d --build --wait
```

**CPU/GPU:** a variante `vision` instala o PyTorch **somente CPU** (índice
oficial `download.pytorch.org/whl/cpu`) e é a única configuração empacotada e
exercitada. Não há imagem CUDA nem configuração de GPU no Compose: isso
dependeria de benchmark que mostre necessidade (ver #22/#23). A imagem com
visão tem cerca de 2,5 GB (PyTorch + OpenCV); a padrão, cerca de 230 MB
(medidas no build de 2026-10-03).

## Ciclo de vida e falhas

| Situação | Comportamento |
|---|---|
| Inicialização | Valida variáveis, tokens, pesos e catálogo antes de abrir a porta; configuração inválida encerra o processo com mensagem `SONAR_API_…` e o Compose reinicia (`unless-stopped`) |
| Saúde | `HEALTHCHECK` chama `/healthz` por HTTPS com a CA montada; falha de certificado, resposta não `ok` ou corpo grande = não saudável |
| Parada | SIGTERM encaminhado por `init`; o uvicorn encerra graciosamente e o `docker compose stop` espera até 15 s. O código de saída 143 (SIGTERM relançado) é esperado; 137 indicaria SIGKILL |
| Arquivos ausentes | Montar caminho inexistente cria diretório vazio no host (comportamento do Docker); o serviço então falha na validação, com mensagem clara |
| Logs | JSON por requisição, sem token nem imagem; rotação de 3 × 10 MB |

## Testes

```sh
python -m pip install -e '.[api,api-dev]'
PYTHONPATH=src python -m unittest tests.test_packaging -v   # sem Docker
python scripts/smoke.py                                     # com Docker
```

`tests/test_packaging.py` cobre, sem Docker: arquivos de contêiner sem segredos,
porta em loopback, volumes somente leitura, `.env.example` sem valores reais,
probe de saúde (sucesso, CA desconhecida, hostname errado, status/JSON/corpo
inválidos, conexão recusada, CA ausente, recusa de `http://`) e falhas de
configuração na inicialização. Sem os extras, os testes de probe e de
inicialização aparecem como *skipped*, não como validação.

## Dependências e licenças

Versões fixadas em `pyproject.toml`; imagem base `python:3.12-slim`. Não há
lockfile: dependências transitivas podem variar entre builds (limite já
descrito em [ci.md](ci.md)). Licenças conferidas nos metadados dos pacotes
instalados e em [vision.md](vision.md):

| Pacote | Licença |
|---|---|
| fastapi 0.142.2 | MIT |
| uvicorn 0.54.0 | BSD-3-Clause |
| python-multipart 0.0.32 | Apache-2.0 |
| httpx2 2.13.1 e trustme 1.2.1 (apenas `api-dev`; fora da imagem) | BSD-3-Clause; MIT OR Apache-2.0 |
| ultralytics 8.4.137 | AGPL-3.0, compatível com o projeto (AGPL-3.0-only) |
| opencv-python 4.14.0.94 | MIT no wrapper ([vision.md](vision.md)); o metadado do pacote declara Apache 2.0 (OpenCV) |
| lap 0.5.13 | BSD-2-Clause |
| torch 2.14.1+cpu (índice CPU) | Expressão composta no metadado: Apache-2.0, BSD-2/3-Clause, BSL-1.0, MIT e Apache-2.0 com exceção LLVM |

Distribuir a imagem com ultralytics implica as obrigações da AGPL-3.0 (código
correspondente disponível); a imagem padrão não o inclui. Pesos, vídeos e
artefatos de hardware **não** estão cobertos pela licença do repositório: cada
origem deve ser verificada e registrada (veja o guia de visão). Revise as
licenças ao alterar versões.

## Limites

- Backend simulado não prova acurácia nem latência; medir é da #22.
- A CA e o certificado gerados aqui são só para desenvolvimento.
- O build da variante `vision` não é executado no CI; foi construído
  manualmente e confirmou imports (cv2, lap, ultralytics, torch CPU) como uid
  10001, mas **não** foi testado com pesos reais.
- Nada aqui foi validado com o firmware ou com hardware.
- Sem escaneamento de vulnerabilidades da imagem e sem lockfile.
