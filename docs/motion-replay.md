# Replay local de vídeo para avaliação — #11

Responsável: Bryan. Data: 2026-10-17.
[Especificação](experiments/issue-11-replay-spec.md) ·
[Avaliador pareado](motion-evaluation.md) · [Plano de coleta](experiments/issue-7-plano.md).

## O que passou a existir

O comando conecta vídeo privado autorizado → YOLO/ByteTrack → VisionService →
snapshot de detecção e sidecar de movimento. Usa os adapters existentes, sem
mudar API, journal, preview, parâmetros de trajetória ou contratos do ESP.
Preserva classes do detector geral; o especialista opcional acrescenta escadas.
R21 continua candidato e R20 rollback; não há treino ou promoção de modelo.

O caminho tátil local continua independente. Esta é ferramenta de modelo/cloud,
sem montagem, nova VM, cobrança ou implementação de firmware.

## Entradas necessárias

Instalar os extras existentes `python -m pip install -e '.[vision]'`.
Obter pesos por origem autorizada e conferir hashes conforme [releases](releases.md).
Não usar arquivos .pt de origem desconhecida. Não publicar vídeo/pesos/anotações.

Preparar **um clip por execução**, com revisão humana anterior das anotações:

1. `snapshot-anotado.json`: formato v1 da [#33](evaluation.md), com manifesto
   da mídia original e SHA-256 correto; `frames` em índices originais crescentes,
   `status=ok`, `predictions=[]`, caixas/classes/identidades/visibilidade humanas.
   `tracker_epoch` pode ser o token `annotation-template`, `latency_ms=0` apenas
   como placeholder que será substituído, nunca como medição. O run descreve
   o código efetivamente usado, hash do peso geral e protocolo escolhido;
   `latency_scope=processing`, `model_load_included=false`,
   `tracker_version=ByteTrack-8.4.137`. Confiança/tamanho/device vêm desse run.
2. `motion-anotado.json`: sidecar v1 com predições vazias, referências humanas,
   configuração completa de TrajectoryConfig, contexto de câmera e timestamps
   de apresentação revisados, na mesma ordem. Atribuir `snapshot_sha256` ao
   SHA-256 de `evaluation.canonical(snapshot)` depois de terminar o template.
3. Vídeo privado correspondente. O CLI exige kind=recorded; não usar mídia
   gerada/sintética como evidência real. Testes internos sintéticos são separados.
4. Para `split=test`, congelar amostra, anotação e parâmetros aprovados antes
   de rodar. O CLI não autentica consentimento, ética, independência ou aprovação;
   referências preenchidas não substituem a revisão exigida pela #7.

É preciso anotar a sequência selecionada inteira, inclusive ausências do alvo.
O runner não cria anotações nem interpreta vídeos antigos como verdade.
Preservar índices originais, timestamps de apresentação e regra de amostragem;
para VFR, não derivar tempo por FPS médio. O programa confere ordem/tipos/hash,
mas **não consegue provar** que os timestamps revisados correspondem à captura.
`fixed` é uma declaração controlada, nunca uma inferência de caixas/IMU.

O decode é sequencial, sem seek aproximado. Frames não selecionados são lidos,
mas não atualizam tracker/estimador: os resultados só descrevem essa sequência.
Registrar os gaps e não apresentar replay esparso como avaliação de todo o vídeo.
O manifesto v1, snapshot e sidecar mantêm seus formatos; não há schema novo de rede.

## Executar

Exemplo POSIX com arquivos privados; substituir os nomes pelos artefatos revisados:

```sh
PYTHONPATH=src python -m sonar_vision.replay_motion \
  --snapshot datasets/issue-11/snapshot-anotado.json \
  --motion datasets/issue-11/motion-anotado.json \
  --video videos/issue-11/tomada.mp4 \
  --weights models/general.pt \
  --stair-weights models/stairs-r21.pt \
  --stair-sha256 449aecd65557e18a982a4c3ab6a33c7a7e41020b7f368b4305db4a1823607813 \
  --output results/issue-11/replay-01
```

Sem especialista, omitir os dois argumentos de escadas; isso não avalia o R21.
Não usar o especialista de duas classes no lugar do detector geral.
O CLI verifica hash de ambos os pesos e do vídeo antes da inferência, além das
resoluções durante decode. Versão do ByteTrack deve corresponder ao factory.
A confiança sugerida do perfil R21 é 0,35 e imgsz 640; o comando não aprova
silenciosamente o protocolo do template nem troca a configuração fornecida.

O diretório novo contém snapshot.json, motion.json e provenance.json.
Proveniência guarda configurações efetivas de modelos/tracker e trajetória,
hashes e limitações. Os arquivos têm dados privados por frame; não anexar ao PR.
O stdout informa apenas contagem e acceptance_evaluated=false. Em POSIX,
diretório novo usa 0700 e arquivos 0600; isso não é criptografia nem política
institucional de compartilhamento. Não sobrescreve e recusa saída fora de results/.

Depois, usar a ferramenta já existente:

```sh
PYTHONPATH=src python -m sonar_vision.evaluate_motion \
  --snapshot results/issue-11/replay-01/snapshot.json \
  --motion results/issue-11/replay-01/motion.json \
  --output results/issue-11/metricas-01.json \
  --review results/issue-11/revisao-01.json
```

Escolher novo nome ao repetir. Erro/EOF antecipado/resolução divergente abortam
sem publicar avaliação de sucesso; investigar a mídia e repetir, sem apagar
falhas do relatório do experimento. Falha de disco durante escrita pode deixar
bundle incompleto: descartá-lo da análise e escolher saída nova. O CLI não
converte falhas de decode em um relatório completo de qualidade ponta a ponta.

## Medição e limitações

- Cada latency_ms mede trabalho do VisionService no relógio do processo;
  elapsed_ms do replay inclui decode e abertura da sessão, exclui carga do modelo
  e warmup descartável. FPS de replay é throughput, não cadência real dos óculos.
- A imagem é BGR decodificada original. Não aplica upload max-edge/JPEG95,
  rede, admissão AWS ou compressão do ESP. Esses caminhos exigem ensaio separado.
- A exportação da #33 agora preserva stair_direction do Result, em vez de
  substituir up/down por unknown. Não altera a observação da API. Escadas sem
  track_id continuam sem identidade e com movimento unknown/no_track.
- O comando é executável com entradas reais revisadas, mas ainda não existem
  nesta entrega novas anotações independentes ou medição de qualidade real.
- Não conclui #7/#11/#16/#19, não mede risco/TTC e não aprova uso autônomo.

## Verificação da entrega

[Evidência agregada](experiments/issue-11-replay-results.json), macOS/Python 3.11.16:
398 testes passaram, zero falhas/erros/skips, com extras e peso geral confiável.
Após o ajuste de tratamento de erros, 49 testes direcionados passaram novamente,
sem skips. Nove testes novos verificam alinhamento/imutabilidade, câmera móvel,
EOF/resolução/falha de inferência, recusa de templates preditos, integridade,
privacidade/não sobrescrita e sentido de escadas. O teste de integração usa
OpenCV e YOLO real em vídeo sintético gerado no teste, não cenas independentes.

Ruff passou e links/documentação foram verificados. Comandos na raiz:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_motion_replay.py -v
python scripts/check_docs.py
git diff --check
```

Sem SONAR_E2E_WEIGHTS, somente o teste opcional do detector real fica skipped;
os outros oito não precisam de vídeo/peso ou extras. Para a regressão completa,
usar scripts/run_tests.py e o procedimento de extras/pesos do CI existente.
