# API de inferência — #24

Implementação experimental de `POST /v1/inference` do
[contrato 0.1](protocol/eventos-semanticos.md), em `src/sonar_vision_api/`.
Responsável: Julio. Decisão: [ADR 0007](decisions/0007-api-de-inferencia.md).
Não implementa política de anúncios (#5/#31), firmware, banco, broker,
dashboard ou deploy. Mensagens da API não comandam vibração nem confirmam risco
local; o caminho tátil do ESP32 continua independente da rede.

## Instalação

Na raiz do repositório, Python 3.11 ou superior:

```sh
python -m venv .venv
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
python -m pip install -e '.[api,api-dev]'
```

Para o backend real, instale também `.[vision]` e obtenha os pesos conforme o
[guia de visão](vision.md). Nenhum peso, certificado ou token é versionado.

## Execução local reproduzível

```sh
# 1. CA local e certificado para localhost (pasta ignorada pelo Git)
python -m sonar_vision_api.dev_tls .local/tls

# 2. Credencial do dispositivo: o token aparece UMA vez; o arquivo guarda só o hash
python -m sonar_vision_api.tokens glasses-01 .local/tokens > .local/glasses-01.token

# 3. Servidor (somente HTTPS)
export SONAR_API_BACKEND=simulated
export SONAR_API_TOKENS_FILE=.local/tokens
python -m sonar_vision_api --certfile .local/tls/server.pem --keyfile .local/tls/server-key.pem
```

Teste com um cliente que **confia na CA local**:

```sh
curl --cacert .local/tls/ca.pem https://localhost:8443/healthz
curl --cacert .local/tls/ca.pem \
  -H "Authorization: Bearer $(cat .local/glasses-01.token)" \
  -F 'metadata={"version":"0.1","session_id":"boot-1","frame_id":"1","captured_at_ms":1000};type=application/json' \
  -F 'image=@frame.jpg;type=image/jpeg' \
  https://localhost:8443/v1/inference
```

`frame.jpg` deve ser uma imagem sintética ou autorizada, nunca de participante.
No Windows, o curl com Schannel pode exigir `--ssl-no-revoke`, porque a CA
local não publica lista de revogação; isso **não** desliga a validação do
certificado. Nunca use `-k`/`--insecure` nem `verify=False`.

Para o backend real: `SONAR_API_BACKEND=ultralytics` e
`SONAR_API_WEIGHTS=models/yolov8n.pt`.

## Configuração

Variáveis lidas na inicialização; valor inválido impede o processo de subir.
Veja `.env.example`.

| Variável | Padrão | Observação |
|---|---|---|
| `SONAR_API_BACKEND` | obrigatória | `simulated` (detecções roteirizadas) ou `ultralytics` |
| `SONAR_API_TOKENS_FILE` | obrigatória | `device_id sha256` por linha; fora do Git |
| `SONAR_API_WEIGHTS` | — | obrigatória com `ultralytics` |
| `SONAR_API_MAX_BODY_BYTES` | 524288 | corpo inteiro do multipart; proposta |
| `SONAR_API_MAX_PIXELS` | 1920000 | 1600×1200 (UXGA da OV2640); proposta |
| `SONAR_API_TIMEOUT_MS` | 1500 | deve ser < 2000 ms (timeout do cliente) |
| `SONAR_API_MAX_SESSIONS` | 8 | sessões simultâneas no `VisionService` |
| `SONAR_API_IDLE_SECONDS` | 60 | expiração de sessão ociosa |
| `SONAR_API_CATALOG_DIR` | — | pacote de vozes publicado (#26); opcional |

Os limites de upload e pixels são **propostas iniciais** para revisão do grupo,
não valores validados.

## Comportamento

Ordem de validação, antes de qualquer efeito:

1. `Authorization: Bearer` → 401 `unauthorized` (antes de ler o upload).
2. `Content-Type` multipart com boundary → 415.
3. Corpo lido com limite (também ignorando `Content-Length` mentiroso) → 413.
4. Exatamente duas partes: `metadata` (`application/json`) e `image`
   (`image/jpeg`); partes extras ou repetidas → 400; tipo errado → 415.
5. Metadata estrita: campos exatos, `version` `"0.1"`, chaves duplicadas,
   NaN, `frame_id` decimal canônico, `captured_at_ms` inteiro seguro → 400.
6. Cabeçalho JPEG lido sem decodificar; pixels acima do limite → 413.
7. Admissão: se houver inferência em andamento → 429 `busy`, sem fila.
8. Frame repetido/fora de ordem ou regressão de captura → 400.
9. Resposta validada (campos, vocabulário, 20 objetos, 120 caracteres,
   referências do áudio, 16 KiB) antes do envio; violação → 500.

Sessões: chave interna `(device_id da credencial, session_id)`. Um
`session_id` novo do mesmo dispositivo (reboot) fecha a sessão anterior. Mudança
de resolução faz `reset` explícito (novo `tracker_epoch`). Falha do backend →
500 e a próxima captura reabre a sessão com epoch novo, mantendo a proteção
contra replay. Sessão expirada por inatividade é reaberta com epoch novo.

Timeout: ao exceder `SONAR_API_TIMEOUT_MS` a requisição recebe 503
`unavailable`. A inferência **não é interrompida**; o slot fica ocupado até ela
terminar (novas requisições recebem `busy`), o resultado tardio é descartado e
o log registra `abandoned_work_finished` com a duração real.

Política de anúncios: `InferenceService(..., policy_factory=...)` cria uma
política por sessão com `select(observation, capture_age_lower_bound_ms=...)`.
Padrão `NullPolicy` → `audio: null`. Sugestão inválida é descartada (log
`audio_rejected`) sem perder a observação. Integração prevista com o
`AudioPolicy` proposto na branch `anuncios-por-audio`.

Catálogo de áudio: `GET /v1/catalog/manifest` e `GET /v1/catalog/files/<path>`
usam a mesma credencial; veja [distribuição do catálogo](catalog-distribution.md).

`GET /healthz` informa `backend` e versão do contrato, sem autenticação nem
dados de sessão.

## Instrumentação (#22/#6)

Uma linha JSON por requisição (`event: inference_request`) com `request_id`,
`device_id`, `session_id`, `frame_id`, status, motivo interno e tempos:
`read_ms`, `decode_ms`, `inference_ms` (`processing_ms` do núcleo),
`policy_ms`, `encode_ms`, `work_ms`, `total_ms`, além de `body_bytes`,
dimensões e `objects`. `abandoned: true` marca timeout. Sem espera em fila,
porque não há fila. Nunca são registrados token, imagem ou texto pessoal.

## Testes

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

Sem os extras, os testes HTTP/HTTPS aparecem como **skipped**; validação,
contrato, autenticação e serviço rodam com a biblioteca padrão. Com
`.[api,api-dev]`, sobe um servidor HTTPS real em porta local e verifica:
sucesso com a CA confiada, recusa com CA desconhecida e ausência de HTTP puro.

## Limitações conhecidas

- Mocks não comprovam a integração final: ainda falta medir com o backend
  `ultralytics` e um cliente real (#6/#22).
- Uma inferência por vez no processo; vários óculos simultâneos recebem `busy`.
- Token novo ou revogado só vale após reiniciar o processo.
- `valid_for_ms` vem fixo (1000) do módulo visual; torná-lo configurável é
  mudança no `core.py` (Bryan).
- Contrato 0.1 não tem código para "sessão substituída"; resposta de sessão
  antiga é tratada pelo ESP32 (FR-6).
- O backend `ultralytics` pode tentar acesso de rede próprio da biblioteca
  (configurações/telemetria); não verificado nesta etapa.
- Ao servir em rede, a AGPL §13 exige oferecer o código-fonte correspondente
  aos usuários do serviço.
- Nada foi validado com hardware.
