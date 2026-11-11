# Telemetria ToF da demonstração — proposta #73

Interface separada do [contrato de inferência 0.1](eventos-semanticos.md).
Responsável cloud: Bryan. Revisão com Mathias, Tarcísio e Weslley/#17 e ensaio
físico pendentes. Esta proposta não afirma que o firmware já envia ToF.
Decisão: [ADR 0024](../decisions/0024-painel-demonstracao.md).

## Publicação autenticada

`POST /v1/demo/tof`, HTTPS com certificado/host validados, `Authorization:
Bearer <credencial individual>`, `Content-Type: application/json`.
Origem é o `device_id` da credencial, não um campo declarado pelo cliente.
Exatamente estes campos, sem extras, duplicatas, NaN ou Infinity:

```json
{
  "version": "demo-tof-1",
  "session_id": "boot-1",
  "sequence": "12",
  "captured_at_ms": 3100,
  "distance_mm": 1250,
  "valid": true,
  "quality": "good",
  "sector": "all",
  "zone": null,
  "aggregation": "min_valid_8x8"
}
```

| Campo | Regra |
|---|---|
| `session_id` | Mesma sessão por boot selecionada pelo operador; identificador do contrato 0.1 |
| `sequence` | Decimal canônico, até 64 caracteres como os IDs existentes; estritamente crescente, independente de `frame_id` |
| `captured_at_ms` | Inteiro 0..2^53−1, relógio monotônico local do mesmo boot usado na câmera; não pode regredir |
| `distance_mm` | Inteiro 0..2^31−1 se válido; `null` se inválido; unidade sempre milímetros |
| `valid` | Booleano explícito; uma distância zero só é aceita quando explicitamente válida, nunca como preenchimento |
| `quality` | `good`/`degraded` para válido; `invalid` para inválido |
| `sector` | `left`, `center`, `right` ou `all`; setor definido na origem, sem projeção sobre YOLO |
| `zone` | Inteiro 0..63 quando `aggregation=zone`, caso contrário `null` |
| `aggregation` | `zone`: leitura da zona indicada; `min_valid_8x8`: mínimo somente das zonas válidas de toda a matriz, `sector=all` |

O intervalo inteiro do transporte não é especificação de alcance do sensor.
`quality` é classificação do produtor, não probabilidade/calibração. Hardware
deve documentar quais status nativos tornam uma zona válida/degradada, orientação
e numeração física 0..63 e como escolhe `sector`, antes de integrar. Não presumir
que zona zero tem uma orientação óptica específica. No mínimo agregado, se não
houver zona válida, enviar `valid=false`, `quality=invalid`, `distance_mm=null`.
Sem firmware confirmado, a implementação testa somente essa semântica proposta.

O servidor acrescenta `received_at_ms` (UTC Unix) e idade por relógio monotônico
próprio. Não subtrair relógio ESP do UTC da VM para calcular latência. A diferença
de captura ToF−imagem só é mostrada para a mesma sessão selecionada e pressupõe
o relógio comum exigido acima; não demonstra simultaneidade nem associação espacial.
Filas/retries de telemetria nunca podem bloquear sensores/geometria/tátil.
Primeira proposta: envio best effort, uma requisição ativa, sem fila de leituras
velhas. Cadência física deve ser acordada com hardware, abaixo do teto 10/s.

Limites operacionais: corpo inteiro ≤2048 bytes (inclusive sem Content-Length);
10 tentativas/s autenticadas da origem selecionada. API e painel são um processo.
Resposta 204 sem corpo quando aceita. Leituras inválidas são aceitas como
estado indisponível, substituem a anterior e não viram zero/caminho livre.

| HTTP | Significado |
|---|---|
| 400 | JSON/esquema inválido; não altera última medição |
| 401 | Sem credencial válida; rejeita antes de ler corpo |
| 403 | Credencial de outro dispositivo; rejeita antes de ler corpo |
| 409 `demo_conflict` | Boot não selecionado, sessão encerrada, sequência repetida/fora de ordem ou captura regressiva |
| 413 / 415 | Corpo excessivo / tipo incompatível |
| 429 | Limite agregado de ingestão; produtor deve descartar, sem fila |

O contador exibido no painel contabiliza conflitos de sessão/ordem da origem
selecionada; não é auditoria de ataques ou contador de erros de esquema.
Estados observáveis e retenção: [painel](../demo-panel.md).

`DELETE /v1/demo/session`, mesma autenticação, encerra só a observação e apaga
JPEG/ToF/previsões. Requisições futuras ao painel não repovoam a sessão encerrada
até recriação do processo. O serviço 0.1 continua disponível.

## Consultas do navegador

`GET /v1/demo/snapshot`: somente IPs permitidos, sem Bearer. Fonte/sessão, tipo
simulado/ESP configurado, backend, estado e idade independentes de imagem/ToF.
Estado `waiting`, `receiving`, `stale`, `invalid` ou `expired`; `ended` informa
fim de sessão. Imagem contém frame, captura, recebimento, hash, dimensões,
`inference` (`pending`, `available`, `unavailable`) e projeção de previsões.
ToF contém campos acima e recebimento. Nenhum segredo, caminho privado, texto
de áudio ou histórico. Metadados somem na expiração junto do payload.

`GET /v1/demo/image?frame_id=<id>&sha256=<hash>`: o único JPEG atual, sem cache.
409 quando houve substituição/expiração entre snapshot e download. Navegador
limpa imagem/caixas e tenta de novo no próximo ciclo; não associa dados antigos.
Os endpoints não alteram o resultado de `POST /v1/inference`.
