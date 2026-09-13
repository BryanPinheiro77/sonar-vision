# ADR 0003: separar observações e sugestões de áudio

- Data: 2026-09-13.
- Status: proposta; comportamentos confirmados por Bryan, contrato técnico
  pendente de revisão do grupo na #12.
- Responsáveis pela revisão: frentes de visão/cloud e firmware, a designar.

## Contexto

O ADR 0001 mantém o risco e o feedback tátil locais. Informações remotas podem
chegar atrasadas, duplicadas ou após movimento da cabeça; não devem ser tratadas
como comandos de segurança.

## Decisão proposta

Separar observação visual de sugestão de áudio. A VM sugere, o ESP32 arbitra
validade, orientação e prioridade. Urgência local interrompe fala e não espera
rede. Uma sugestão pendente no máximo, identidade por mensagem e sessão,
avisos de disponibilidade sem repetição por oscilação. Direções se referem
aos óculos na captura e ficam inválidas após mudança significativa de orientação.

O [contrato em rascunho](../protocol/eventos-semanticos.md) detalha propostas de
campos e testes. Relógio monotônico e registro de captura locais evitam exigir
sincronização UTC para decidir idade. JSON não está aprovado como formato final.

## Alternativas consideradas

- Falar toda detecção ou usar fila ilimitada: acumula informação velha.
- VM comandar vibração: viola independência definida no ADR 0001.
- Validade desde recebimento: ignora tempo de captura, processamento e rede.
- Direção da caminhada: exige estimativa adicional não validada.
- HTTP, TCP e MQTT: decisão adiada; baseline existente não é substituída aqui.

## Consequências

Firmware mantém registros limitados de captura e regras de admissão. VM mantém
referências de origem e não atribui risco local. Sem implementação ou valores
finais nesta decisão. Exemplos são sintéticos; nenhuma imagem é publicada.
