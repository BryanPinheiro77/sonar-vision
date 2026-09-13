# Contrato de eventos semânticos — rascunho

- Autor: elaboração assistida por IA a partir das decisões de Bryan.
- Data: 2026-09-13.
- Status: Draft; revisão técnica pelos trios de visão/cloud e firmware pendente.
- Issue: #12. Relacionadas: #5, #6, #9 e #11.
- Decisão associada: [ADR 0003](../decisions/0003-eventos-semanticos.md).

## Contexto

A VM acrescenta informação visual ao protótipo; sensores e ESP32 continuam
responsáveis pelo risco geométrico e vibração independentemente da rede.
Tracking experimental não comprova identidade, distância ou colisão.

Bryan confirmou os comportamentos abaixo durante a definição da #12. Os nomes
dos campos, tipos e regras de implementação marcados como proposta ainda não
são escolhas aprovadas pelo grupo. Nenhum endpoint, broker ou codec é criado.

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

## Requisitos não funcionais — propostas

- NFR-1: fila de sugestões pendentes limitada a 1; falha do parser, áudio ou
  transporte não pode adicionar espera de rede ao caminho tátil.
- NFR-2: limites positivos e finitos para idade máxima, mudança angular,
  timeout de assistência, estabilização e cooldown dos avisos DEVEM ser
  configuráveis, aprovados e testados; sem valores padrão definidos aqui.
- NFR-3: limites de bytes, texto, IDs, registros de captura e observações DEVEM
  ser definidos antes da implementação, com teste de saturação e descarte.
- NFR-4: registrar motivo de descarte e tempos, sem gravar imagens ou dados
  pessoais por padrão. Autenticação e proteção do transporte são pendências
  obrigatórias antes de expor serviços; ID de sessão não autentica mensagens.

## Contrato lógico / API Contracts — proposta para revisão

Notação TypeScript apenas para leitura; não fixa linguagem, API HTTP nem
serialização. JSON nos exemplos é uma proposta, não decisão de transporte.

```typescript
type Direction = "left" | "center" | "right" | "unknown";
type Movement = "approaching" | "receding" | "crossing" | "stable" | "unknown";
interface Envelope {
  version: "0.1-draft";
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
O formato de erros de API será escolhido junto com o transporte.

## Modelos de dados e restrições propostas

| Campo/entidade | Tipo | Restrição |
|---|---|---|
| version/type | literal | Exatos; versão/tipo desconhecido rejeitado |
| session_id | string | Não vazia; sessão atual criada pelo ESP32 a cada boot |
| message_id | string | Não vazio; único por mensagem na sessão; retransmissão preserva ID e conteúdo |
| frame_id | string | Não vazio; único na sessão, gerado pelo ESP32 |
| captured_at_ms | inteiro | Não negativo, seguro na serialização; igual ao registro local |
| valid_for_ms | inteiro | Positivo; limitado também pela política local |
| tracker_epoch/track_id | string/null | Identidade é sessão + epoch + ID; null significa sem tracking, nunca ID zero implícito |
| class_name | string | Vocabulário versionado ainda a mapear, incluindo escadas; não implica perigo geométrico |
| confidence | número | Finito entre 0 e 1; score do detector, não probabilidade de segurança |
| direction/movement | enum | unknown é explícito; campo ausente não equivale a unknown |
| objects | lista | Pode estar vazia; vazio não significa caminho livre |
| observation_id | string | Referência existente da mesma sessão, frame e captura |
| text | string | Não vazia, idioma e tamanho a fechar na #5; não autoriza travessia |
| directional | boolean | Obrigatório; true para qualquer fala espacial relativa à captura |
| registro de captura local | memória limitada | frame, tempo monotônico, orientação, qualidade e época de referência IMU |

Proposta conservadora: campos extras também são rejeitados nesta versão de
rascunho; extensões exigem revisão/versionamento. Classe desconhecida não gera
sugestão falada. Vocabulário completo, UUID/contadores e limites de memória
ainda não estão definidos; não implementar presumindo escolhas finais.

## Validade, ordem e orientação — algoritmo proposto

1. Validar estrutura, versão, sessão e limites antes de qualquer efeito.
2. Localizar frame no registro do ESP32. Timestamp deve coincidir com o registro,
   nunca substituir o relógio local por um timestamp da VM. Frame desconhecido
   ou removido da memória é rejeitado. Descontinuidade do relógio invalida registros.
3. Calcular idade = agora_monotônico - captura_local. Rejeitar idade negativa ou
   idade >= min(valid_for_ms, limite_local). Para áudio, aplicar também a validade
   da observação de origem; a sugestão não pode estendê-la.
4. Rejeitar duplicata; mesmo ID com conteúdo diferente é conflito. Proposta:
   guardar IDs até a captura expirar, sem expulsar IDs válidos para aceitar mais
   mensagens; saturação rejeita novas mensagens. Após expiração, checagem de
   idade/registro impede replay sem exigir histórico ilimitado.
5. Áudio sem observação de origem válida é descartado, sem fila de dependências.
   Proposta: uma sugestão por observação; referência já consumida não fala de novo.
   Captura anterior à última sugestão admitida não substitui a atual/pendente.
   Ordenação é por captura local, não por relógio da VM; empates/revisões ficam
   limitados pela regra de uma sugestão por observação.
6. Para áudio direcional, comparar orientação local atual com a da captura,
   usando referência IMU consistente. Amostras inválidas, antigas ou mudança
   de referência/calibração tornam a comparação inválida. Fórmula angular,
   tolerância temporal câmera–IMU e limiares ainda precisam de revisão.
7. Repetir checagens de idade, orientação e prioridade imediatamente antes da
   reprodução, mesmo que a sugestão tenha sido aceita na chegada.

Não depende de sincronização UTC entre VM e ESP32. O timestamp ecoado não é
confiável sozinho: a referência é o registro de captura mantido pelo ESP32.
O mecanismo de captura e envio dessas referências será detalhado na #6.

Proposta ao surgir urgência local: cancelar fala e pendente, rejeitar sugestões
enquanto urgente e, após liberação, admitir apenas sugestões de capturas feitas
depois dela. Sem retomada da frase interrompida. Avisos de disponibilidade
pendentes devem refletir só o estado atual, sem fila histórica de transições.

Disponibilidade proposta: inicialmente não confirmada; ausência de resultados
novos/válidos por timeout indica indisponibilidade. Recuperação exige fluxo
estável por janela configurável. Resultado vazio pode provar processamento
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
  oscilações abaixo da janela de estabilização, então não repetir avisos.
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

## Pendências para aprovação técnica

Formato final (JSON é só exemplo), transporte HTTP/TCP/MQTT, proteção de acesso,
limites temporais/angulares/de memória, vocabulário e confiança por classe,
instrumentação de disponibilidade, orientação/calibração, geração de voz e
política #5. Decidir ainda expiração/mudança de orientação durante fala já iniciada;
por ora só urgência local tem interrupção obrigatória confirmada.

Não promover este rascunho a contrato implementável nem fechar #12 até revisar
essas pendências, exemplos e critérios com as frentes envolvidas.

## Fora de escopo / Out of Scope

Implementação de API, firmware, TTS, broker, LLM, transporte de pixels, telemetria
de risco local e comando remoto de atuadores. A #9 define risco local; esta
proposta não transmite nem confirma risco geométrico. Não inclui promessa de
segurança, autorização de travessia ou compensação da direção de caminhada.
