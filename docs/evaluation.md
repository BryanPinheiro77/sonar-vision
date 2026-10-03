# Avaliação automatizada de visão e latência — #33

- Data: 2026-10-02. Responsável previsto: Matheus (@Matheus-xz), com apoio de IA.
- Status: ferramenta de avaliação e fixtures implementadas; avaliação real pendente.
- Fontes: [issue #33](https://github.com/BryanPinheiro77/sonar-vision/issues/33),
  [protocolo #7](experiments/protocolo-visual.md), [visão #21](vision.md),
  [simulador #30](simulator.md), [contrato 0.1](protocol/eventos-semanticos.md).
- Regras de avaliação: [ADR 0006 proposto](decisions/0006-avaliacao-anotada.md).
  Não constitui aprovação de limiares, amostragem ou segurança pelo grupo.

## Solução e escopo

`src/sonar_vision/evaluation.py` lê um snapshot JSON de resultados e referências,
valida os dados e produz relatório agregado, revisão privada por frame e Markdown.
Usa somente biblioteca padrão Python >=3.11 e unittest, no pacote existente.
Sem dependências, provedor, banco, dashboard, treinamento ou transporte novos.
Não lê imagens/vídeos, executa detector, mede sensores ou modifica áudio/risco/TTC.
O caminho tátil continua independente; validação física/rede desligada permanece
com firmware e #27.

A fixture [issue-33-fixture.json](experiments/issue-33-fixture.json) contém somente
anotações, predições e tempos sintéticos originais, sob AGPL-3.0-only. Não representa
dados coletados nem desempenho de YOLO/ByteTrack. Anotações reais e revisão humana
independente exigidas pela #7 continuam pendentes. Código/licença não relicenciam
vídeos, anotações externas ou pesos; registrar origem/permissões de cada artefato.

## Formato de entrada v1

Estrutura completa reproduzível na fixture; este formato é local de avaliação,
não altera a mensagem 0.1 enviada aos óculos.

| Campo | Conteúdo obrigatório |
|---|---|
| schema_version | 1 |
| run | run_id, code_version, model, configuration, protocol e metadados de latência |
| dataset_manifest | Manifesto v1 da #7, com todos os campos já documentados |
| frames | Lista de amostras anotadas/preditas, ordenadas por frame dentro de cada clip |

Run:
- model: name, version, sha256 (obrigatório para dados reais; null só em sintéticos).
- configuration: detector_confidence, image_size, device (cpu/cuda/mps), tracker_version.
- protocol: iou_threshold em (0,1], association=max_cardinality_then_iou,
  ignore_policy=exclude_invisible_overlap, max_gap_frames,
  minimum_sources_per_group e approval_reference (null enquanto proposta).
- latency_scope: processing, capture_to_response, capture_to_audio ou sensor_to_tactile.
  Nunca misturar escopos numa entrada/comparação.
- latency_clock=single_monotonic_intervals: são intervalos medidos no mesmo
  relógio, não timestamps VM/ESP32 subtraídos. A declaração não prova a medição.
- warmup_excluded=true, model_load_included booleano; elapsed_ms é janela medida
  incluindo falhas, ou null se desconhecida. Não somar latências para inventar FPS.

Frame:
- clip_id referencia clip do manifesto; frame_index inteiro crescente da tomada;
  tracker_epoch identifica reinício; status é ok/timeout/discarded/decode_error/warmup.
- latency_ms é intervalo finito não negativo; obrigatório em ok/timeout/discarded,
  null permitido em decode_error/warmup. Warmup não participa de métricas.
- ground_truth: reference_id (identidade local anotada, sem nome pessoal),
  class_name, box xyxy normalizada na imagem original, visible booleano,
  stair_direction (up/down/unknown em stairs; null nas outras).
- predictions: track_id string ou null, class_name, box normalizada, confidence
  finita em [0,1] e stair_direction. IDs de tracking duplicados no frame são
  rejeitados; null não inventa identidade.
- timeout/discarded/decode_error têm predictions=[]; referências visíveis
  continuam como FN, para não ocultar falha do caminho avaliado. Se a finalidade
  for inferência antes do descarte, exportar esse estágio separadamente e
  registrar escopo coerente. Sem referência anotada não se calcula acurácia.

IDs são opacos com até 128 caracteres ASCII de A-Z/a-z/0-9/underscore/ponto/hífen.
Classes normalizadas seguem contrato; referência deve pertencer às classes
registradas da tomada. Dataset manifest não permite mistura de evidências:
executar separadamente synthetic/recorded, exploratory/controlled/integrated e
exploration/tuning/test/demo. Dados reais exigem hash de pesos e referência de
anotação em todos os clips, além de permissões/revisão ética da #7.
Não inferir aprovação a partir de uma referência textual.

Limites da ferramenta: 32 MiB de JSON, 10000 frames, 256 clips e 100 objetos por
lista/frame; são limites de processamento offline, não limites de hardware.
Campos extras, chaves duplicadas, NaN/Infinity, caixa sem área ou fora de [0,1],
regressão/duplicação de frame, identidade de referência com classe variável,
falha com predições e metadados incompletos são rejeitados.

## Associação, detecção e escadas

Os parâmetros são obrigatórios na entrada: nenhum limiar de risco é introduzido.
A fixture usa IoU=0.50, confidence=0.50, gap=1 e mínimo de duas fontes apenas como
perfil sintético de cálculo. A #7 ainda precisa aprovar valores e critérios finais.

Associação por classe e IoU >= limiar, uma predição por referência e vice-versa.
Hungarian maximiza primeiro a quantidade de associações elegíveis, depois a soma
de IoUs. Isso evita perder um TP por escolher isoladamente a maior IoU. Empates
exatos usam ordem da entrada; preservar essa ordem ao reproduzir resultados.
Predições abaixo de detector_confidence são contadas como filtered_predictions.

Referências invisible são excluídas e contabilizadas. Depois de casar referências
visíveis, predições restantes que coincidam por classe/IoU com uma referência
invisível são contadas como ignored_predictions. As demais continuam como FP.
Esta política de ignore/oclusão é proposta; não é um protocolo MOT aprovado.

TP = associação correta; FN = referência visível não associada; FP = predição
não associada e não ignorada. Duplicatas geram FP. Classe errada gera FN da
verdadeira e FP da predita; associação adicional sem classe dos não casados
fornece diagnóstico de confusão, sem converter erro em TP.
Precision=TP/(TP+FP), recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN).
Denominador zero retorna null no JSON e N/A no Markdown, nunca 100%.
Confiança é score de detector, não precisão medida nem probabilidade de segurança.
Não calcula AP/mAP, curvas de confiança ou acurácia pelo número de deteções.

Escadas: matriz verdade up/down × resposta up/down/unknown/missed.
unknown de resposta é abstenção; missed inclui falha de detecção/classe errada.
Verdade unknown é contada separadamente e excluída do denominador de sentido.
Relata conhecidos, detectados, respondidos, abstenções, corretos, acertos sobre
todas as verdades conhecidas, cobertura de respostas e acertos entre respondidas.
Não tratar abstenção/confusão como acerto nem afirmar borda do primeiro degrau.

## Tracking com referência, sem contagem de pessoas

A associação geométrica anterior vincula predição a reference_id anotado.
Diagnósticos da ferramenta, com regra explícita:
- detection_loss: referência visível sem detecção casada, contado por amostra.
- unassigned: detecção casada sem track_id confirmado.
- id_switch: mesmo alvo anotado, epoch constante, ID casado diferente e diferença
  de frame <= max_gap_frames+1 desde a última atribuição.
- fragmentation: atribuição recuperada após perda/unassigned dentro desse limite.
- continuity_break: intervalo maior que o configurado; inicia segmento novo,
  sem interpolar ou contabilizar troca entre segmentos.
- epoch_reset: epoch mudou no clip; reinicia comparação, não é ID switch.
- identity_transfer: ID passa para referência anotada diferente dentro do limite,
  mantendo epoch; é diagnóstico adicional, não duplicar como uma nova pessoa.

Clips são isolados. Invisibilidade, ausência da referência na amostra ou warmup
quebram continuidade; arquivo de entrada deve anotar todos os alvos avaliáveis,
incluindo oclusão explicitamente, para não fabricar continuidade.
Eventos e IDs ficam somente no arquivo --review em results/. Não implementa
IDF1/HOTA/MOTA nem assume equivalência com contadores de ferramentas MOT.
Tracking depende da qualidade da anotação/associação; uma troca de ID pode
também refletir caixas ambíguas. Bryan deve apoiar a revisão desses casos.

## Grupos, latência, comparação e privacidade

Agrupa por classe, iluminação e cenário, mantendo tabelas de classes sem amostras.
Sources conta source_group_id distintos, não recortes/frames como tomadas
independentes. Esse número não comprova independência física. insufficient_sample
usa mínimo declarado; não significa aprovação quando false. Matriz de
aplicabilidade, amostras e limiares de aceitação continuam com #7.
acceptance_evaluated=false sempre: relatório não aprova a entrega acadêmica.

Latência: N, média, P50/P95 nearest-rank e máximo, sem warmup; falhas medidas
participam do agregado. Também fornece latência por iluminação/cenário e por
status, contagens de timeout/descarte/decode_error e células sem medições.
FPS efetivo = frames ok *1000 / elapsed_ms; se janela ausente, null.
Não confundir throughput de sucesso, FPS de vídeo e média de FPS instantâneo.

--baseline avalia uma segunda entrada e calcula diferenças TP/FP/FN e média de
latência somente se manifesto, capturas/referências anotadas, protocolo e
convenções de medição coincidirem. Modelo/configuração de detector podem mudar
como parte da comparação; preservar esses valores nos JSONs. Caso incompatível,
comparable=false, deltas=null e motivo explícito. Não comparar datasets diferentes
como se mudança de modelo explicasse o resultado.

Relatório JSON e eventos por frame são restritos a results/ no workspace atual.
A síntese Markdown é restrita a docs/experiments/ e contém somente contagens,
classes/condições/enums, sem IDs de clips/tracks, caixas, paths, nomes, texto de
áudio ou configurações arbitrárias. Nenhum output existente é sobrescrito.
Resumo no terminal não imprime path privado nem exceção original.
Revisão humana de privacidade é necessária antes de publicar síntese real,
especialmente grupos pequenos; não há upload automático.

Vídeos/anotações brutos: videos/issue-7/ e datasets/issue-7/, ignorados.
Resultados/review locais: results/issue-33/, ignorados. Política de compartilhamento,
retenção e armazenamento externo ainda depende de aprovação da #7; até lá,
manter localmente privado, sem publicar ou escolher provedor. Gitignore não é
controle de acesso. Conferir licenças/permissões de cada origem no diário privado.

## Integração com artefatos atuais

`frame_from_result(clip_id,frame_index,result,ground_truth,latency_ms=...)` extrai
snapshot de Result interno da #21, copiando caixas/classes/score/ID e epoch.
Não altera Result.observation() nem acrescenta caixas ao contrato 0.1.
Caller deve alinhar anotação com a mesma captura original; frame_index é índice
da tomada, não assumir que contador de requisição após seek seja esse índice.
Passar intervalo medido explicitamente, sem substituir por relógio remoto.

Benchmark #21 é resumo de latência sem caixas/anotações; não é entrada de acurácia.
Simulador #30 também não fornece caixas no log: seus intervalos ajudam a
instrumentar captura/resposta, mas não permitem inventar referência ou calcular
TP/FP/FN por si só. API/cliente devem produzir snapshot pareado privado para
avaliação real. Nenhum detector, trajetória #11 ou escada #16 é implementado aqui.

## Execução e testes

PowerShell, na raiz:

```powershell
$env:PYTHONPATH = 'src'
python -B -m sonar_vision.evaluation docs/experiments/issue-33-fixture.json --output results/issue-33/report-01.json --review results/issue-33/review-01.json --summary docs/experiments/issue-33-sintese-local-01.md
python -B -m sonar_vision.evaluation docs/experiments/issue-33-fixture.json --baseline docs/experiments/issue-33-fixture.json --output results/issue-33/comparison-01.json
python -B -m unittest discover -s tests -p test_evaluation.py -v
python -B -m unittest discover -s tests -v
git diff --check
git check-ignore results/issue-33/report-01.json results/issue-33/review-01.json
```

Usar sufixo novo ao repetir; síntese versionada já existente não é sobrescrita.
A síntese de evidência é issue-33-sintese.md; o comando acima cria outra
cópia local com sufixo local-01, permitindo execução em checkout novo.
Para dados reais, preparar JSON no armazenamento privado com pesos/anotações/
fontes/configuração registrados conforme formato, executar em results/ e revisar
resumo antes de versionar. Os comandos não baixam artefatos exclusivos de Bryan.

Resultado esperado da fixture: TP=5, FP=2, FN=2; precision=recall=5/7;
latência N=8, média=285 ms, P50=40 ms, P95=2000 ms; um ID switch, uma
fragmentação e um reset de epoch. Escadas de verdade down: uma confusão up,
uma abstenção unknown e uma não detectada. Nenhum desses tempos é medição real.

## Matriz de aceitação

| Critério #33 | Entrega/evidência | Limite |
|---|---|---|
| Entrada documentada, modelo/configuração/fonte | Snapshot v1, manifesto #7 e validação | Produtores reais devem alinhar anotações/capturas |
| Detecção/latência e confiança distinta | TP/FP/FN, precision/recall/F1, percentis/estados | Sem AP/mAP ou probabilidade de segurança |
| Revisão perdas/trocas com referência | Eventos privados e regras de continuidade | Sem IDF1/HOTA; revisão humana de ambiguidades |
| Classe/iluminação/cenário/escadas | Grupos e matriz de sentido/abstenções | Amostras e aplicabilidade ainda a aprovar |
| Cálculos conhecidos/limitações | Fixture e unittest com solução por força bruta independente | Não é desempenho de modelo real |
| Síntese em docs/experiments, brutos privados | Markdown agregado e outputs sob results/ | Armazenamento externo/revisão pública pendentes |
| Testes próprios/evidências | Comandos e resultados locais na síntese | ByteTrack real pode permanecer skipped |
| Documentação/índice/ADR | Guia, links e ADR 0006 proposta | Revisão dos critérios na #7 antes de avaliação final |
| PR reproduzível | Arquivos próprios e instruções para revisão | Sem commit/push/PR automático |
| Sem segredos/mídia/pesos, origem/licença | Fixture original AGPL; não baixa/publica artefatos | Permissões das fontes reais devem ser verificadas |

No PR, vincular #33, explicar associação ótima e alternativas da ADR, anexar
evidências e limitações. Responsável humano precisa explicar cálculos/testes.
Avaliação real, aprovação do protocolo e integração física não foram realizadas;
não usar os resultados sintéticos como demonstração de segurança ou desempenho.

## Evidência local — 2026-10-02

Windows/PowerShell, Python 3.12.7:
- 27 testes próprios passaram, incluindo associação versus força bruta,
  classes/condições, tracking/oclusão/epoch, escadas, latência/falhas, limites,
  adapter interno #21, privacidade, validação e CLI.
- Suíte completa: 124 testes, 120 aprovados, 4 skipped por dependências opcionais
  do ByteTrack real ausentes; tempo reportado de 11,767 s.
- Execução da fixture e baseline idêntica retornou 0, TP=5, FP=2, FN=2;
  deltas TP/FP/FN=0 e latência média=0 na comparação idêntica.
- Valores de latência/escadas/tracking conferidos contra as respostas conhecidas.
- Outputs/review em results/ confirmados como ignorados; síntese agregada em
  docs/experiments/issue-33-sintese.md, sem IDs de alvos ou caixas.
- git diff --check, verificação de whitespace dos novos arquivos e links locais
  da documentação sem erros.

Dados reais, anotações revisadas, benchmark de desempenho real, sensores/rede,
firmware e aprovação do protocolo não foram validados. Nenhum commit/push/PR
foi realizado nesta entrega.
