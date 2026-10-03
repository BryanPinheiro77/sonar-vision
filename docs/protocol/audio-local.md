# Interface de áudio local e catálogo de vozes — proposta da #25

- Data: 2026-10-03. Responsável: Julio.
- Status: **proposta para revisão**. Não está aprovada para reprodução física
  até registrar no PR a revisão de Bryan e da frente de firmware (#18).
- Issue: #25. Relacionadas: #5/#31 (política), #9 (urgência local), #12
  (contrato 0.1), #18 (arbitragem e reprodução no ESP32), #32 (catálogo).
- Decisão associada: [ADR 0008](../decisions/0008-interface-audio-local.md).
- Exemplos verificáveis: [exemplos-audio-local.json](exemplos-audio-local.json).

O contrato [0.1](eventos-semanticos.md) **não muda**. Este documento detalha o
que acontece nos óculos depois que uma sugestão chega, e o que acontece sem
ela: aviso urgente, avisos de disponibilidade, catálogo instalado e falhas.
Valores numéricos são os do perfil experimental 0.1; nenhum limiar de risco da
#9 é escolhido aqui. Nada disto é limite de segurança comprovado.

Legenda: **[confirmado]** consta no contrato 0.1, na ADR 0003 ou nas issues;
**[proposta]** é sugestão desta issue que depende de revisão.

## 1. Urgência local

- [confirmado] A urgência é decidida localmente pela #9. A vibração começa sem
  esperar áudio, catálogo, rede ou VM. Nenhuma regra deste documento a atrasa.
- [confirmado] A urgência interrompe qualquer fala informativa (visual ou de
  disponibilidade), descarta a sugestão pendente e não retoma nada depois.
- [confirmado] Enquanto a urgência durar, sugestões novas são rejeitadas
  (`urgent_active`). Depois da liberação, só entram sugestões de capturas
  feitas **após** a liberação (`captured_before_urgency_release`).
- [proposta] Aviso falado curto e **genérico**, `local.urgent` ("Atenção",
  texto ainda hipótese de UX da #32), tocado do armazenamento local, **uma vez
  por episódio** de urgência. A histerese que define o fim de um episódio é da
  #9. Se o arquivo não estiver disponível, só se registra diagnóstico
  (`essential_audio_unavailable`); a vibração segue igual.
- [proposta] Não há comando de locomoção ("Pare", "Desvie") no aviso urgente.

### Aviso genérico × detalhe visual

- [confirmado] O aviso urgente **não cita classe nem direção**.
- [proposta] Citar a classe associada ao risco só será permitido quando existir
  uma associação validada entre o alvo geométrico local e um objeto visual
  (mesma captura, região e tempo verificados). Essa associação não existe no
  contrato 0.1 e **nunca** pode ser presumida só porque a direção coincide.
  Até lá, o detalhe visual é só informativo e cai durante a urgência.

## 2. Prioridades, interrupção e repetição

| Prioridade | Origem | Interrompe | Pode ser interrompida por | Repetição |
|---|---|---|---|---|
| P0 urgência | estado local da #9 | P1 e P2 | nada | 1 aviso por episódio [proposta] |
| P1 disponibilidade | estado local estabilizado (#18) | nada; passa à frente da P2 pendente [proposta] | P0 | estado atual, sem repetir por oscilação; 10000 ms entre inícios [confirmado] |
| P2 visual | `audio_suggestion` da VM | nada | P0; vencimento; orientação > 15° ou inválida | 1 pendente além da atual; cooldown e seleção na VM (#5/#31) |

- [confirmado] Existe no máximo **uma** sugestão visual pendente. Uma
  atualização admissível mais nova substitui a pendente (`replaced`) sem
  cortar a fala atual. Uma captura mais antiga que a última admitida não
  substitui (`stale_capture`).
- [proposta] O aviso de disponibilidade espera a fala visual atual terminar.
  Ao começar, fala o estado **atual**. Se o estado voltar ao último anunciado,
  nada é falado. Transições antigas não são reproduzidas.
- [confirmado] Mensagem duplicada não fala de novo (`duplicate`). O mesmo ID
  com conteúdo diferente é conflito (`conflict`).

## 3. Validade: visual × estado local

- **Visual** [confirmado]: idade = agora − captura local (registro do ESP32).
  Descartar se a idade for negativa ou se `idade >= min(valid_for_ms, 1000)`.
  A VM não pode estender o limite local. A checagem é repetida antes de
  começar a tocar e durante a fala: vencimento interrompe (`expired`).
- **Orientação** [confirmado]: só para `directional=true`. Rotação 3D relativa
  desde a captura maior que 15° interrompe (`orientation_changed`). Orientação
  inválida, antiga ou não comparável descarta (`orientation_invalid`). Fala não
  direcional não depende da orientação.
- **Local** [confirmado/proposta]: avisos P0/P1 não têm idade de captura nem
  limite angular. Valem enquanto o estado local que os originou for verdadeiro
  no momento de começar a tocar.

## 4. Identificação de avisos e catálogo

- [proposta] A identidade de uma frase é `(catalog_version, id)`, com IDs
  estáveis do formato da #32 (`local.urgent`, `visual.person.left.unknown.none`…).
- [proposta] **Compatibilidade com o contrato 0.1:** a VM continua enviando só
  `text`. O ESP32 resolve o texto por **igualdade exata** (UTF-8 NFC, sem
  normalizar, sem aproximação) no catálogo instalado. Texto não encontrado é
  descartado (`phrase_not_in_catalog`); frase sem arquivo também é descartada
  (`audio_missing`). **Nunca** há síntese remota nem TTS como alternativa.
- [proposta] VM e óculos devem usar o mesmo `phrase_version` aprovado. Isso é
  verificado na instalação e no teste de bancada, não por mensagem.
- [proposta] **Migração futura (0.2), se aprovada:** adicionar `phrase_id` e
  `catalog_version` à `audio_suggestion` e informar a versão instalada na
  requisição. Isso exige uma nova versão do contrato, aceita em paralelo durante
  a transição, porque a 0.1 rejeita campos extras. Não faz parte desta issue.

### Manifesto exigido pelo dispositivo

Subconjunto do formato da #32 que os óculos verificam ao instalar:

| Campo | Regra no dispositivo |
|---|---|
| `schema_version` | suportado (hoje `1`); senão `schema_unsupported` |
| `catalog_version`, `phrase_version` | não vazios; senão `version_missing` |
| `status` | `released`; `draft` só em bancada (`catalog_not_released`) |
| `profile` | idêntico ao perfil de áudio do firmware; senão `profile_incompatible` |
| `entries[].id/text` | IDs e textos únicos, texto NFC com no máximo 120 caracteres, `text_sha256` correto |
| `entries[].audio` | `null` ou `{path, sha256, size_bytes}` conferidos com o arquivo |
| avisos essenciais | `local.urgent`, `local.visual_unavailable` e `local.visual_restored` presentes **com áudio**; senão `essential_missing` / `essential_audio_missing` |

Origem, direitos e revisão auditiva são exigências de bancada (#32) e não são
conferidos pelo ESP32. O hash detecta divergência, mas não autentica a origem.

### Formato de áudio

- [proposta — depende da #18] Perfil candidato: WAV, PCM, 16000 Hz, mono,
  16 bits, o mesmo das fixtures da #32 e compatível com saída I2S
  (MAX98357A). O firmware deve aprovar ou trocar esse perfil, medir o espaço
  ocupado e o tempo de carga antes do lote final de vozes.

## 5. Falhas

| Situação | Comportamento |
|---|---|
| Catálogo candidato inválido (hash, schema, perfil, aviso essencial ausente) | Rejeitar o pacote inteiro e manter o catálogo em uso (troca atômica) |
| Nenhum catálogo válido instalado | Sem voz; vibração inalterada; diagnóstico a cada aviso essencial |
| Texto sem frase ou frase sem arquivo | Descartar a sugestão; sem fallback remoto |
| Arquivo ilegível na reprodução | Encerrar a fala, registrar o motivo e não repetir; a vibração não muda [proposta] |
| Perda de rede ou VM | Sugestões visuais param; avisos P0/P1 continuam locais; indisponibilidade após 3000 ms [confirmado] |
| Sessão anterior / timestamp divergente | `session_mismatch` / `capture_mismatch` |

**Avisos essenciais precisam estar no armazenamento local antes do uso**: a
instalação é recusada sem eles.

## 6. Verificação

O modelo de referência em `src/sonar_vision_local_audio/` é uma especificação
executável, **não firmware**. Ele reproduz as regras acima com relógio e
orientação simulados. O arquivo de exemplos traz catálogos válidos e inválidos
e 14 cenários com o resultado esperado. Os testes executam todos eles.

```sh
PYTHONPATH=src python -m sonar_vision_local_audio.examples docs/protocol/exemplos-audio-local.json
PYTHONPATH=src python -m unittest discover -s tests -p test_local_audio.py -v
```

Saída esperada do primeiro comando: `catalog_cases=11 scenarios=14 failures=0`.
Não há dependência fora da biblioteca padrão. Os arquivos de áudio dos exemplos
são marcadores de texto (não são WAV) e não podem ser instalados num aparelho.

## 7. Limitações

- Não implementa firmware, TTS, política de seleção (#31) nem urgência (#9).
- A vibração não está no modelo. A independência tátil precisa ser medida em
  hardware (#9/#18).
- O modelo não confere o cabeçalho WAV; isso fica no validador de bancada da
  #32 e no firmware.
- A memória de IDs consumidos não tem limite no modelo. No firmware, ela é
  limitada pela expiração da captura (contrato 0.1, passo 4).
- Textos de aviso continuam hipóteses de UX até a avaliação supervisionada.
