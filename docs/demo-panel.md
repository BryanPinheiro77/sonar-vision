# Painel de demonstração — #73

Responsável: Bryan (modelo/cloud). **Implementação e evidência local simulada;
AWS manual, CPU4 e ESP físico pendentes.** [ADR 0024](decisions/0024-painel-demonstracao.md),
[contrato ToF proposto](protocol/demo-tof.md), [referência visual aprovada](../DESIGN.md).
O outro trio revisará o contrato e implementará aquisição/envio na #17.

## Dados, estados e limites

`/demo` abre sem cadastro/login, somente nas redes autorizadas. Não contém
token do ESP. Mostra JPEG obtido da **API**, com caixas/classes/IDs do diagnóstico
original, sem outra inferência. Verifica SHA-256 antes de desenhar. Fonte, boot,
frame, captura, hash e epoch identificam a imagem. `simulated` identifica a fonte;
backend `simulated` é indicação separada de previsões roteirizadas. `esp32` é
declaração do operador, não atestado criptográfico de captura física.

Imagem e ToF têm idade/estado próprios. Inválida exibe indisponível, nunca zero
ou caminho livre. Distância não é atribuída a pessoa/caixa. Diferença de captura
usa o mesmo relógio de boot exigido no contrato, não implica sincronismo.
Falha somente no JPEG mantém ToF atual disponível; falha da consulta de estado
indica desconexão de ambos. Pausa/aba oculta suspendem consultas; dados envelhecem.

| Limite inicial de demonstração | Valor |
|---|---|
| Atualização / espectadores operacionais | A cada 2 s / até 3 abas, **provisório até CPU4** |
| Snapshots / JPEGs | Limite agregado 3/s de cada por processo; excesso 429 |
| ToF / assets | 10 tentativas/s da fonte selecionada / 24 requisições/s |
| Atraso | Idade desde recebimento ≥5 s, canais independentes |
| Retenção | Descarte aos 30 s, varredura a cada 1 s mesmo sem consultas |
| Memória do painel | Um JPEG ≤limite de upload (padrão 512 KiB), até 20 previsões, uma leitura ≤2048 bytes |
| Diagnóstico pendente | Após 2 s vira inferência indisponível |

Buffers de upload/inferência/respostas em trânsito também consomem memória;
isso não limita a RAM total do processo. Não há fila própria, histórico,
arquivo de imagem, banco ou treino automático. Coleta/dataset é #72. Diário
da #52 permanece desligado salvo avaliação explicitamente configurada. HTTP
no-store; frontend sem armazenamento persistente. Espectador ainda pode copiar
conteúdo. O limite agregado não identifica usuários: mais de três abas pode
causar429 nas demais. Três abas não são capacidade validada.

## Executar localmente sem placa

Python≥3.11 e ambiente virtual conforme [execução](execution.md). Simulador usa
OpenCV dos extras existentes, gerando retângulos/JPEGs com rótulo sintético:

```sh
python -m pip install -e '.[vision,api,api-dev]'
umask 077
mkdir -p .local/demo73
python -m sonar_vision_api.dev_tls .local/demo73/tls
python -m sonar_vision_api.tokens demo-sim .local/demo73/tokens > .local/demo73/device.token
export SONAR_API_BACKEND=simulated
export SONAR_API_TOKENS_FILE=.local/demo73/tokens
export SONAR_DEMO_ENABLED=1
export SONAR_DEMO_DEVICE_ID=demo-sim
export SONAR_DEMO_SESSION_ID=demo-73
export SONAR_DEMO_SOURCE_KIND=simulated
export SONAR_DEMO_ALLOWED_CIDRS=127.0.0.1/32,::1/128
python -m sonar_vision_api --port 8443 \
  --certfile .local/demo73/tls/server.pem --keyfile .local/demo73/tls/server-key.pem
```

Confiar explicitamente na CA pública local no computador/navegador de teste,
verificando origem e removendo confiança após o ensaio. Não desabilitar TLS,
usar `--insecure` ou distribuir chave privada. Abrir `https://localhost:8443/demo`.
Em outro terminal, ativar o mesmo ambiente:

```sh
PYTHONPATH=src python scripts/demo_source.py \
  --endpoint https://localhost:8443 --ca-file .local/demo73/tls/ca.pem \
  --token-file .local/demo73/device.token --session demo-73 \
  --frames 20 --interval 2 --exercise-errors
```

A fonte recusa servidor sem rótulo `simulated` ou sessão correspondente.
Alterna imagens visualmente distintas, registra hashes, envia inválida a cada
três amostras e sequência repetida esperando 409. Recibos não contêm tokens.
Para interromper canais separadamente, usar `--images-only` ou `--tof-only`;
manter o outro e aguardar 5 s/30 s. Reiniciar simulador conserva o boot selecionado
e usa IDs/sequências monotônicas. Novo boot físico exige nova sessão e recriação
do serviço. ToF pode iniciar antes da primeira imagem.

`--end-session` envia DELETE autenticado, apaga ambos os canais e bloqueia sua
repopulação até reinício. Encerrar também servidor por Ctrl+C. Nenhum desses
comandos mede sensor, áudio/tátil físicos ou segurança de navegação.

## Compose local

Mesmo serviço/imagem/volumes, sem porta adicional. Variáveis acima mais:

```sh
export SONAR_HOST_TLS_DIR=./.local/demo73/tls
export SONAR_HOST_TOKENS_FILE=./.local/demo73/tokens
export SONAR_HOST_MODELS_DIR=./models
mkdir -p models
export SONAR_UID=$(id -u)
export SONAR_GID=$(id -g)
docker compose -p sonar73 -f compose.yaml -f compose.demo.yaml up -d --build --wait
docker compose -p sonar73 -f compose.yaml -f compose.demo.yaml ps
```

No Docker o peer pode ser gateway NAT. Conferir o IP efetivamente visto e incluir
somente seu CIDR/32 em `SONAR_DEMO_ALLOWED_CIDRS`; recriar serviço. Não usar `/0`
ou X-Forwarded-For. Bind continua 127.0.0.1; não publicar externamente para
contornar 403. Teste dentro do contêiner não comprova acesso externo.

```sh
docker compose -p sonar73 -f compose.yaml -f compose.demo.yaml down
```

## AWS — roteiro manual de Bryan

**Não executado nesta entrega; não criar recursos agora.** Reutilizar
[operação AWS](aws-operation.md), CPU4/R21 e runner paralelo da #22. Conferir
conta/ledger e saldo agregado **US$15/8h**, sem renovar orçamento. Preservar
prazo absoluto/timer/guard, encerramento e limpeza da #23. Painel não acrescenta
instância/disco/serviço; contabilizar CPU/RAM e tráfego extras no mesmo ledger.

1. Revisar PR/commit, obter pesos legítimos/hashes, construir imagem com assets
   empacotados e registrar ID imutável/base/versões. Seguir transferência
   verificada, arquivos privados, TLS e preflight da #23.
2. Conferir prazo/timer/guard antes da API. Preservar CPU4/3GiB, runner paralelo
   e hashes. CLI serial não equivale ao perfil CPU4 medido.
3. Security Group: SSH 22 apenas operador/32; HTTPS 8443 apenas IPs públicos/32
   dos computadores da apresentação e da origem ESP. Nunca 0.0.0.0/0 ou ::/0.
   Registrar/remover regras ao terminar. Uma rede compartilhada autorizada
   também alcança a página sem login; não usá-la para imagens pessoais.
4. Fornecer URL e CA **pública** aos espectadores; confiar na CA pelo mecanismo
   do SO/navegador, ou usar certificado público já confiável. SAN deve incluir
   host/IP. Token individual fica só no ESP/cliente; chave TLS e operação privados.
5. Selecionar dispositivo/boot e fonte `simulated` no primeiro ensaio. Allowlist
   usa peers/32 efetivamente vistos, inclusive NAT. Conferir 403 de outro IP e
   que X-Forwarded-For não permite contorno. Não adicionar proxy nesta entrega.
6. Acrescentar `-f compose.demo.yaml` em **todos** os comandos do ensaio,
   preservando os overlays paralelo/áudio da #23. Não habilitar diário persistente.
   Na VM já preparada, com release/imagem/arquivos privados existentes:

```sh
export SONAR_DEMO_DEVICE_ID=demo-sim
export SONAR_DEMO_SESSION_ID=demo-73
export SONAR_DEMO_SOURCE_KIND=simulated
# IP de documentação: substituir pelos peers/32 autorizados conferidos.
export SONAR_DEMO_ALLOWED_CIDRS=203.0.113.10/32
PYTHONPATH=src python3 scripts/check_aws_release.py --parallel --audio
docker compose -p sonar23 -f compose.aws.yaml -f compose.aws.parallel.yaml \
  -f compose.aws.audio.yaml -f compose.demo.yaml up -d --wait --wait-timeout 120
```

O preflight original valida release/modelos/TLS, não SG/painel/sessão/benchmark.
Se fonte selecionada não tiver credencial provisionada, o processo recusa startup.

7. No cliente autorizado, enviar duas imagens com `demo_source.py` usando
   HTTPS/CA da VM. Conferir hashes do recibo/painel e download da **AWS**. Testar
   inválida, replay,401/403/413, atraso independente, retenção e DELETE. Evidência
   local não satisfaz esse passo. Guardar só agregados autorizados, sem JPEG/token.
8. Comparar condições 0/1/3 espectadores abaixo. Após revisão com hardware,
   selecionar `esp32`, boot novo e demonstrar ESP → AWS → navegador com ambos os trios.
   Comprovar fisicamente que falha de página/nuvem não altera tátil local.
9. Encerrar sessão e serviço próprios; limpar/auditar recursos da #23 (instância,
   volumes, SG/chaves), remover regras adicionais/confiança na CA e atualizar custo/
   tempo acumulado. Stop da instância não é limpeza completa.

Rollback: imagem/configuração anterior sem overlay demo, preservando credenciais
vigentes e prazo. Reinício perde imagens/leituras; não restaurar boot/tracks
antigos ou credencial revogada.

## Comparar latência e recursos no CPU4

`scripts/demo_benchmark.py` envia sempre o mesmo JPEG numa fonte explicitamente
simulada, com **backend real** para CPU4. Cada invocação mede uma condição sem
sobrescrever saída. Cliente mede HTTPS completo, não CPU/RAM remotos. Coletar
na VM com `sample_container.py` e logs da API, conforme
[reprodução #22](experiments/issue-22-reproduce.md). Registrar quota CPU4/3GiB,
hashes imagem/pesos/runner/configuração, rede, duração e aquecimento.

```sh
PYTHONPATH=src python scripts/demo_benchmark.py \
  --endpoint "$BENCH_ENDPOINT" --token-file "$BENCH_TOKEN" --ca-file "$BENCH_CA" \
  --session demo-73 --spectators 0 --duration 60 --fps 10 \
  --output .local/demo73/cpu4-r1-viewers0.json
```

Repetir para 1 e 3, saídas novas; repetir a série mais duas vezes, ordens 3/1/0 e
1/0/3. Sem outras abas. Espectadores gerados consultam snapshot/JPEG a cada 2 s,
sem renderização; complementar com três abas reais. Conferir zero erros/429,
FPS admitido e P50/P95/P99, deltas de CPU/RAM. Aplicar metas existentes #22 ao perfil
congelado (≥8 admissões/s, trabalho P95≤80ms, HTTPS P95≤150/P99≤250ms), sem inventar
tolerância nova do grupo. Se houver prejuízo, suspender painel/reduzir carga e
revisar antes da apresentação. Até medir, 2 s/três abas são limite **provisório**.

## Verificações e limites de aceite

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_demo.py -v
PYTHONPATH=src python scripts/run_tests.py --report-dir .local/demo73/test-report
python scripts/check_docs.py
git diff --check
```

[Evidência local e pendências](experiments/issue-73.md). Não há comandos de
vibração ou limiares locais novos; núcleo C++ e tarefas do ESP permanecem iguais.
Falha do painel preserva a API. Independência tátil física, ToF real, AWS e CPU4
dependem dos ensaios. Não encerrar a #73 como inteiramente validada antes deles.
