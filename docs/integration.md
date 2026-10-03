# Testes de integração e ponta a ponta — #27

Verificam os componentes conectados (cliente → HTTPS → autenticação → API →
`VisionService`/tracker → contrato → arbitragem local de áudio) e os modos de
falha, com cenários reproduzíveis. Complementam, sem substituir, os testes
unitários de cada módulo. Responsável pela coordenação: Julio.

Teste em computador **não** valida acurácia visual, ergonomia, bancada física
nem o firmware.

## Peças

| Módulo | Papel |
|---|---|
| `src/sonar_vision_integration/server.py` | Servidor HTTPS real em processo (uvicorn + TLS + API da #24) com uma CA temporária e tokens gerados na hora. O backend padrão é **simulado e controlável** (atraso, bloqueio e falha) |
| `client.py` | Cliente mínimo dos óculos: uma requisição ativa por dispositivo (`ClientBusy`, sem fila), timeout total de 2000 ms, registro de capturas e validação completa da resposta antes de qualquer efeito |
| `tactile.py` | Simulação independente do caminho tátil numa thread própria, enquanto a rede ou a API ficam travadas |
| `bench.py` | Medição ponta a ponta dependente do ambiente, com versões, configuração e commit |

O cliente daqui **não** é o simulador dos óculos da #30 (Matheus). Ele cobre
só o necessário para estas verificações. Quando a #30 entrar na `main`, os
cenários podem usá-lo como transporte.

## Cenários cobertos (`tests/test_e2e.py`, determinísticos)

| Critério da #27 | Teste |
|---|---|
| Captura simulada → API → detector/tracker → resposta | `test_capture_api_tracker_response` |
| Áudio: sugestão → validação no cliente → arbitragem local (#25) | `test_audio_suggestion_reaches_local_arbitration` |
| Credencial ausente ou inválida | `test_missing_and_invalid_credentials` |
| Certificado inválido (CA desconhecida, hostname errado) | `test_untrusted_ca_and_wrong_hostname_fail_closed` |
| Limites de payload e pixels, campos incorretos, tipo de mídia | `test_payload_limits_and_incorrect_fields` |
| Sessão expirada (reabre com epoch novo) | `test_expired_session_reopens_with_new_epoch` |
| Sessões misturadas, reboot e isolamento entre dispositivos | `test_mixed_sessions_and_devices_stay_isolated` |
| Timeout, `busy` sem acumular frames, trabalho abandonado | `test_timeout_then_busy_without_accumulating_frames` |
| Uma requisição ativa por dispositivo no cliente | `test_one_active_request_per_device_on_client` |
| Desconexão do servidor, sem reenviar a captura | `test_disconnection_is_reported_without_retry` |
| Cancelamento pelo cliente não libera o slot antes da hora | `test_client_cancellation_does_not_free_the_slot_early` |
| Respostas duplicadas, vencidas e fora de ordem; frame reenviado | `test_duplicate_expired_and_out_of_order_responses` |
| API travada não bloqueia o caminho tátil simulado | `test_api_lockup_does_not_block_simulated_tactile_path` |
| Rede travada não bloqueia o caminho tátil simulado (sem extras) | `test_network_lockup_does_not_block_simulated_tactile_path` |
| Relatório separa números dependentes do ambiente | `test_benchmark_report_separates_environment_numbers` |

**Independência tátil:** uma thread de laço tátil (período de 10 ms) lê uma
distância simulada e "vibra" quando há obstáculo, enquanto outra thread fica
presa numa requisição: um socket TCP que nunca responde, ou a API com a
inferência bloqueada. O teste confirma que a vibração simulada começa
**enquanto a rede ainda está presa**. O limite de 250 ms é folgado de
propósito, porque o escalonador de um computador não é o FreeRTOS. Isso **não**
é validação de hardware nem de limiares da #9.

## Testes com detector real (opcionais)

`tests/test_e2e_real.py` roda só com `SONAR_E2E_WEIGHTS` apontando para um
`.pt` confiável já obtido (veja o [guia de visão](vision.md)) e com
`.[vision,api,api-dev]` instalados. O teste não baixa pesos, não usa câmera e
não acessa serviços externos. Ele não roda no CI. Sem a variável, aparece
como skipped.

## Execução

Instalação, na raiz:

```sh
python -m pip install -e '.[api,api-dev]'
```

Bash:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_e2e*.py' -v
```

PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p "test_e2e*.py" -v
```

Para rodar o teste opcional com o detector real (PowerShell):

```powershell
$env:SONAR_E2E_WEIGHTS = "models/yolov8n.pt"
python -m unittest discover -s tests -p "test_e2e_real.py" -v
```

Benchmark, que é dependente do ambiente e grava em `results/` (ignorado pelo Git):

```sh
python -m sonar_vision_integration.bench --frames 50 --output results/issue27-simulated-01.json
python -m sonar_vision_integration.bench --frames 50 --weights models/yolov8n.pt --output results/issue27-real-01.json
```

O relatório registra commit, Python, plataforma, versões dos pacotes,
configuração, desfechos (admitidos e descartes por motivo), tempo de ida e
volta no cliente e tempos por etapa no servidor (`read_ms`, `decode_ms`,
`inference_ms`, `policy_ms`, `encode_ms`, `work_ms`, `total_ms`). Nunca
registra imagens, tokens ou caminhos locais, e não sobrescreve arquivos.

## Automação

- **Sem extras** (job *Unit tests*): roda a simulação tátil com socket travado;
  os demais testes de ponta a ponta aparecem como skipped.
- **Com `.[api,api-dev]`** (job *API tests*): roda todos os cenários
  determinísticos, sem câmera, credencial real, pesos ou custo.
- **Detector real e benchmark:** apenas manuais e opcionais.

Não há decisão arquitetural nova nesta issue, portanto não há ADR. Os testes
exercitam as decisões das ADRs 0003, 0007 e 0008.

## Limitações

- Rede de loopback num único computador: sem Wi-Fi, ESP32, câmera ou TLS do firmware.
- O backend simulado devolve detecções roteirizadas. Isso não mede o modelo.
- No Windows, conexão recusada aparece como timeout depois de cerca de 2 s; no
  Linux, como `connect`. O teste aceita os dois, porque ambos significam
  "indisponível, sem reenvio".
- Os testes com tempo (timeout e laço tátil) usam folgas generosas e podem ficar
  mais lentos em máquinas sobrecarregadas.
- A ordem de respostas fora de ordem é testada pela admissão no cliente. Com
  uma requisição ativa, o transporte não produz essa situação sozinho.
