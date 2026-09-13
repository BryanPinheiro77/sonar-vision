# ADR 0003: separar observações e sugestões de áudio

- Data: 2026-09-13.
- Status: decisão experimental aprovada por Bryan em 2026-09-13;
  atualização documental para incorporação por PR na #12.
- Responsáveis pela revisão: frentes de visão/cloud e firmware, a designar.

## Contexto

O ADR 0001 mantém o risco e o feedback tátil locais. Informações remotas podem
chegar atrasadas, duplicadas ou após movimento da cabeça; não devem ser tratadas
como comandos de segurança.

## Decisão

Separar observação visual de sugestão de áudio. A VM sugere, o ESP32 arbitra
validade, orientação e prioridade. Urgência local interrompe fala e não espera
rede. Uma sugestão pendente no máximo, identidade por mensagem e sessão,
avisos de disponibilidade sem repetição por oscilação. Direções se referem
aos óculos na captura e ficam inválidas após mudança significativa de orientação.

O [contrato experimental](../protocol/eventos-semanticos.md) detalha campos,
exemplos e critérios. Relógio monotônico e registro de captura locais evitam
exigir sincronização UTC para decidir idade. JSON sobre HTTPS, resposta com
observação e sugestão opcional, uma requisição ativa e nenhuma fila de imagens
antigas. Credencial individual por dispositivo e certificado validado.

Perfil inicial: validade de 1000 ms desde captura, mudança angular máxima de
15 graus, timeout de requisição de 2000 ms, indisponibilidade após 3000 ms,
recuperação com 3 resultados novos válidos consecutivos, cooldown de 10000 ms
para avisos, texto de 120 caracteres, 20 objetos e resposta de 16 KiB.
Fala direcional é interrompida ao vencer ou ultrapassar o limite angular.
Esses parâmetros são experimentais, não resultados de validação.

## Alternativas consideradas

- Falar toda detecção ou usar fila ilimitada: acumula informação velha.
- VM comandar vibração: viola independência definida no ADR 0001.
- Validade desde recebimento: ignora tempo de captura, processamento e rede.
- Direção da caminhada: exige estimativa adicional não validada.
- TCP cru/MQTT para inferência: não adotados nesta versão. HTTPS mantém
  captura e resposta correlacionadas; MQTT continua opção futura de telemetria.

## Consequências

Firmware mantém registros limitados de captura e regras de admissão. VM mantém
referências de origem e não atribui risco local. Sem implementação nesta decisão.
A validade curta pode interromper frases: medir esse efeito antes de rever o
perfil. Exemplos são sintéticos; nenhuma imagem é publicada.
