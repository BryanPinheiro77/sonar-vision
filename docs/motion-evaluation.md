# Avaliação pareada de movimento aparente — #11

Responsável: Bryan. Data: 2026-10-16. Ferramenta offline, sem mídia ou rede.
[Especificação](experiments/issue-11-motion-spec.md) ·
[trajetória](trajectory.md) · [coleta proposta](experiments/issue-11-coleta.md) ·
[avaliação de detecção/tracking #33](evaluation.md).

## Responsabilidade

Esta ferramenta pertence à frente de modelo/IA e cloud de Bryan e seu trio.
Montagem, firmware e bancada ficam com Mathias, Tarcísio e Weslley, conforme
divisão confirmada por Bryan em 16/10/2026. Avaliar dados no computador não
exige que Bryan implemente captura/drivers ou tenha as placas fisicamente.

## O que a ferramenta resolve

Compara movimentos previstos com anotações humanas alinhadas às mesmas capturas,
reutilizando associação por classe/IoU e diagnósticos de identidade da #33.
Não roda YOLO, treina, captura vídeo, compensa câmera, fala ou comanda hardware.
O contrato da API e o formato v1 da #33 permanecem iguais. O caminho tátil local
continua independente. A #11 só termina após avaliação real e revisão aplicáveis.

## Executar agora, sem vídeo ou extras

Na raiz do checkout, Python >=3.11, biblioteca padrão:

```sh
PYTHONPATH=src python -m sonar_vision.evaluate_motion \
  --snapshot docs/experiments/issue-33-fixture.json \
  --motion docs/experiments/issue-11-motion-fixture.json \
  --output results/issue-11/motion-01.json \
  --review results/issue-11/motion-review-01.json
PYTHONPATH=src python -m unittest tests.test_motion_evaluation -v
```

Usar nome novo ao repetir; não sobrescreve. Outputs só em `results/` do checkout,
modo 0600 nos sistemas que suportam permissões POSIX. O stdout tem só contagens;
erro retorna 2 sem imprimir valores/caminhos da entrada. Revisão guarda IDs
opacos e estado por amostra; manter privada. Nenhum upload automático.

Fixture original sintética, AGPL-3.0-only, vinculada ao snapshot existente da #33:
sete referências visíveis, seis com movimento humano conhecido; dois acertos
de estado, uma abstenção e duas perdas entre as seis. A terceira resposta
conhecida está errada. Um cruzamento tem estado crossing mas sentido oposto;
logo acerto lateral é 0/1. Uma emissão com câmera móvel é controle negativo.
São respostas de cálculo conhecidas, não desempenho de modelo real.

## Preparar dados reais

Antes de olhar previsões, anotar/revisar caixas, classe, identidade local,
visibilidade, segmento e movimento de referência conforme #7. Preservar a
divisão por origem; não transformar vídeos já usados em ajustes em teste novo.
Referências de autoria, permissão, revisão, modelo/configuração e software
ficam no snapshot da #33 e no diário privado. A ferramenta não autentica essas
declarações. Novos vídeos não provocam treino automático.

O sidecar local contém os campos abaixo, **todos obrigatórios**:

| Campo | Regra |
|---|---|
| schema_version | Inteiro 1 |
| snapshot_sha256 | SHA-256 do JSON canônico do snapshot completo, não dos bytes do arquivo |
| trajectory_config | Todos os campos de TrajectoryConfig efetivamente usados, sem novos padrões implícitos |
| frames | Mesma ordem e quantidade de frames do snapshot, incluindo falhas/warmup |
| frame.clip_id / frame_index | Mesmos valores do frame base |
| frame.captured_at_ms | Tempo da captura original, inteiro seguro, crescente por clip |
| frame.camera_motion | fixed/moving/unknown, declaração do contexto usado no processamento |
| frame.references | reference_id, segment_id, movement, lateral_direction; mesmos IDs/ordem de ground_truth |
| frame.predictions | movement, lateral_direction, reason; mesmos índices/quantidade de predictions antes do filtro |

Movimentos: approaching/receding/crossing/stable/unknown. Direção lateral só
para crossing confirmado: left_to_right/right_to_left ou null se não anotada/
inconclusiva. Durante confirmação ainda unknown, não exportar direção candidata
como direção confirmada. Motivos são os enums existentes de Motion, sem texto livre.
ID nulo exige unknown/no_track. Mudança de rótulo humano requer segmento novo;
o mesmo segmento/alvo/clip tem movimento e direção humana constantes.

Timestamp não é obtido do FPS por esta ferramenta. Para arquivo de FPS variável,
usar tempos de apresentação alinhados; no ESP documentar a referência temporal
da captura. Se relógio reiniciar, separar clip/sessão, sem emendar tempos.
Não inferir câmera fixa da caixa, de yaw estável ou para obter mais respostas.

## Adapter para Result interno

`motion_frame_from_result(base_frame, result, camera_motion=..., references=...)`
verifica que o frame da #33 foi construído do mesmo Result: compara predições,
epoch, referências e metadados presentes, não só número de caixas. Copia
captura e movimentos/motivos sem alterar Result ou Result.observation().
O chamador alinha `frame_index` com a captura original, como no adapter da #33;
nem o hash nem esse teste provam alinhamento físico se o produtor fornecer dados
errados ou se capturas distintas tiverem predições idênticas.

Exemplo de composição **em memória**, após inferência e revisão das referências:

```python
from dataclasses import asdict
import hashlib

from sonar_vision.evaluation import canonical, frame_from_result
from sonar_vision.evaluate_motion import motion_frame_from_result

# result, reviewed_boxes, reviewed_motion, camera_context, trajectory_config
# e latency_ms devem vir da rodada/anotação reais, nunca ser inferidos do modelo.
base = frame_from_result("clip01", original_frame_index, result,
                         reviewed_boxes, latency_ms=latency_ms)
paired = motion_frame_from_result(base, result, camera_motion=camera_context,
                                  references=reviewed_motion)
# Montar snapshot conforme #33 e todos os frames pareados antes de calcular hash.
motion_input = {
    "schema_version": 1,
    "snapshot_sha256": hashlib.sha256(canonical(snapshot)).hexdigest(),
    "trajectory_config": asdict(trajectory_config),
    "frames": paired_frames,
}
```

Esse trecho mostra a interface; não é comando completo de captura. Snapshot e
sidecar reais ficam privados, sem caixas/identidades no Git. Sem verdade humana
não há qualidade medida. O journal atual da API e o preview agregado **não**
contêm todos os campos necessários: não fabricar movimento/contexto a partir
deles. Não foi acrescentada exportação automática a esses produtores.

## Leitura das métricas

Matriz: cinco estados humanos × cinco respostas + missed. Referências invisíveis
e warmup ficam separados. Falha, timeout ou predição abaixo do corte da #33
produzem missed quando há referência visível. O início sem histórico permanece
unknown; não é descartado para melhorar o resultado.

- `accuracy_all_known`: acertos de estado / todas as referências humanas conhecidas,
  incluindo perdas e abstenções. Zero denominador é null, nunca 100%.
- `answer_coverage_all_known`: respostas conhecidas / verdades conhecidas.
- `accuracy_when_answered`: condicional às respostas; ler junto da cobertura.
- `lateral_accuracy_all_labeled_crossings`: lado correto / todos os cruzamentos
  com direção humana anotada, incluindo perdas/unknown/lado errado.
- `unknown_truth`: referência humana inconclusiva, fora das taxas conhecidas,
  mas presente na matriz. Não é automaticamente acerto quando a previsão abstém.
- `abstention_reasons`: motivos entre respostas unknown casadas, incluindo as
  de referência unknown. Perdas ficam na matriz, sem inventar motivo do estimador.
- `camera_guard_violations`: predições elegíveis com movimento conhecido quando
  contexto moving/unknown; inclui predições sem referência casada.
- `segments`: número de segmentos com referência visível, com contadores de
  pelo menos uma perda, abstenção, estado errado ou falha lateral nos conhecidos.
  Um segmento pode ter vários problemas; contadores não são categorias exclusivas.
  Falha lateral inclui lado errado, abstido ou perdido, não só sentido inverso.
- `by_condition`: classe, iluminação, cenário e contexto da câmera; grupos
  pequenos não se tornam aprovados por ter taxa alta.

Contagens são por objeto/frame; segmentos não comprovam fontes independentes.
As taxas são ponderadas por amostras, não média de segmentos. Detecção e
diagnósticos de ID usam as regras já descritas na #33; não são HOTA/IDF1.
Não relata TTC, distância, risco, autorização de passagem ou contagem de pessoas.
`acceptance_evaluated` permanece false. O agregado omite IDs, caixas, paths e
metadados livres; revisar privacidade antes de publicar resultados reais.

## Limites e validação

32 MiB por arquivo, 10000 frames e 100 objetos por lista, conforme #33.
Campos extras, hash divergente, frames faltantes/fora de ordem, timestamp
duplicado/regressivo, labels ou configuração inválidos são rejeitados.
Uma falha de disco na escrita pode deixar output parcial; o nome não é
reutilizado automaticamente. Examinar/remover manualmente antes de repetir.

Os testes usam cálculo conhecido, múltiplos alvos, segmentos, abstenção/perda,
controle de câmera, privacidade do agregado, cópia sem mutação, saída CLI e
recusa de paths externos/symlink. Especificação validada com 98/100 e sem erros;
aviso de endpoint HTTP não se aplica à CLI offline. Avaliação real permanece
pendente, junto à revisão de janela, referências e critérios da #7.

[Evidência da verificação em 16/10/2026](experiments/issue-11-motion-results.md):
389 testes passaram, zero falhas/erros/skips, com extras e peso geral confiável.
