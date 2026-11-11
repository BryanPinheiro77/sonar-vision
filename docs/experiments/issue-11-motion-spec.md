# Avaliação pareada de movimento — especificação da ferramenta #11

## Metadata

**Author:** Bryan. **Date:** 2026-10-16. **Status:** especificação de implementação no escopo autorizado da #11; critérios experimentais finais pendentes.
Escopo de implementação autorizado na continuação da #11; este documento
detalha a engenharia da ferramenta offline. Não aprova protocolo/amostra,
limiares finais da #7, desempenho real ou compensação de câmera.

## Contexto

A #11 já fornece movimentos e motivos no Result interno. O preview só agrega
contagens, e o snapshot v1 da #33 não inclui movimento nem tempo de captura.
Comparar contagens não permite distinguir erro, abstenção ou detecção perdida.
Reutilizar a associação geométrica existente evita uma segunda regra de IoU.

## Functional Requirements

- FR-1: MUST validar um snapshot v1 da #33 e um sidecar local vinculado por
  SHA-256 canônico do snapshot completo; frames/objetos não podem ser misturados.
- FR-2: MUST exigir um registro por frame, em mesma ordem, timestamp monotônico
  crescente por clip, contexto fixed/moving/unknown, rótulo humano e segmento por
  reference_id, e saída de movimento por índice da predição original.
- FR-3: MUST associar por classe/IoU com a regra da #33, após filtro de confiança;
  referência visível sem associação conta missed; invisíveis e warmup separados.
- FR-4: MUST registrar matriz de cinco estados humanos contra cinco estados
  previstos mais missed. Unknown humano fica separado de acurácia conhecida;
  unknown previsto é abstenção, não acerto das referências conhecidas.
- FR-5: MUST informar perdas/trocas da #33, erros de direção lateral, motivos de
  abstenção, emissões com câmera não fixa e contagens por segmento/condição.
  Não excluir início sem histórico ou gaps dos denominadores.
- FR-6: MUST oferecer adapter de Result para predições e captura do sidecar,
  verificando correspondência exata com o frame base; referência humana é
  argumento separado, nunca inferida das previsões.
- FR-7: MUST produzir JSON agregado e revisão privada opcional com CLI local.
  O stdout contém somente contagens; não implementar endpoint/upload.

## Non-Functional Requirements

- NFR-1: MUST preservar API/contrato 0.1, formato v1 da #33, parâmetros do
  estimador, caminho tátil e dependências existentes; usar biblioteca padrão.
- NFR-2: MUST aceitar no máximo 32 MiB por arquivo, 10000 frames e 100 objetos
  por frame, conforme snapshot existente; rejeitar campos extras, duplicatas,
  tipos inválidos, NaN/Infinity e desalinhamento antes de publicar resultado.
- NFR-3: MUST restringir outputs a results/ no checkout e não sobrescrever.
  Agregado não inclui IDs de fontes/tracks, caixas, caminhos ou texto livre.
- NFR-4: MUST manter acceptance_evaluated=false; sintético não é acurácia real.

## Acceptance Criteria

### AC-1: (FR-1, FR-2)

Given hash/ordem/referências divergentes, When avaliar,
  Then rejeitar antes de calcular ou escrever métricas.
### AC-2: (FR-3, FR-4)

Given alvo conhecido correto, errado, unknown e perdido,
  When avaliar, Then contar os quatro casos no denominador conhecido.
### AC-3: (FR-4, NFR-4)

Given somente referências unknown ou invisíveis,
  When avaliar, Then retornar taxa conhecida null e contagens separadas.
### AC-4: (FR-3, FR-5)

Given oclusão, duas identidades e troca de ID,
  When avaliar, Then manter diagnóstico da #33 e segmentos separados por alvo.
### AC-5: (FR-5)

Given crossing oposto ou emissão com câmera moving/unknown,
  When avaliar, Then contar erro lateral ou violação do controle de câmera.
### AC-6: (FR-6, NFR-1)

Given Result e frame correspondentes, When exportar,
  Then copiar estados/motivos/tempo sem mudar Result.observation(); divergência
  de frame/predições é rejeitada, inclusive com igual quantidade de objetos.
### AC-7: (FR-7, NFR-2, NFR-3)

Given entrada inválida ou output existente/externo,
  When executar CLI, Then falhar sem sobrescrever nem imprimir valores privados.
### AC-8: (FR-5)

Given segmentos de durações distintas, When relatar,
  Then separar contagem de amostras e segmentos; não usar frames como tomadas.
### AC-9: (NFR-1, NFR-4)

Given fixture sintética, When executar,
  Then usar dados próprios, sem mídia/pesos/rede e sem aceite experimental.

## Edge Cases

- EC-1: Timestamp duplicado/regressivo, objetos faltantes/duplicados, config
  incompleta, movimento/lateral inválidos: rejeitar.
- EC-2: Warmup, referência invisível, timeout e predição filtrada: manter regras
  declaradas; erro/timeout com verdade visível vira missed, não desaparece.
- EC-3: ID nulo: movimento unknown/no_track; não inventar identidade.
- EC-4: Rótulo humano do mesmo segmento muda: rejeitar, usar segmento novo.
- EC-5: Disco, JSON ou path falham: mensagem genérica, sem valores da entrada.

## API Contracts

Sem REST novo. CLI local proposta: `python -m sonar_vision.evaluate_motion
--snapshot arquivo.json --motion sidecar.json --output results/report.json
[--review results/review.json]`. Adapter Python retorna dict sem escrever disco.

```typescript
type Movement = "approaching" | "receding" | "crossing" | "stable" | "unknown";
type Lateral = "left_to_right" | "right_to_left" | null;
interface HumanMotion {
  reference_id: string; segment_id: string; movement: Movement; lateral_direction: Lateral;
}
interface PredictedMotion {
  movement: Movement; lateral_direction: Lateral; reason: string;
}
```

## Data Models

| Modelo/campo | Tipo | Restrição |
|---|---|---|
| Sidecar | objeto | schema_version=1, snapshot_sha256, trajectory_config completo, frames |
| Frame | objeto | clip_id, frame_index, captured_at_ms, camera_motion, references, predictions |
| references | HumanMotion[] | Mesmos IDs/ordem de ground_truth; segmento opaco; estado constante por segmento/alvo/clip |
| predictions | PredictedMotion[] | Mesma ordem/quantidade de predictions original, antes do filtro |
| camera_motion | enum | fixed/moving/unknown; declaração do operador, não medição de IMU |
| captured_at_ms | inteiro | 0..2^53-1, crescente por clip; tempo real da captura, não derivado automaticamente de FPS |
| lateral_direction | enum/null | Só crossing confirmado pode ter sentido; null em crossing significa direção não anotada/inconclusiva |
| reason | enum | Motivos existentes de Motion; não texto arbitrário |

## Out of Scope

- OS-1: Não coletar mídia, anotar automaticamente, rodar detector ou reconstituir movimento
ausente do journal, mudar preview/diagnóstico público, treinar, compensar IMU ou
definir limites de aceite.

- OS-2: Não alterar API ou snapshots existentes. O produtor real terá de alinhar Result/anotação;
hash e validação estrutural não comprovam honestidade ou qualidade da referência.
