# Piloto de treino para cadeiras e mesas

**Author:** Bryan.
**Date:** 2026-10-06.
**Status:** Approved — Bryan autorizou a execução da #51 com “segue entao”; aprovação limitada ao piloto, sem adoção do modelo.
**Reviewers:** Bryan; revisão final de qualidade pelo grupo na #7.
**Issue:** [#51](https://github.com/BryanPinheiro77/sonar-vision/issues/51).

## Context

A preparação tem 9 capturas/32 caixas aprovadas de um local antigo (14 cadeiras,
18 mesas) e 8 capturas/16 caixas aprovadas de dois locais novos. Na baseline
YOLOv8n reduzida, local A teve 2/4 cadeiras e 0/4 mesas; local B teve 3/4 cadeiras
e 0/4 mesas. Aumentar a resolução de entrada não recuperou as mesas no diagnóstico.
As referências foram revisadas antes das previsões; oito capturas não estimam
acurácia geral nem confiabilidade do protótipo.

**Objetivo:** executar um primeiro ajuste supervisionado do YOLOv8n para as
classes físicas cadeira/mesa e verificar se recupera mesas em outro local sem
perder a cobertura de cadeira da baseline. Entregar um resultado mensurável,
inclusive se o modelo falhar, com todas as versões, hashes e limites registrados.

**Divisão proposta para este piloto:** antigo = treino (9 capturas/32 caixas);
local A = validação durante treino (4 capturas/8 caixas); local B = comparação
exploratória depois de congelar checkpoint (4 capturas/8 caixas). Isso substitui
expressamente a proposta anterior de excluir A/B de treino e validação: ambos
continuam fora de treino, mas A passa a permitir seleção de checkpoint. O
manifesto antigo e as referências ficam preservados. A divisão só será aplicada
na execução aprovada; não houve alteração silenciosa dos papéis antigos.

Não são necessários mais vídeos para executar este piloto limitado. Negativos,
mais locais de treino e um teste final novo são necessários para ampliar a
avaliação e decidir futura adoção, não gates artificiais do primeiro ensaio.
Os resultados antigos A/B já foram vistos: B não será apresentado como teste
final cego. Nenhuma nova rodada ou ajuste usará B para escolher hiperparâmetros.

## Functional Requirements

- FR-1: O exportador MUST usar somente as caixas aprovadas, as capturas congeladas e os grupos físicos registrados; nenhuma previsão do detector vira label.
- FR-2: O piloto MUST usar antigo/train, A/val, B/evaluation; frames, recortes ou resoluções do mesmo grupo MUST NOT cruzar papéis.
- FR-3: O experimento MUST usar classes internas 0=chair e 1=table, incluindo mesa de escritório; MUST NOT modificar dining_table/Table no contrato/API.
- FR-4: O treino MUST partir do peso YOLOv8n oficial já verificado e executar exatamente uma rodada limitada a 20 épocas, imgsz=640, batch=4, seed=42, device=cpu, workers=0, optimizer=AdamW, lr0=0.001 e patience=20. Registrar augmentations/configurações efetivas da versão fixada; não buscar hiperparâmetros neste piloto.
- FR-5: O checkpoint MUST ser escolhido somente pela validação A, usando best.pt da seleção de fitness da versão instalada; registrar epoch e SHA-256 antes de abrir a comparação B.
- FR-6: A comparação MUST executar baseline e candidato nas mesmas 4 capturas B 270×480, confiança=0.35 e imgsz=640; usar associação uma a uma por classe física, IoU≥0.50, max_cardinality_then_iou da ferramenta #33.
- FR-7: O relatório MUST informar TP/FN por classe/local, previsões de móveis sem associação, classes não alvo separadas, divergências e desfecho atingiu/não atingiu a meta. Não ocultar capturas difíceis nem trocar referências após ver o candidato.
- FR-8: O candidato MUST permanecer experimental offline; nenhuma alteração na API, YOLO geral, escadas, tracking, áudio, limiares geométricos ou caminho tátil local.

## Non-Functional Requirements

- NFR-1: MUST verificar 100% dos hashes das capturas/peso/referências e zero grupos/imagens compartilhados entre train/val/evaluation.
- NFR-2: MUST manter zero mídia, labels brutos, caminhos pessoais ou pesos no Git e zero gasto AWS/GPU paga; arquivos de treino privados/localmente.
- NFR-3: MUST registrar duração, versões, hardware, CPU/RAM e latência média/P50/P95 do detector em CPU, com aquecimento excluído identificado e 100% das falhas contabilizadas; isso não mede HTTPS/ESP32.
- NFR-4: MUST fazer somente uma rodada de até 20 épocas neste piloto. Uma falha não autoriza ciclos de tuning sobre B.
- NFR-5: MUST verificar as conversões de caixas e rejeitar label sem aprovação, caixa inválida, mídia alterada, classe inesperada ou sobreposição de grupos antes do treino.

## Acceptance Criteria

### AC-1: Exportação rastreável (FR-1, FR-2, NFR-1, NFR-5)

Given as capturas e caixas congeladas, When preparar o piloto, Then devem existir
9 capturas/32 labels de treino, 4/8 de validação e 4/8 de avaliação com grupos
físicos disjuntos e hashes verificados; a conversão xyxy→xywh deve voltar às
caixas originais com erro ≤1e-7. Qualquer inconsistência deve bloquear execução.

### AC-2: Rodada reproduzível (FR-3, FR-4, NFR-2, NFR-4)

Given a especificação aprovada, When executar o treino, Then a rodada deve
registrar classes e parâmetros previstos, versões, seed, diretório novo e
resultado/checkpoints sem substituir pesos existentes ou usar recurso pago.
Interrupção/falha também deve gerar registro; não declarar sucesso do treino.

### AC-3: Congelamento antes da comparação (FR-5, FR-6)

Given a rodada terminada, When selecionar best.pt pela validação A, Then
registrar seu hash e epoch antes da comparação B; B não entra em treino,
seleção de checkpoint, early stopping ou decisão de nova rodada.

### AC-4: Meta experimental aprovada do piloto (FR-6, FR-7)

Given as 4 capturas B revisadas, When comparar candidato congelado e baseline,
Then a meta aprovada para esta rodada é **pelo menos 3/4 cadeiras, 2/4 mesas e no máximo uma
previsão extra de cadeira/mesa sem associação** no conjunto de 4 capturas.
A baseline medida tinha 3/4 cadeiras e 0/4 mesas; a intenção é recuperar mesa
sem regressão de cadeira. Informar os números mesmo quando a meta falhar.
Esses limiares são hipóteses deste pequeno piloto, não aceite de produto,
segurança ou estimativa de acurácia populacional. Sem negativos, não medir
confiabilidade de ausência de objetos nem precisão global das outras classes.

### AC-5: Entrega do experimento e preservação do protótipo (FR-7, FR-8, NFR-3)

Given o piloto realizado ou interrompido, When entregar os resultados, Then
documentar atingiu/não atingiu meta, comparação por captura/classe, recursos,
falhas, parâmetros e limitações; confirmar que produção/caminho tátil não mudou.
A entrega do estudo pode estar completa com meta não atingida; isso rejeita o
candidato e não encerra a necessidade de melhorar a visão. Meta atingida apenas
justifica investigar um lote maior; não promove o modelo automaticamente.

## Edge Cases

- EC-1: Captura ausente, alterada ou indecodificável → interromper antes de treino e registrar código fixo; nunca excluir silenciosamente.
- EC-2: Label pendente, classe inválida ou caixa fora de [0,1] → bloquear exportação.
- EC-3: Grupo ou pixels iguais em papéis diferentes → bloquear divisão; imagem transcodificada mantém grupo físico.
- EC-4: Validação vazia ou melhor checkpoint ausente → registrar falha; não escolher checkpoint por B.
- EC-5: Sem detecção de mesa/cadeira → contabilizar FN, não usar unknown como acerto.
- EC-6: Memória insuficiente/interrupção → preservar log/configuração e registrar falha; qualquer mudança de batch/rodada exige registro e decisão antes de retestar B.
- EC-7: Annotation coverage incompleta ou partes de alvo incertas → registrar essa limitação e não alegar certificação de anotação exaustiva. O piloto usa as caixas aprovadas; não inventar caixas/negativos adicionais.
- EC-8: Dependências/peso incompatíveis → bloquear; não atualizar, baixar ou trocar modelo silenciosamente.

## API Contracts

N/A — não há endpoint novo nem alteração de schema público. Contrato local
planejado para artefatos privados, não mensagem do ESP32:

```typescript
interface PilotReport {
  status: "completed" | "failed";
  reference_sha256: string;
  candidate_sha256: string | null;
  target_achieved: boolean | null;
  chair_tp: number;
  table_tp: number;
  unmatched_furniture_predictions: number;
  failures: string[];
  production_changed: false;
}
```

## Data Models

| Entidade | Campo | Tipo | Restrições |
|---|---|---|---|
| Capture | id, group_id | string | Grupo físico preservado em toda derivação |
| Capture | role | enum | train/val/evaluation; exatamente um por grupo |
| Capture | image_sha256 | string | 64 hex; deve corresponder aos bytes congelados |
| Annotation | class_id | integer | 0 chair, 1 table; classes internas |
| Annotation | xyxy | number[4] | Normalizada, 0≤x1<x2≤1, 0≤y1<y2≤1 |
| Annotation | reviewer | string | Aprovação humana registrada antes do uso |
| Run | parameters, versions | object | Configuração efetiva e pacote fixado |
| Run | checkpoint_sha256 | string/null | Congelado antes de evaluation B |
| PilotReport | per_frame, failures | array | Todos os casos preservados; sem mídia em síntese pública |

## Out of Scope

- OS-1: Adoção do modelo em produção ou troca do detector geral: perderia outras classes e precisa de decisão própria.
- OS-2: Novo mapeamento table/dining_table no wire: continua pendente do grupo/ADR.
- OS-3: Teste final de generalização, mAP populacional, tracking/trajectória e uso vestível: amostra minúscula/correlacionada e resultados anteriores já vistos.
- OS-4: Confiabilidade de negativos: nenhum negativo foi fornecido/revisado; coletar na próxima etapa.
- OS-5: AWS, GPU paga, Edge, dependência nova, treino de escadas, alteração de risco/TTC ou feedback local.
- OS-6: Busca de hiperparâmetros e novas rodadas depois de abrir B: requer novo desenho/dados.

## Sources and Decision Record

A divisão por papéis e os alvos numéricos foram elaborados a pedido de Bryan
e aprovados para esta rodada pela confirmação registrada na #51. O ADR 0014
preserva a alteração em relação à reserva anterior de A/B. Essa aprovação não
adota o modelo nem define metas finais da #7. As fontes antigas são preservadas.

Configuração de treino e formatos disponíveis: [Ultralytics train](https://docs.ultralytics.com/modes/train/)
e [dataset de detecção](https://docs.ultralytics.com/datasets/detect/). Aplicar
na versão Ultralytics 8.4.137 instalada; não migrar modelo por mudanças da documentação.

## Resultado da rodada aprovada

Vinte épocas concluídas, checkpoint da época 14 congelado pela validação A.
O candidato teve 0/4 cadeiras e 0/4 mesas no B a confiança 0,35, contra 3/4 e
0/4 da baseline. Candidato rejeitado; produção inalterada. Ver
[relatório e verificação](issue-51-resultado.md). Não houve outra rodada ou
tuning posterior no B.
