# ADR 0022 — proposta de ensaio dos motores1027 indicados como ERM

- Data: 2026-10-09.
- Status: **proposta para decisão do responsável; não altera a baseline vigente**.
- Responsável pela proposta: Bryan, com apoio de IA; bancada a designar.
- Issue: [#1](https://github.com/BryanPinheiro77/sonar-vision/issues/1).

## Evidência e conflito

A baseline e o [perfil da #4](../protocol/haptic-local.md) preveem dois LRA.
O vendedor dos dois motores comprados como “Vibracall1027 3V” declara9000RPM,
operação2,5–4V,80mA máximo, cabo3cm, diâmetro9mm e altura4mm. RPM indica
rotação, portanto **ERM é a classificação inferida da descrição comercial**.
Não há fabricante/datasheet inequívoco ou caracterização física disponível.
Não presumir LRA pelo formato e não importar parâmetros de outro motor1027.

O DRV2605L suporta ambos os tipos com configuração/calibração próprias:
[fonte primária TI](https://www.ti.com/lit/ds/symlink/drv2605l.pdf). Essa capacidade
não prova desempenho do motor comprado nem valida os limites declarados.

## Proposta concreta

Usar os motores já comprados **como candidatos para bancada ERM**, antes de
exigir nova compra de LRA. Registrar a decisão antes de implementar configuração
ou atuação. Manter dois drivers e seleção de acesso por TCA; preservar geometria,
contrato remoto e independência do caminho tátil local.

Após identificação elétrica/placas/alimentação, preparar configuração ERM por
motor, com limites autorizados e calibração do próprio conjunto. Não usar modo,
efeito ou calibração LRA. Não configurar a tensão máxima do anúncio como padrão
ou declarar80mA como pico de partida medido.

Ensaiar início/parada mecânicos, preempção, repetição, força/conforto de bancada
sem participantes e sincronismo entre lados. Manter a meta principal **<100ms**
sem alterá-la para acomodar o componente. Os pulsos80ms e ciclos300/800/1500ms
da #4 passam a ser hipóteses de comparação para ERM, sem transferência de
validação física (que ainda não existe). Registrar versão/atuador separadamente;
não juntar medições LRA e ERM como equivalentes.

O plano2400tentativas da #4 pode orientar a avaliação completa somente após
preparação e aprovação do perfil específico de execução. Não iniciar milhares
de tentativas sem primeiro conferir viabilidade/limites e repouso do motor.
Resultados de latência, amplitude e compreensão devem fundamentar a escolha final.

## Alternativa

Manter LRA como requisito da primeira bancada e identificar atuadores LRA com
datasheet compatível com alimentação/DRV/montagem. Essa alternativa envolve
componente diferente; não escolher modelo, comprar ou descartar os motores
existentes antes de decisão do grupo e avaliação da necessidade.

## Consequências e limites

Aprovar esta proposta autoriza somente seleção experimental/planejamento dos
candidatos ERM, sujeito às condições elétricas. Não aprova uso vestível,
segurança física, parâmetros de risco, pinagem, alimentação completa ou testes
com pessoas. Atualizar baseline e perfil com a aprovação explícita; até lá,
permanecem LRA previsto e motores ERM candidatos em conflito documentado.
Nenhum driver, configuração de placa, código, atuação ou compra criado nesta ADR.
