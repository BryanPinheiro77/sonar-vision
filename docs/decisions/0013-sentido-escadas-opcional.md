# ADR 0013 — sentido de escadas como segunda etapa opcional

- Data: 2026-09-29.
- Status: proposta experimental da #16; ativação padrão depende de revisão do grupo e #7.
- Responsável pela implementação: Bryan, com apoio de IA.

## Contexto

O contrato 0.1 já prevê `stairs` e `stair_direction=up|down|unknown`. O detector
COCO geral não tem a classe escada; OIV7 detecta `Stairs`, mas não distingue
sentido. O peso local de duas classes treinado na #16 teve 17/20 sentidos
corretos, 1 `unknown`, 2 escadas perdidas e 0/10 falsos positivos no primeiro
teste reservado de 30 imagens. Substituir o detector geral pelo peso de duas
classes removeria as outras categorias da interface.

## Decisão proposta

Permitir um peso opcional `stairs_up/stairs_down` em `UltralyticsFactory`.
Quando configurado explicitamente, o detector principal e seu ByteTrack
continuam inalterados; a segunda etapa acrescenta ou classifica detecções de
escada. `Detection` carrega `stair_direction` validado, e `Result.observation()`
usa esse valor no campo já existente do contrato. Sem segundo peso, escadas
continuam com sentido `unknown`.

Uma caixa especializada casa com uma caixa `stairs` principal se IoU normalizada
for `>= 0.5`, limiar congelado no piloto de imagens da #16. Se houver `up` e
`down` para a mesma escada, o sentido vira `unknown`. Escada encontrada apenas
pela segunda etapa entra sem ID de tracking (`track_id=null`). O limite não é
critério de segurança e deve ser avaliado pelo protocolo da #7 antes de
qualquer ativação padrão.

## Alternativas consideradas

- Trocar o detector principal pelo peso de duas classes: perde pessoas e
  demais classes do contrato.
- Usar somente OIV7: mantém outras classes, mas sempre devolve `unknown` para
  o sentido.
- Fazer a classificação dentro do firmware: contraria a separação entre
  semântica remota e alerta tátil geométrico local.

## Consequências e validação

O segundo peso custa outra inferência por frame. Não há avaliação de latência
ponta a ponta, vídeo ou hardware. A falha da segunda etapa invalida a sessão
visual, conforme a política existente da #21; não afeta o alerta tátil local.
Fotos e pesos não entram no Git. O peso experimental v3 é distribuído como
asset de uma pré-release pública, com origem, licença e SHA-256 documentados em
[`docs/releases.md`](../releases.md). A publicação do peso não o ativa por
padrão nem encerra a validação da #16/#7. O modelo foi exercitado localmente
com YOLOv8n geral e peso v3, preservando as demais detecções; testes sem pesos cobrem
contrato, associação, conflito e ausência de correspondência. A #7 precisa
aprovar condições e limites de aceitação; qualquer ativação padrão requer nova
decisão registrada.
