# Contrato de eventos semânticos — versão experimental 0.1

- Autor: elaboração assistida por IA a partir das decisões de Bryan.
- Data: 2026-09-13.
- Status: pacote técnico experimental aprovado por Bryan em 2026-09-13;
  detalhamento documental para incorporação por PR. Não validado no hardware.
- Issue: #12. Relacionadas: #5, #6, #9 e #11.
- Decisão associada: [ADR 0003](../decisions/0003-eventos-semanticos.md).

## Contexto

A VM acrescenta informação visual ao protótipo; sensores e ESP32 continuam
responsáveis pelo risco geométrico e vibração independentemente da rede.
Tracking experimental não comprova identidade, distância ou colisão.

Bryan aprovou comportamentos, JSON/HTTPS e limites iniciais abaixo. Os detalhes
de campos e admissão especificam esse pacote para revisão no PR; não representam
implementação existente nem aprovação de desempenho ou segurança pelo grupo.

## Requisitos funcionais confirmados

DEVE/MUST indica obrigação; NÃO DEVE/MUST NOT indica proibição.

- FR-1: a VM DEVE separar observação visual de sugestão de áudio; observar não
  obriga falar. Nenhuma dessas mensagens DEVE alterar risco/TTC ou vibração local.
- FR-2: o ESP32 DEVE verificar validade e prioridade antes de reproduzir áudio.
- FR-3: alerta local urgente DEVE iniciar vibração sem esperar áudio/rede e
  interromper a fala informativa, sem acumular falas antigas para depois.
- FR-4: DEVE haver no máximo uma sugestão pendente além da fala atual. Uma
  atualização pode substituir a pendente, mas não interrompe automaticamente
  a fala atual. Seleção semântica fica na #5.
- FR-5: sugestões DEVEM referenciar a captura de origem e ser descartadas se
  vencidas antes da reprodução; validade não deve começar no recebimento.
- FR-6: mensagens DEVEM ter ID e sessão; duplicatas não geram áudio novamente,
  e respostas de sessões anteriores são rejeitadas.
- FR-7: perda de assistência visual DEVE gerar um aviso sem repetição por
  oscilação. Restabelecimento exige resultados novos e válidos, não só conexão.
  Os avisos respeitam o alerta local e não dependem de resposta da VM.
- FR-8: direção DEVE referir-se aos óculos na captura, não ao deslocamento.
- FR-9: sugestão direcional DEVE ser descartada se houver mudança significativa
  de orientação desde a captura. Sem orientação válida/comparável, NÃO DEVE
  presumir direção correta. Limiar angular ainda será testado.

## Requisitos não funcionais

- NFR-1: fila de sugestões pendentes limitada a 1; falha do parser, áudio ou
  transporte não pode adicionar espera de rede ao caminho tátil.
- NFR-2: os limites do perfil inicial abaixo DEVEM ser configuráveis e
  registrados nos experimentos. Alterações exigem revisão; não aumentar
  validade automaticamente para compensar rede ou inferência lenta.
- NFR-3: resposta DEVE respeitar 16 KiB, 20 objetos e 120 caracteres por texto;
  saturação de recursos locais DEVE rejeitar admissão sem bloquear sensores.
- NFR-4: registrar motivo de descarte e tempos, sem gravar imagens ou dados
  pessoais por padrão. HTTPS DEVE validar certificado e identidade do servidor;
  credencial individual por dispositivo NÃO DEVE entrar no Git ou nos logs.
  ID de sessão não autentica mensagens.

### Perfil experimental inicial aprovado

| Parâmetro | Valor | Regra de fronteira |
|---|---:|---|
| Idade visual máxima | 1000 ms desde captura | idade >= limite: descartar |
| Mudança de orientação | 15 graus | mudança > limite: descartar/interromper fala direcional |
| Timeout da requisição | 2000 ms | inclui conexão, envio e leitura da resposta |
| Ausência de resultados válidos | 3000 ms | intervalo >= limite: indisponível |
| Recuperação | 3 resultados novos válidos consecutivos | duplicatas não contam; erro ou timeout reinicia contagem |
| Cooldown de avisos de disponibilidade | 10000 ms | entre inícios de avisos; reavaliar estado antes de falar |
| Texto por sugestão | 120 caracteres Unicode | contar pontos de código, não bytes UTF-8 |
| Objetos por resposta | 20 | excedente torna resposta inválida |
| Corpo da resposta JSON | 16384 bytes UTF-8 | incluindo envelope; limitar durante leitura |
| Requisições em andamento por dispositivo | 1 | sem fila de imagens antigas |
| Áudios pendentes | 1 além do atual | atualizar sem acumular |

Valores de bancada, não margens de segurança comprovadas. Todos os campos
temporais são inteiros finitos não negativos; validade deve ser positiva.
O limite local de 1000 ms vale também se a VM enviar validade maior.

## Contrato lógico / API Contracts

Notação TypeScript apenas para leitura; serialização JSON UTF-8 sobre HTTPS.
Detalhamento do endpoint para a implementação na #6:

- `POST /v1/inference`, autenticação `Authorization: Bearer <credencial individual>`.
- Corpo `multipart/form-data`: parte `metadata` (application/json) com
  `version`, `session_id`, `frame_id`, `captured_at_ms`; parte `image`
  (image/jpeg) com a captura correspondente. Não enviar imagem antiga após timeout.
- `200 application/json`: `{ "observation": VisualObservation,
  "audio": AudioSuggestion | null }`. Ambos os campos obrigatórios. Validar
  envelope completo; admitir observação antes do áudio. Referências devem coincidir.
- Erro JSON: `{ "error": { "code": string } }`, sem credenciais/imagens.
  Códigos: 400 `invalid_request`, 401 `unauthorized`, 403 `forbidden`,
  413 `payload_too_large`, 415 `unsupported_media_type`, 429 `busy`,
  500 `internal_error`, 503 `unavailable`. Erros não geram áudio visual.
- Em erro, não reproduzir corpo como fala, não reenfileirar a captura, nem
  seguir redirecionamento para outro host com a credencial. Próxima tentativa
  usa captura nova; frequência/backoff e limite de upload serão definidos na #6.

Uma requisição cliente em andamento; timeout encerra a espera e invalida sua
resposta tardia. A #6 deve tratar cancelamento/trabalho remanescente no servidor
sem criar fila de frames por dispositivo (pode responder busy). Sensores e
vibração não aguardam esse ciclo. MQTT permanece opção futura de telemetria,
não requisito deste contrato de inferência.

A credencial deve ser provisionada fora do Git, validada no servidor e passível
de revogação. Falha de certificado/autenticação implica indisponibilidade,
nunca fallback para HTTP ou TLS sem verificação. Provisionamento, armazenamento,
rotação e relógio necessário à validação de certificados pertencem à #6.

```typescript
type Direction = "left" | "center" | "right" | "unknown";
type Movement = "approaching" | "receding" | "crossing" | "stable" | "unknown";
interface Envelope {
  version: "0.1";
  type: "visual_observation" | "audio_suggestion";
  session_id: string;
  message_id: string;
  frame_id: string;
  captured_at_ms: number; // relógio monotônico do ESP32, eco da captura
  valid_for_ms: number;  // desde a captura, não desde a recepção
}
interface VisualObservation extends Envelope {
  type: "visual_observation";
  tracker_epoch: string; // muda quando o tracker reinicia
  objects: Array<{
    track_id: string | null;
    class_name: string;
    confidence: number;
    direction: Direction;
    movement: Movement;
    stair_direction: "up" | "down" | "unknown" | null;
  }>;
}
interface AudioSuggestion extends Envelope {
  type: "audio_suggestion";
  observation_id: string;
  text: string;
  directional: boolean;
}
type LocalDecision =
  | { outcome: "accepted" }
  | { outcome: "discarded"; reason: string };
```

`accepted` significa admissão local, não fala executada nem entrega garantida.
LocalDecision é resultado lógico de teste/log, não um ACK de rede definido.
Erros locais não são falados automaticamente nem enviados como comandos.

## Modelos de dados e restrições

| Campo/entidade | Tipo | Restrição |
|---|---|---|
| version/type | literal | Exatos; versão/tipo desconhecido rejeitado |
| session_id | string | Não vazia; sessão atual criada pelo ESP32 a cada boot |
| message_id | string | Não vazio; único por mensagem na sessão; retransmissão preserva ID e conteúdo |
| frame_id | string | Contador decimal crescente na sessão, gerado pelo ESP32; string evita perda de precisão |
| captured_at_ms | inteiro | Não negativo, seguro na serialização; igual ao registro local |
| valid_for_ms | inteiro | Positivo; limitado também pela política local |
| tracker_epoch/track_id | string/null | Identidade é sessão + epoch + ID; null significa sem tracking, nunca ID zero implícito |
| class_name | string | person, car, motorcycle, bus, bicycle, chair, dining_table, dog, stairs, traffic_light ou unknown; normalização na VM |
| confidence | número | Finito entre 0 e 1; score do detector, não probabilidade de segurança |
| direction/movement | enum | unknown é explícito; campo ausente não equivale a unknown |
| objects | lista | Pode estar vazia; vazio não significa caminho livre |
| observation_id | string | Referência existente da mesma sessão, frame e captura |
| text | string | Não vazia, português, até 120 pontos de código; não autoriza travessia |
| stair_direction | enum/null | up/down/unknown para stairs; null para demais classes; capacidade ainda a implementar |
| directional | boolean | Obrigatório; true para qualquer fala espacial relativa à captura |
| registro de captura local | memória limitada | frame, tempo monotônico, orientação, qualidade e época de referência IMU |

Campos extras e chaves JSON duplicadas são rejeitados nesta versão; extensões
exigem revisão/versionamento. Classe unknown não gera sugestão falada.
traffic_light é extra do escopo, não autoriza travessia nem codifica estado do
sinal nesta versão. dining_table normaliza mesas sem prometer cobertura de todos
os tipos. Confiança é score do detector; filtro/política por classe ficam na #5.

IDs de sessão/mensagem/epoch são strings opacas não vazias. A implementação
deve gerar IDs sem reutilização no seu domínio; reinício do tracker muda epoch.
Limite por ID: 128 bytes UTF-8 (detalhamento de serialização para revisão no PR).
O ESP32 preserva registros referenciados pela requisição atual, fala e pendente;
registros sem referência expiram. Histórico ilimitado não é necessário.

## Validade, ordem e orientação

1. Validar estrutura, versão, sessão e limites antes de qualquer efeito.
2. Localizar frame no registro do ESP32. Timestamp deve coincidir com o registro,
   nunca substituir o relógio local por um timestamp da VM. Frame desconhecido
   ou removido da memória é rejeitado. Descontinuidade do relógio invalida registros.
3. Calcular idade = agora_monotônico - captura_local. Rejeitar idade negativa ou
   idade >= min(valid_for_ms, limite_local). Para áudio, aplicar também a validade
   da observação de origem; a sugestão não pode estendê-la.
4. Rejeitar duplicata; mesmo ID com conteúdo diferente é conflito. Regra:
   guardar IDs até a captura expirar, sem expulsar IDs válidos para aceitar mais
   mensagens; saturação rejeita novas mensagens. Após expiração, checagem de
   idade/registro impede replay sem exigir histórico ilimitado.
5. Áudio sem observação de origem válida é descartado, sem fila de dependências.
   Uma sugestão por observação; referência já consumida não fala de novo.
   Captura anterior à última sugestão admitida não substitui a atual/pendente.
   Ordenação é por captura local, não por relógio da VM; empates/revisões ficam
   limitados pela regra de uma sugestão por observação.
6. Para áudio direcional, comparar orientação local atual com a da captura,
   usando referência IMU consistente. Amostras inválidas, antigas ou mudança
   de referência/calibração tornam a comparação inválida. Comparar rotação
   relativa 3D pela menor separação angular entre orientações (não subtração
   direta de yaw). A #9 deve fornecer amostras com qualidade e referência
   comparáveis; sincronização e calibração serão validadas no hardware.
7. Repetir checagens de idade, orientação e prioridade imediatamente antes da
   reprodução, mesmo que a sugestão tenha sido aceita na chegada. Durante fala
   direcional, vencimento ou mudança >15 graus também interrompe; sem retomada.
   Orientação inválida durante fala direcional também a cancela. A tarefa de
   áudio deve observar essas condições sem espera de rede.

Não depende de sincronização UTC entre VM e ESP32. O timestamp ecoado não é
confiável sozinho: a referência é o registro de captura mantido pelo ESP32.
O mecanismo de captura e envio dessas referências será detalhado na #6.

Ao surgir urgência local: cancelar fala e pendente, rejeitar sugestões
enquanto urgente e, após liberação, admitir apenas sugestões de capturas feitas
depois dela. Sem retomada da frase interrompida. Avisos de disponibilidade
pendentes devem refletir só o estado atual, sem fila histórica de transições.

Disponibilidade: inicialmente não confirmada; após 3000 ms sem resultados
novos/válidos, indisponível. Recuperação exige 3 resultados consecutivos válidos
da sessão atual, com capturas crescentes; erro, timeout ou intervalo >=3000 ms
reinicia contagem. Duplicatas não contam nem renovam o prazo. Resultado vazio
pode provar processamento
ativo, não qualidade visual nem ausência de perigos. Critérios para câmera
ilegível/baixa luz continuam pendentes; heartbeat sozinho não basta.

## Critérios de aceitação / Acceptance Criteria

Critérios para implementação futura, não testes já executados:

- AC-1 (FR-1): Dada observação válida, quando recebida, então registrar objetos
  sem iniciar fala/vibração e sem modificar estado de risco local.
- AC-2 (FR-2, FR-5): Dada sugestão admitida, quando sua idade atingir o limite
  antes de tocar, então descartar com expired, sem iniciar fala.
- AC-3 (FR-3): Dada fala atual e pendente, quando surgir urgência local, então
  iniciar vibração sem espera de rede, cancelar ambas e não retomá-las.
- AC-4 (FR-4, NFR-1): Dada fala atual e pendente, quando chegar atualização
  admissível mais nova, então substituir só a pendente, mantendo capacidade 1.
- AC-5 (FR-6): Dado ID consumido, quando retransmitido, então não falar novamente.
- AC-6 (FR-6): Dado reboot, quando chegar resposta da sessão anterior, então rejeitar.
- AC-7 (FR-7): Dada indisponibilidade confirmada, quando houver pequenas
  oscilações sem completar a recuperação, então não repetir avisos.
- AC-8 (FR-7): Dada conexão restabelecida sem resultados novos válidos, quando
  avaliar disponibilidade, então não anunciar assistência restabelecida.
- AC-9 (FR-8, FR-9): Dada fala direcional, quando orientação exceder o limite
  desde a captura, então descartar, sem reinterpretar como direção da caminhada.
- AC-10 (FR-9): Dada orientação inválida/antiga ou referência reiniciada,
  quando avaliar sugestão direcional, então descartar com orientation_invalid.
- AC-11 (NFR-2, NFR-3): Dado perfil sem limites obrigatórios ou buffers cheios,
  quando admitir mensagens, então rejeitar novas sugestões sem bloquear sensores.
- AC-12 (NFR-4): Dado descarte, quando registrar diagnóstico, então registrar
  motivo e tempos sem anexar imagem, credenciais ou texto pessoal.
- AC-13 (FR-2, FR-5): Dada resposta cujo timestamp não corresponde ao registro,
  quando recebida, então rejeitar sem alterar o relógio local.
- AC-14 (FR-1, FR-2): Dada mensagem com campo obrigatório ausente, confiança
  inválida ou comando tátil extra, quando validada, então rejeitar sem efeitos.
- AC-15 (FR-4): Dada sugestão de captura mais nova admitida, quando chegar uma
  mais antiga, então não substituir a pendente nem reproduzir informação antiga.
- AC-16 (FR-7): Dada recuperação estabilizada com resultados novos válidos,
  quando não houver urgência local, então anunciar restabelecimento uma vez.

## Casos extremos / Edge Cases

- EC-1: mensagem malformada/incompleta → invalid_message; sem defaults silenciosos.
- EC-2: áudio chega antes da observação → missing_observation; descartar.
- EC-3: VM reinicia tracker → epoch novo; mesmo track_id não representa mesmo alvo.
- EC-4: transporte duplica/reordena → deduplicação e checagem de captura; sem fila antiga.
- EC-5: desconexão/timeout → avisos locais estabilizados, vibração independente.
- EC-6: orientação/referência IMU perdida → rejeitar áudio direcional; não declarar
  que toda a percepção local continua válida, pois falhas dos sensores têm política própria.
- EC-7: áudio/TTS falha → diagnóstico e descarte; nunca bloquear caminho tátil.
- EC-8: silêncio ou objects vazio → não inferir caminho livre nem travessia segura.

## Critérios adicionais do pacote aprovado

- AC-17 (FR-2, FR-9): Dada fala direcional em andamento, quando idade atingir
  1000 ms ou mudança superar 15 graus, então interromper sem retomar.
- AC-18 (NFR-3): Dada resposta acima de 16384 bytes, 20 objetos ou texto acima
  de 120 pontos de código, quando recebida, então rejeitar sem efeitos visuais.
- AC-19 (NFR-4): Dado certificado inválido ou credencial rejeitada, quando
  conectar, então falhar sem desabilitar verificação e manter caminho tátil.
- AC-20 (NFR-1): Dada requisição ativa, quando houver nova captura, então não
  iniciar envio paralelo nem criar fila de capturas antigas.
- AC-21 (FR-7): Dado aviso iniciado há menos de 10000 ms, quando estado mudar,
  então não falar novo aviso antes do cooldown e reavaliar estado ao liberá-lo.

## Validação e responsabilidades seguintes

A #12 define o contrato experimental, não comprova seus limites. A #6 implementa
o endpoint, limites do upload, cancelamento, provisionamento TLS/credenciais e
testes de falhas. A #5 define seleção, texto, TTS e carga cognitiva. A #9 valida
qualidade/sincronização IMU e caminho tátil. Não há dependência de LLM para avisos.

Risco de UX explícito: idade máxima de 1 segundo desde captura pode deixar
pouco tempo para falar após a inferência e cortar mensagens direcionais.
Medir conclusão de frases, interrupções e descarte na #5/#6 antes de considerar
uso real; não ampliar limites sem revisão. Avisos locais de disponibilidade
não dependem da idade de uma captura e não usam o limite angular.

### Áudio local e catálogo (#25)

A [interface de áudio local](audio-local.md) detalha, **sem alterar os campos
0.1**, a regra já decidida de que a urgência local interrompe a fala
informativa, limpa a pendente e permite um aviso curto e genérico tocado do
armazenamento local, sem esperar a rede. Também define as prioridades P0/P1/P2,
a validade visual separada do estado local, a resolução de `text` no catálogo
instalado e o comportamento diante de arquivo ausente, catálogo incompatível e
perda de rede. É proposta até a revisão de Bryan e do firmware (#18).

Depois de incorporar a documentação revisada, #12 pode ser encerrada como
contrato experimental definido. Isso não encerra as tarefas acima.

## Fora de escopo / Out of Scope

Implementação de API, firmware, TTS, broker, LLM, transporte de pixels, telemetria
de risco local e comando remoto de atuadores. A #9 define risco local; esta
proposta não transmite nem confirma risco geométrico. Não inclui promessa de
segurança, autorização de travessia ou compensação da direção de caminhada.
