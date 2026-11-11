# 0008 — Interface de áudio local e catálogo instalado (proposta)

- Status: proposta da #25; precisa da revisão de Bryan e da frente de firmware
  (#18), registrada no PR, antes de valer para reprodução física.
- Data: 2026-10-03.
- Responsável: Julio.
- Relacionadas: #25, #5/#31, #9, #12, #18, #32; ADR 0001 e ADR 0003.

> Numeração: 0005 e 0006 aparecem em PRs abertos e 0007 no PR da #24. Esta ADR
> usa 0008 para não colidir; renumerar no merge, se o grupo preferir.

## Contexto

A ADR 0003 decidiu que a urgência local interrompe a fala e não espera a rede,
mas não definiu como os óculos identificam frases, que catálogo precisam ter
instalado, nem como reagem a arquivo ausente, a catálogo incompatível ou à
perda de rede. A #32 propôs o formato do catálogo. A #18 fará a reprodução.

## Decisão proposta

1. Prioridade local: P0 urgência > P1 disponibilidade > P2 sugestão visual.
   A urgência interrompe P1/P2 e limpa a pendente, sem retomada.
2. Aviso urgente falado genérico (`local.urgent`), uma vez por episódio,
   tocado do armazenamento local. A classe só pode ser citada com associação
   validada, nunca pela coincidência de direção.
3. Contrato 0.1 inalterado: o ESP32 resolve `text` por igualdade exata no
   catálogo instalado, com identidade `(catalog_version, id)`. Não há fallback
   remoto. A migração para `phrase_id` fica registrada como opção de uma 0.2.
4. O catálogo só é instalado com `status=released`, perfil idêntico ao do
   firmware, hashes válidos e os três avisos essenciais com áudio. A troca é
   atômica: um pacote rejeitado não remove o catálogo em uso.
5. Perfil candidato WAV PCM 16 kHz mono 16 bits, sujeito à aprovação da #18.
6. Um modelo de referência em Python e exemplos verificáveis servem como
   especificação executável, sem substituir o firmware.

## Alternativas consideradas

- **Adicionar `phrase_id` já na 0.1:** quebraria a regra de rejeitar campos
  extras e exigiria migração coordenada com a VM e a #24 sem necessidade
  demonstrada. O texto exato já é único no catálogo (validador da #32).
- **TTS remoto quando faltar arquivo:** cria dependência de rede justamente nas
  falhas; rejeitado para avisos essenciais e para frases visuais.
- **Aviso urgente com classe e direção do objeto visual:** sem associação
  validada, induziria a atribuir o risco ao objeto errado.
- **Repetir o aviso urgente periodicamente:** soma carga cognitiva à vibração;
  a repetição fica a cargo da vibração da #9.
- **JSON Schema com dependência externa:** a biblioteca padrão e testes
  executáveis atendem ao critério de validação automática.

## Consequências

- A VM pode gerar texto que o aparelho não tem. Ele é descartado e registrado,
  então as versões de frases precisam andar juntas.
- O firmware precisa de troca atômica de catálogo e de espaço para os avisos
  essenciais, mesmo que a lista visual seja reduzida.
- Os textos ("Atenção" etc.) e o perfil de áudio seguem como hipóteses até a
  avaliação supervisionada e a revisão do firmware.
