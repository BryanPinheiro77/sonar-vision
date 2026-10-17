# Replay local para avaliação de movimento — #11

## Metadata

**Author:** Bryan. **Date:** 2026-10-17. **Status:** implementação no escopo
autorizado, revisão pelo PR pendente; sem aceite experimental.

Escopo: continuação da #11 solicitada por
Bryan após incorporar a preparação. Especificação de engenharia; não aprova
critérios experimentais da #7. Revisão pelo PR desta entrega.

## Contexto

O adapter de Result existe, mas nenhum comando conecta vídeo autorizado,
VisionService e anotações às duas entradas da avaliação. O preview agregado
não basta. A solução será um replay offline explícito, sem alterar o preview,
a API ou o journal do servidor.

## Functional Requirements

- FR-1: MUST ler snapshot v1 e sidecar v1 como templates anotados, com predictions
  vazias e status ok, um único clip e timestamps de apresentação revisados.
  MUST rejeitar template com predições, falhas/warmup ou escopo diferente de processing.
- FR-2: MUST validar hash do vídeo contra manifesto, dimensões de cada frame e
  hash do modelo geral contra run.model.sha256, antes de inferência correspondente.
  O especialista opcional MUST exigir hash explícito e registrar sua configuração.
- FR-3: MUST decodificar sequencialmente até os índices originais solicitados,
  sem seek aproximado, e passar os timestamps fornecidos e contexto de câmera
  ao VisionService. Frames omitidos no template não entram no tracker.
- FR-4: MUST usar frame_from_result e motion_frame_from_result, atualizar tempos
  reais de processamento e hash canônico do sidecar, e validar o par produzido.
  MUST preservar as referências humanas e stair_direction previsto do Result; o
  modelo nunca gera verdade de referência. A correção do adapter #33 afeta só
  exportação de avaliação, sem mudar schema ou observação da API.
- FR-5: MUST escrever bundle privado novo em results/, com snapshot, sidecar e
  proveniência (hashes/configurações completos), sem mídia, upload ou stdout privado.
- FR-6: MUST liberar captura e sessão em sucesso/falha; falha de decode MUST
  abortar sem relatório parcial de qualidade, sem omitir silenciosamente o frame.

## Non-Functional Requirements

- NFR-1: MUST preservar API, contratos existentes, parâmetros de estimador,
  política de áudio e independência tátil. Sem dependência nova ou download de pesos.
- NFR-2: MUST reutilizar limites de 32 MiB/10000 frames/100 objetos e validação
  existente. Output não sobrescreve e arquivos usam 0600/diretório 0700 em POSIX.
- NFR-3: MUST rotular origem sintética como tal; não declarar aceite experimental.
  Templates devem descrever uma única sequência contínua selecionada: não usar
  amostra esparsa de detecção para alegar continuidade em todos os frames do vídeo.

## Acceptance Criteria

### AC-1: (FR-1, NFR-2)

Given template inválido ou com predições, When replay,
  Then rejeitar antes de processar dados.
### AC-2: (FR-2, FR-3)

Given vídeo/modelo diferentes ou resolução divergente,
  When carregar/processar, Then rejeitar sem produzir par avaliável.
### AC-3: (FR-3, FR-4)

Given índices e timestamps irregulares revisados,
  When executar, Then preservar exatamente o alinhamento e anotações e produzir
  entradas aceitas pelo avaliador, com hash canônico correto.
### AC-4: (FR-3, FR-4)

Given câmera moving/unknown, When replay,
  Then preservar abstenção do estimador, sem assumir câmera fixa.
### AC-5: (FR-5, NFR-1)

Given output existente/externo/symlink externo,
  When gravar, Then rejeitar sem sobrescrever; API e observação remota não mudam.
### AC-6: (FR-6)

Given EOF/decode prematuro ou inferência falha,
  When encerrar, Then liberar recursos e não publicar bundle de sucesso.

## Edge Cases

- EC-1: EOF não distingue corrupção do decoder: abortar de forma explícita.
- EC-2: Timestamps duplicados/regressivos são rejeitados. Não derivar tempos de FPS médio.
- EC-3: Rótulos unknown não viram acertos de movimento conhecido. Escadas sem ID mantêm
unknown/no_track. Nenhuma compensação IMU é acrescentada.

## API Contracts

CLI local `python -m sonar_vision.replay_motion --snapshot ... --motion ...
--video ... --weights ... --output results/issue-11/replay-01
[--stair-weights ... --stair-sha256 ...]`.
Saída 0 com contagem de frames; erro 2 genérico. Sem endpoint REST.

```typescript
interface ReplaySuccess { frames: number; acceptance_evaluated: false; }
// Snapshot e sidecar reutilizam os formatos v1 existentes da #33/#11.
```


## Data Models

| Entidade | Formato |
|---|---|
| Template snapshot/sidecar | Formatos v1 existentes, hash canônico válido, predições vazias |
| Bundle | snapshot.json, motion.json, provenance.json |
| Proveniência | Configuração efetiva do factory, hashes de vídeo/pesos, trajetória, versões e limitações |

## Out of Scope

- OS-1: Não coleta dados, revisa consentimento ou substitui anotador. Não mede rede,
captura ESP, áudio ou risco. Não aprova amostras/limiares, troca pesos, treina,
converte journal antigo ou modifica a API. JPEG/upload de AWS não são simulados:
este comando avalia a imagem decodificada original e registra essa diferença.
- OS-2: EOF prematuro exige diagnóstico e nova execução; não é uma execução completa
com cálculo de qualidade ponta a ponta. Apenas frames fornecidos são avaliados.
