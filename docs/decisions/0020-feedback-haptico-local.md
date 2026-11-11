# ADR 0020 — padrões hápticos e medição da latência local

- Data: 2026-10-09.
- Status: **desenho e perfil experimental de bancada aprovados por Bryan em
  2026-10-09**, com resposta “tenho q aprovar essa proposta? aprovo entao”.
  Implementação/validação física e parâmetros elétricos/limiares permanecem pendentes.
- Responsável pela proposta: Bryan, com apoio de IA; revisão firmware/bancada
  e usabilidade a designar pelo grupo.
- Issue: [#4](https://github.com/BryanPinheiro77/sonar-vision/issues/4).

## Contexto

O escopo e ADR 0003 mantêm alerta imediato local e áudio subordinado à urgência.
A #4 exige padrões simples e protocolo para a meta inicial <100 ms. O núcleo
simulado da #9 fornece evidência; não valida limiares, sensores ou atuação.

## Decisão aprovada para a etapa experimental

Usar canais E/D para direção e cadência para urgência, com amplitude calibrada
constante. Centro e bilateral usam ambos; documentar a ambiguidade e avaliar
compreensão. Introduzir proposta distinta para percepção degradada, sem
interpretar perda de dados/cobertura como caminho livre. Todos os tempos são
parâmetros para comparação de bancada/UX, sem validação ou aprovação operacional.

Medir do estímulo físico observável ao início mecânico do último canal necessário
em relógio comum, incluindo fase do sensor. Separar marcos de leitura/política/
comando e incerteza; comando I2C não é evidência de vibração. Preservar <100 ms,
contando falhas/inconclusivos sem alterar a meta para percentil favorável.
Detalhes, candidatos e repetição: [protocolo da #4](../protocol/haptic-local.md).

Bryan informou a compra de um TCA9548A e confirmou dois DRV2605L, um por LRA,
em 2026-10-09.
Documentar isso como informação de componente existente. Confirmar na #1
variantes dos módulos, ligação, alimentação,
seleção I2C e atraso entre canais. O multiplexador seleciona acesso; amplitude
é comandada ao driver e depende de calibração, não é potência aplicada pelo TCA.
A quantidade dos componentes está confirmada pelo responsável; funcionamento
independente, reprodução conjunta e montagem ainda precisam de validação.
Não definir pinos ou presumir intensidade percebida proporcional à potência.

## Alternativas e consequências

- Codificar distância por amplitude contínua: adia-se pela calibração e
  complexidade; proximidade fica explícita no estado local de origem.
- Um ritmo diferente para cada classe de objeto: rejeitado nesta proposta;
  mistura visão e risco local e amplia vocabulário sem avaliação.
- Medir só software ou comando elétrico: insuficiente para meta de início físico.
- Usar percentil com falhas excluídas como aceite: não representa o requisito
  inicial e esconde tentativas sem resposta.
- Usar câmera/VM/áudio para autorizar vibração: incompatível com arquitetura.

Esta ADR não cria firmware/drivers/tasks, altera contratos, aprova limiares ou
representa medições. O desenho experimental foi aprovado pelo responsável; a execução física
depende de bancada, instrumento, calibração e interfaces. Avaliação com pessoas
exige consentimento, supervisão e exame das exigências éticas institucionais.
