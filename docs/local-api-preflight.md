# Ensaio local: frames, detecção, IDs e sugestão de áudio — #19

Responsável: Bryan. Data: 2026-10-17.
[Serviço integrado](integrated-service.md) · [Cliente](simulator.md) ·
[Revisão de áudio](experiments/issue-32-revisao.md) · [Movimento](motion-replay.md).

## Objetivo

Verificar no computador o caminho vídeo → JPEG → API HTTPS → YOLO geral/R21 →
recibos do cliente → relatório com caixas, IDs e frase aceita ou motivo de
supressão/descarte. A API envia **sugestão em texto**, não arquivo de voz.
Não há TTS, áudio físico, firmware, compensação de câmera ou nova infraestrutura.
O caminho tátil local continua independente. Isso não conclui #19/#7/#11/#16.

## Ensaio executado

O macOS recusou leitura do vídeo original nos Downloads. A restrição foi
respeitada: montou-se uma sequência privada com quatro capturas já autorizadas
e congeladas do local B, cada uma repetida por três segundos. **Não é o vídeo
contínuo original e não é evidência de qualidade de tracking/movimento.**
Essas cenas já foram usadas na #51; não são teste independente cego.

A execução usou a API real em processo local, TLS validado, YOLO geral + R21 e
perfil experimental aprovado da #31, com hashes conferidos. Base de código
executada: c52c88989b88e35c7d943f44a1022a7f851c034f. A preparação do replay #65
foi incorporada depois; os comandos de API/cliente/revisão usados não mudaram.

[Resultado agregado](experiments/issue-19-local-preflight.json):

| Medida | Observado |
|---|---|
| Frames HTTPS admitidos | 120 |
| Frames admitidos sem diagnóstico correlacionado | 0 |
| Sugestão aceita | 1: “Cadeira”, presente no catálogo e acompanhada de chair elegível |
| Frames aceitos sem nova sugestão | 119; a política não narra a cada frame |
| Evento final da fonte | 1 source_ended_or_decode_failed; não foi frame aceito |
| Observações de classe por objeto/frame | 90 chair, 270 unknown; não são contagens de objetos distintos |
| Latência do cliente | P50 39 ms, P95 44 ms, P99 49 ms; escopo local do recibo |
| Limite de oferta e upload | 10/s solicitados, max-edge 640, JPEG95 |
| Encerramento | API parada; tokens/TLS temporários removidos |

A frase aceita foi conferida por igualdade exata no catálogo. Isso não comprova
compreensão/pronúncia nem identifica corretamente todo objeto. Unknown de classe
inclui normalização fora do vocabulário; não chamar todas essas observações de
falhas de modelo. O diagnóstico não preserva a classe COCO bruta para resolver
cada caso automaticamente; a revisão de causas segue na #7.
O cliente atual não distingue EOF de corrupção do decoder nesse evento terminal.
A sequência gerada tinha 120 frames e os 120 foram aceitos; registrar a limitação
sem reclassificar o evento como timeout de rede ou apagar o registro.

## Preparar os vídeos novos

Guardar originais privados em videos/issue-7/ ou outra pasta com acesso permitido
pelo sistema. Se Downloads estiver protegido, mover/copiar pelo Finder para uma
pasta autorizada; não alterar proteção do macOS automaticamente. Registrar autoria,
permissão, cenário, iluminação e contexto da câmera conforme a #7.
Preservar fontes reservadas antes de abrir predições, se houver teste independente
com protocolo/anotação aprovados. Vídeos de exploração não viram treino automático.

## Repetir com os comandos existentes

Na raiz de checkout atualizado, Python >=3.11 com os extras existentes:

```sh
python -m pip install -e '.[vision,api,api-dev]'
```

Obter os pesos do pacote privado autorizado e colocá-los em models/general.pt e
models/stairs-r21.pt, pasta ignorada pelo Git. Não baixar/carregar .pt desconhecido.
Conferir a origem e os hashes do [perfil R21](experiments/issue-22-r21-profile.json).
O R20 fica reservado para rollback, sem seleção pós-teste do melhor resultado.
Os placeholders abaixo são nomes de arquivos locais, não URLs para upload.

### 1. Preparação, uma vez por rodada

Exemplo POSIX; usar nome novo se .local/ensaio-01 já existir. Não reutilizar
certificados/recibos de outra rodada nem versionar tokens, imagens ou relatórios.

```sh
umask 077
mkdir -p .local
mkdir .local/ensaio-01
mkdir .local/ensaio-01/diagnostics
python -m sonar_vision_api.dev_tls .local/ensaio-01/tls
python -m sonar_vision_api.tokens glasses-local .local/ensaio-01/tokens > .local/ensaio-01/token
```

A pasta .local/ deve existir (`mkdir -p .local`). A CA é apenas de desenvolvimento;
nunca usar --insecure nem desligar a verificação de certificado.

### 2. Terminal da API

```sh
export SONAR_API_BACKEND=ultralytics
export SONAR_API_TOKENS_FILE="$PWD/.local/ensaio-01/tokens"
export SONAR_API_WEIGHTS="$PWD/models/general.pt"
export SONAR_API_WEIGHTS_SHA256=f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36
export SONAR_API_STAIR_WEIGHTS="$PWD/models/stairs-r21.pt"
export SONAR_API_STAIR_WEIGHTS_SHA256=449aecd65557e18a982a4c3ab6a33c7a7e41020b7f368b4305db4a1823607813
export SONAR_API_AUDIO_CONFIG="$PWD/docs/experiments/audio-experimental-31.json"
export SONAR_API_DIAGNOSTICS_DIR="$PWD/.local/ensaio-01/diagnostics"
python -m sonar_vision_api --host 127.0.0.1 --port 8443 \
  --certfile .local/ensaio-01/tls/server.pem \
  --keyfile .local/ensaio-01/tls/server-key.pem
```

Usar porta livre; se mudar 8443, mudar também o endpoint do cliente e healthcheck.
A API fica só em loopback. Sem a configuração de áudio, o padrão é audio=null;
isso não é defeito do detector. API verifica os hashes e aquece antes de servir.

### 3. Outro terminal, cliente e revisão

Substituir videos/issue-7/shopping-01.mp4 pelo arquivo autorizado. O source-id
é rótulo opaco, não nome/endereço de participante. Orientação/urgência abaixo
são simuladas pelo cliente padrão; não são sensores nem câmera fixa.

```sh
python -m sonar_vision_api.healthcheck \
  --url https://localhost:8443/healthz --cafile .local/ensaio-01/tls/ca.pem
read -r SONAR_VISION_TOKEN < .local/ensaio-01/token
export SONAR_VISION_TOKEN
python -m sonar_vision.simulator \
  --video "videos/issue-7/shopping-01.mp4" --source-id shopping-exploratorio-01 \
  --endpoint https://localhost:8443/v1/inference --ca-file .local/ensaio-01/tls/ca.pem \
  --fps 10 --max-edge 640 --jpeg-quality 95 --frames 200 \
  --report .local/ensaio-01/recibos.jsonl
unset SONAR_VISION_TOKEN
```

O limite de 200 é teto de frames solicitado para este exemplo, não tamanho
mínimo de amostra. `--fps 10` é oferta máxima, não garantia de 10/s admitidos.
O envio mantém uma requisição ativa, sem acumular imagens antigas. Gravar vídeos
não exige subir VM nem enviar imagens à internet nesta etapa.

Parar a API com Ctrl+C no primeiro terminal para drenar o diagnóstico. Depois:

```sh
python -m sonar_vision_integration.review \
  --receipts .local/ensaio-01/recibos.jsonl \
  --journal .local/ensaio-01/diagnostics/predictions-*.jsonl \
  --video "videos/issue-7/shopping-01.mp4" \
  --output .local/ensaio-01/revisao.html
```

A rodada deve conter um único journal; para múltiplos, repetir --journal com
cada arquivo. O HTML reconstrói os frames enviados e verifica hashes antes de
associar caixas; não faz segunda inferência. Se mudar vídeo/codec/OpenCV, não
forçar associação após divergência. Abrir o HTML localmente e manter as imagens
anexas na mesma pasta. Encerrar API e remover os segredos temporários da rodada
após o uso; preservar somente os resultados privados necessários à revisão.

## Como revisar

- Conferir imagem, classe, caixa, confiança e ID com referência humana. Contar
  IDs não mede pessoas nem continuidade correta.
- Ler a coluna Sugestão: texto significa aceito pela simulação do cliente,
  **não áudio efetivamente tocado**. no_suggestion pode ser cooldown, classe
  fora do vocabulário ou score insuficiente, não apenas erro de API.
- Conferir sentido up/down/unknown; não inferir borda de degrau ou risco local.
- Movimento unknown andando é a limitação atual da #11. Não declarar fixed para
  forçar aproximação/cruzamento; separar trechos parados e em movimento.
- Registrar falsos positivos/negativos e trocas/perdas de ID somente com
  anotações/revisão apropriadas; esta visualização não calcula acurácia.
- Classificar falhas de modelo, compressão, tracking, rede e latência antes de
  propor treino. Não modificar confiança/pesos em meio ao conjunto congelado.

Para medir movimento com referências humanas e timestamps revisados, usar o
[replay da #11](motion-replay.md), separado deste ensaio HTTPS. Esse replay
processa imagens originais decodificadas; não confundir com a transformação
max-edge/JPEG95 do caminho de API.

Nenhuma voz foi produzida/reproduzida. Formato, direitos, aprovação dos textos e
revisão de compreensão continuam na #32/#5; reprodução física, orientação real
e urgência ficam com o trio de firmware. Hardware e qualidade independente
não foram validados por este ensaio.

## Verificações após os merges

PRs #65 (replay da #11) e #67 (preparação de áudio) foram incorporados após
review com BryanPinheiroDev e dez checks de CI passando em cada head final.
A regressão combinada local encontrou **403 testes**, todos passaram em 46,61 s,
zero falhas/erros/skips, com extras e peso geral confiável. O teste opcional do
detector real usa vídeo sintético, sem alegar qualidade independente. O ensaio
HTTPS descrito acima é uma execução adicional, com capturas autorizadas conhecidas.

Comandos de verificação existentes:

```sh
PYTHONPATH=src python scripts/run_tests.py --report-dir .local/test-report
python scripts/check_docs.py
git diff --check
```

Sem extras/peso autorizado, os testes opcionais podem aparecer skipped, o que
não valida o detector real. A evidência deste ensaio contém apenas agregados;
HTML, imagens e recibos ficaram privados. Nenhum vídeo/peso/token foi commitado.
