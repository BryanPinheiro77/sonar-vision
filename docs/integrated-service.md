# Serviço real e avaliação antes do deploy — #52

Objetivo: executar vídeo/webcam → cliente HTTPS → YOLO geral + ByteTrack +
especialista opcional de escadas → observações/sugestões → revisão no computador.
Responsável: Bryan, com apoio de IA. Decisão: [ADR 0015](decisions/0015-servico-real-diagnostico.md).
A aplicação não depende de novo treino. O candidato de móveis rejeitado na #51
não integra este conjunto. Não há firmware, TTS físico, compensação de câmera
móvel, gravação de vídeos na VM ou treino automático com uploads.

## Preparação

Python 3.11+, Docker/Compose e pesos confiáveis obtidos conforme
[releases](releases.md) e [visão](vision.md). Baseline de ensaio: YOLOv8n COCO
mais especialista **R20** congelado na #16 e autorizado por Bryan para integração.
O R20 é handoff local, não asset público; obtenha o pacote confiável com o
responsável e confira o hash abaixo. O v3 publicado permanece alternativa de
reprodução/rollback; o script de download público continua baixando v3.
Trocar o especialista exige registrar candidato/evidência na #16. Preserve o
peso geral: o especialista reconhece apenas `stairs_up`/`stairs_down`.

```sh
python -m pip install -e '.[vision,api,api-dev]'
python -m sonar_vision_api.dev_tls .local/tls
python -m sonar_vision_api.tokens glasses-01 .local/tokens > .local/glasses-01.token
mkdir -p .local/evaluation .local/diagnostics
chmod 700 .local/evaluation .local/diagnostics
cp docs/experiments/audio-lab-52.json .local/evaluation/audio.json
```

O arquivo de áudio é **perfil experimental de laboratório**, extraído dos
parâmetros já usados na [#31](audio.md); não aprovação de limites físicos.
Revise antes de habilitar. Sem `SONAR_API_AUDIO_CONFIG`, a API conserva
`audio: null`. A sugestão não comanda vibração nem confirma risco geométrico.

## API e Compose

Coloque ambos os pesos em `models/` (ignorado). Registre os hashes efetivos com
`python -c "from sonar_vision_api.runtime_options import file_hash; print(file_hash('models/yolov8n.pt'))"`
e repita para o especialista. Compare com a origem confiável antes de carregar:
o hash identifica o arquivo; não torna um `.pt` desconhecido seguro.

```sh
export SONAR_BUILD_EXTRAS=api,vision
export SONAR_API_BACKEND=ultralytics
export SONAR_API_WEIGHTS_IN_CONTAINER=/models/yolov8n.pt
export SONAR_API_STAIR_WEIGHTS_IN_CONTAINER=/models/stairs-specialist-r20-candidate.pt
# Substitua pelos hashes conferidos; divergência impede inicialização.
export SONAR_API_WEIGHTS_SHA256="<sha256-geral-conferido>"
export SONAR_API_STAIR_WEIGHTS_SHA256="<sha256-escadas-conferido>"
docker compose -f compose.yaml -f compose.evaluation.yaml up -d --build --wait
python -m sonar_vision_api.healthcheck --cafile .local/tls/ca.pem
```

Em Linux, execute com `SONAR_UID=$(id -u) SONAR_GID=$(id -g)` para leitura de
segredos e escrita na pasta privada, sem tornar arquivos acessíveis a todos.
No Docker Desktop confira igualmente a permissão do bind mount. Pesos, TLS e
configuração permanecem somente leitura; apenas diagnóstico tem volume gravável.
A porta permanece em loopback. Endpoint externo/certificado/orçamento AWS
pertencem a #22/#23; não usar `--insecure` nem desativar validação TLS.

O override ativa áudio **e** diagnóstico para avaliação. Só modelos: use apenas
`compose.yaml`. Só áudio/diagnóstico ou execução sem Docker: configure
`SONAR_API_AUDIO_CONFIG=/caminho/audio.json` e/ou
`SONAR_API_DIAGNOSTICS_DIR=/diretorio/privado` na API executável, junto dos
parâmetros de [api.md](api.md). Nenhuma opção adiciona endpoint público.

Ambos os modelos validam suas classes e aquecem antes de servir. Hashes são
registrados no início e no diagnóstico, junto da configuração e versões.
Rollback: restaurar o par de arquivos confiáveis, seus hashes e a configuração
anterior, recriar o serviço e iniciar nova sessão de cliente. Epochs/IDs antigos
não devem ser concatenados como uma trajetória após reinício.

## Cliente de avaliação

Vídeo autorizado permanece local. Identifique sua origem por um `source-id`
não pessoal; o cliente não envia o caminho ao servidor. Orientação e urgência
abaixo são simuladas, não sensores do ESP32.

```sh
export SONAR_VISION_TOKEN=$(cat .local/glasses-01.token)
python -m sonar_vision.simulator \
  --video /caminho/privado/video.mp4 --source-id local-B-autorizado \
  --endpoint https://localhost:8443/v1/inference --ca-file .local/tls/ca.pem \
  --fps 2 --max-edge 640 --frames 20 --report .local/recibos-B.jsonl
unset SONAR_VISION_TOKEN
```

Para webcam, troque `--video` por `--webcam 0`; informe igualmente a origem.
Para endpoint remoto, use seu HTTPS e a CA correspondente, ou o trust store
público omitindo `--ca-file`. O transporte existente mantém um envio ativo,
prazo total de 2000 ms, validação de resposta e descarte por idade/orientação/
urgência; o serviço mantém um slot sem fila e rejeita concorrência (`busy`).

`--fps` é o máximo solicitado, não promessa de taxa entregue. O vídeo avança
pelo tempo real; frames intermediários são pulados, sem acumular capturas
antigas. `--max-edge` reduz o maior lado preservando proporção, sem recorte;
é escolha explícita de upload, distinta do `image_size` do modelo.
`--jpeg-quality` permite registrar compressão de 1 a 100; padrão 95 conserva
a codificação anterior. Qualidade maior aumenta o upload e pode exceder o
limite de corpo. A revisão reconstrói a qualidade registrada no recibo (95 em
recibos antigos), sem confundir captura comprimida com pixels originais. Registre
resolução/cadência e não compare experimentos que mudaram essas condições.
Sem essas opções, o comportamento de captura anterior permanece disponível.

Saída mostra classe, confiança, ID, sentido de escadas, movimento, latência e
motivo do descarte. Texto só é exibido quando a sugestão passou a arbitragem
local simulada; não é reprodução física de áudio. Movimento permanece `unknown`
para câmera móvel/desconhecida. Escadas adicionadas pelo especialista podem
ter ID nulo: o especialista ainda não possui tracking próprio.

## Revisão privada das previsões remotas

Cada início cria `.local/diagnostics/predictions-<id>.jsonl`, exclusivo, modo 600.
Não contém JPEG/token/identidade do dispositivo/texto de fala; contém caixas
normalizadas, IDs, classe/confiança/escadas, hash do JPEG, captura, observação,
epoch e configuração. Session_id é representado por hash. É diagnóstico de
processamento, **não admissão pelo cliente**. Obtenha-o por acesso de operador;
não existe endpoint de download público.

```sh
python -m sonar_vision_integration.review \
  --receipts .local/recibos-B.jsonl \
  --journal .local/diagnostics/predictions-ID.jsonl \
  --video /caminho/privado/video.mp4 --output .local/revisao-B.html
```

Use `--journal` repetido se houver reinícios. A revisão associa caixas somente
quando observação, frame, captura, epoch e hash do JPEG coincidem. Diagnóstico
perdido/desligado aparece como indisponível, não como ausência de objeto.
Respostas descartadas não viram previsões admitidas. Sem `--video`, o HTML tem
apenas dados. Com `--video`, reconstrói localmente os frames enviados, verifica
hashes e salva imagens com caixas do **servidor**, sem rodar outra inferência.
Exige o mesmo OpenCV/encodificação usados no cliente; diferença de reconstrução
aborta a associação visual. HTML/imagens/recibos são privados e não versionados.

Diagnóstico tem fila própria de 64 registros e limite de 64 MiB por arquivo;
falha, fila cheia ou limite descarta diagnóstico sem invalidar a resposta.
A criação de arquivo solicitado que falhar impede startup. Limite é por
arquivo: configure limpeza/retenção de reinícios antes do deploy (#23).

## Coleta e aperfeiçoamento dos modelos

1. Registre localmente autoria/permissão, data, cenário, ambiente e hash do
   original. Vídeos de pessoas identificáveis exigem as condições éticas do
   projeto; não os publique em issue/Git.
2. Separe locais/objetos/sequências antes de observar resultados. Preserve um
   conjunto independente; não use frames vizinhos em treino e avaliação.
3. Anote/revise caixas/classes e, para tracking, identidades consistentes ao
   longo da sequência e movimento da câmera. Manifesto privado relaciona
   original, frame, dimensões enviadas e transformação. Referência humana deve
   anteceder a consulta às previsões; não converter caixas do modelo em verdade.
4. Congele pesos/hash/configuração; execute cliente e preserve recibos/
   diagnóstico para a #7/#33. Medir IDs emitidos não mede acurácia de tracking.
5. Classifique falsos positivos, omissões, trocas/perdas de ID e inconclusivos.
   Só abra rodada de treino quando essas falhas justificarem o objetivo,
   separação dos dados e critério de aceitação. Treino ocorre separadamente da API.
6. Reavalie candidato congelado em conjunto independente; registre resultado
   negativo e faça rollback quando necessário. Nunca troque peso durante ensaio.

Os vídeos atuais de cadeira/mesa permitem investigar detecção. Para avaliar
tracking andando, grave sequências contínuas com alvos visíveis, entradas/saídas,
oclusões e câmera em movimento, anotando identidades. Não basta pessoa andando
para validar aproximação física: compensação/IMU e geometria permanecem pendentes.

## Verificações

```sh
python scripts/check_docs.py
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python scripts/smoke_vision.py \
  --weights models/yolov8n.pt --stair-weights models/stairs-specialist-r20-candidate.pt \
  --report .local/smoke-vision-52.json
```

Smoke optativo constrói imagem CPU real, carrega ambos os pesos, monta perfil de
áudio explícito e diagnóstico privado, usa cliente HTTPS externo e pixels pretos
sintéticos. Verifica TLS/401, inferência/contrato, replay, busy, timeout, reinício,
hashes e usuário não root; remove serviço e arquivos efêmeros ao terminar.
Não mede acurácia visual. Demais falhas/arbitragem/independência tátil têm testes
controlados de integração; caminho tátil físico não está validado.

### Evidência desta implementação (2026-10-06)

- Suíte completa: **324 testes passaram, zero skips**, com extras e
  `SONAR_E2E_WEIGHTS` apontando ao YOLOv8n local confiável; inclui ByteTrack real,
  HTTP/HTTPS, política, expiração, independência tátil simulada e testes novos.
- Docs e Ruff (`E4,E7,E9,F`): passaram. Nenhuma dependência nova.
- Docker CPU: **15 verificações passaram**, incluindo ambos os pesos/hashes,
  configuração explícita de áudio, 401, TLS inválido, 200, replay, busy, prazo de
  1 ms com 503, reinício com epoch/arquivo novos e uid não root. Docker 29.5.2,
  Compose 5.5.1 no ambiente local; Linux com uid próprio ainda não exercitado.
- Cliente separado com vídeo próprio autorizado B, 16 capturas solicitadas a
  2 FPS e upload com maior lado 640: 16 observações admitidas, zero diagnósticos
  ausentes, sugestão “Cadeira” na primeira captura e supressão nas seguintes.
  IDs/caixas foram correlacionados e reconstrução de todos os JPEGs conferida.
  Latência local p50 47 ms/p95 51 ms; amostra pequena em localhost/macOS,
  **não medição AWS, meta garantida ou acurácia**. Semântica móvel unknown.
- Vídeo A, quatro capturas iniciais: observações admitidas sem objetos/sugestão;
  resultado negativo preservado. Não mede taxa de detecção do vídeo inteiro.

Hashes usados: YOLOv8n
`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`;
escadas v3
`8949d163cab5bfe429a5b4c5d68f683d24a8291a468591f6f719488144d8fec4`.
Os dados/recibos/HTML de avaliação permanecem privados e ignorados pelo Git.
Não foram validados detecção independente de escadas em vídeo, qualidade de
tracking andando, geometria/TTC, AWS, firmware, vibração ou reprodução física.

### Integração do R20 autorizada por Bryan

Perfil congelado: [modelos e parâmetros](experiments/integration-52-r20.json).
Resultados agregados: [ensaio HTTPS](experiments/integration-52-r20-results.json).

- R20 carregado junto de YOLOv8n pela API executável; classe do especialista
  validada, hash conferido, aquecimento e contrato 0.1 preservados. Sem treino.
- Docker CPU com R20: as mesmas 15 verificações passaram.
- 173 casos conhecidos enviados por cliente HTTPS externo em dois modos
  (geral sozinho e geral+R20): 346 observações admitidas, diagnósticos completos.
  As 49 detecções gerais, com classe/confiança/caixa/ID, foram preservadas
  nos 173 pares. Isso não garante retenção quando o limite de 20 objetos atua.
- Entrada de avaliação: maior lado640, JPEG95, confiança0,35, imgsz640 e CPU;
  regra de referência da #16 conservada (sentido e IoU0,50, todos os alvos).
  Resultado **164/173**; os oito problemas prévios continuam e um caso
  adicional foi perdido após a transformação de upload. Não é validação
  independente: há referências conhecidas e material de treino nesse conjunto.
- Comparação controlada do caso adicional: pixels nativos e resize640 sem
  JPEG detectam o alvo; resize640+JPEG95 o perde. Native JPEG95 e resize640
  JPEG100 o recuperam. O problema observado envolve compressão/redimensionamento,
  sem atribuir regressão ao treinamento do R20. A confiança não foi alterada.
- Ensaio exploratório completo em JPEG100 também resultou em **164/173**,
  recuperando um caso e perdendo outro. Não foi adotado como padrão; não
  escolher qualidade por uma única imagem nem tratar esse conjunto como teste
  independente após consultá-lo. JPEG95 permanece o padrão explícito.
- Latência local geral+R20 em JPEG95: p50 38 ms/p95 49 ms, 173 capturas;
  geral sozinho p50 20 ms/p95 26 ms. São medidas localhost/macOS, sem AWS.

A #52 entrega infraestrutura de avaliação experimental com falhas conhecidas;
o R20 não recebe promoção de produção ou aceite final da #16/#7. Avaliar o
caminho completo de captura/encode/upload será parte das próximas coletas,
preservando pesos/parâmetros e referências independentes.

- Vídeo B com R20: 16 capturas admitidas e correlacionadas, cadeira com ID2
  em 15 das 16, uma sugestão Cadeira e supressão nas demais; nenhuma escada emitida
  nesse trecho. P50 48 ms/p95 57 ms em localhost. Sem afirmação de acurácia
  de tracking; as capturas dessa repetição não são idênticas às da rodada v3.
