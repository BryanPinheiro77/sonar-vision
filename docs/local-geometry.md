# #9 — especificação do núcleo geométrico local

**Author:** Bryan, com apoio de IA.
**Date:** 2026-10-09.
**Status:** Approved — desenho de simulação e correção documental aprovados por Bryan em 2026-10-09 (resposta “aprovo”). Código candidato aguarda revisão/publicação.
**Reviewers:** Bryan e frente de firmware; revisão de bancada a designar.

## Context — contexto e fontes de verdade

A [#9](https://github.com/BryanPinheiro77/sonar-vision/issues/9) define o núcleo
local de geometria, risco e TTC com entradas simuladas. O
[escopo aprovado](ESCOPO.md), o [ADR 0003](decisions/0003-eventos-semanticos.md)
e o [contrato 0.1](protocol/eventos-semanticos.md) mantêm esse caminho independente
de visão, câmera, VM e internet. O hardware ainda não foi integrado/validado.

Esta entrega especifica tipos, semântica, fronteiras e testes do núcleo C++17,
sem Arduino/FreeRTOS/drivers. O desenho foi aprovado para simulação; a
[implementação candidata e os comandos](../firmware/README.md) realizam os testes
no computador. **Não há aprovação operacional dos parâmetros nem testes físicos.**
Requisitos confirmados vêm das fontes citadas; fórmulas, tipos e convenção de
eixos abaixo foram aprovados somente para esta simulação.

### Correção documental aprovada

A seção Percepção de [ARCHITECTURE.md](ARCHITECTURE.md) apresentava
“refinamento semântico do risco”, divergindo do ADR 0003, da #9 e do AGENTS.md.
Bryan aprovou corrigir o trecho para contexto visual/sugestões de áudio, sem
canal remoto de alteração do risco/TTC/vibração. A correção está registrada no
[ADR 0019](decisions/0019-nucleo-geometrico-local.md); o contrato 0.1 é preservado.

## Functional Requirements — requisitos funcionais

MUST = DEVE; MUST NOT = NÃO DEVE. FR-1/2/8/9/10/13/14 refletem restrições
confirmadas; o detalhamento dos demais requisitos é o desenho técnico aprovado
para simulação, sem aprovação operacional.

- FR-1: o núcleo MUST receber somente ToF, orientação, calibração, relógio local,
  configuração e estado geométrico anterior; MUST NOT receber imagem, classe
  visual, track_id remoto, sugestão de áudio ou status de rede para calcular risco.
- FR-2: uma entrada ToF MUST representar 64 zonas com distância radial em metros,
  qualidade explícita, identificador de aquisição e tempo monotônico de captura.
- FR-3: a projeção MUST usar raio unitário calibrado e transformação ToF→cabeça,
  seguida da orientação cabeça→referência declarada. Sem origem/convenção de
  distância ou calibração válida, a projeção MUST ser indisponível.
- FR-4: a orientação MUST declarar quaternion [w,x,y,z], qualidade, captura e
  referência comparável. Valores não finitos, norma inválida, idade/futuro ou
  dessincronização fora da configuração MUST invalidar direção compensada.
- FR-5: o núcleo MUST classificar pontos observados em esquerda/centro/direita
  pela convenção proposta e fronteiras explícitas; MUST indicar pontos fora
  do volume configurado, sem reinterpretá-los como região livre.
- FR-6: cada setor MUST retornar distância radial mínima observada, origem da
  observação, validade, motivos e cobertura separadamente. Ausência MUST usar
  valor opcional, sem infinito/zero como sentinela de distância ou TTC.
- FR-7: avaliação de proximidade MUST usar parâmetros explícitos. MUST separar
  banda observada e qualidade de cobertura; evidência próxima positiva continua
  visível mesmo com cobertura limitada, sem afirmar que o restante está livre.
- FR-8: falta/invalidez/atraso MUST produzir estado desconhecido/degradado,
  nunca `safe`, `clear` ou ausência de obstáculo por falta de retorno.
- FR-9: relógio regressivo, sessão/referência/calibração nova ou aquisição
  duplicada MUST impedir derivada e mistura de históricos; nova referência
  reinicia o histórico e preserva apenas observações atuais utilizáveis.
- FR-10: aproximação/TTC MUST exigir associação explícita e continuidade local
  válida; mesma zona ou mínimo do setor MUST NOT provar identidade do alvo.
- FR-11: na fixture controlada associada, taxa relativa MUST ser
  `(range_previous_m - range_current_m) / dt_s`. Sem aproximação positiva
  acima do mínimo configurado, TTC MUST permanecer ausente com motivo explícito.
- FR-12: TTC candidato MUST declarar hipótese de alcance radial relativo linear
  até zero (`range/v`). Tempo até proteção MUST ser campo diferente:
  `max(0,(range-protection_range)/v)`. Nenhum dos dois MUST ser rotulado como
  confirmação de colisão física ou convergência à caminhada.
- FR-13: parâmetros de risco MUST NOT ter padrões operacionais inventados.
  Perfil ausente/inválido MUST retornar avaliação não configurada; valores
  de fixture MUST ser rotulados como simulação, sem autorização para firmware.
- FR-14: saídas MUST NOT acionar LRA/voz/drivers. A política de degradação,
  urgência e atuação pertence à #4/#18; a #9 somente entrega evidência local.
- FR-15: todas as saídas numéricas presentes MUST ser finitas e carregarem
  captura/referência/perfil de origem; repetição dos mesmos dados/estado MUST
  produzir o mesmo resultado, independentemente da rede.

## Non-Functional Requirements — requisitos não funcionais

- NFR-1: implementação candidata MUST ser C++17 e usar zero dependências de
  Arduino, FreeRTOS, câmera, API, rede ou modelo de IA no núcleo.
- NFR-2: processamento MUST ser limitado a 64 zonas e três setores por chamada;
  histórico MUST ter no máximo dois registros por zona, sem fila ilimitada.
- NFR-3: função MUST realizar zero chamadas de I/O e zero alocações dinâmicas
  durante atualização; configuração e buffers são fornecidos pelo chamador.
- NFR-4: testes de matemática MUST usar tolerância de fixture explícita
  (exemplo de laboratório: 1e-9 em double), nunca a mesma tolerância como erro
  físico aprovado do sensor. Precisão float no ESP será medida separadamente.
- NFR-5: 100% dos casos AC abaixo MUST ter teste determinístico no computador
  antes de aceite de código. Repetir cada fixture com rede ausente/presente
  MUST produzir resultados iguais; zero resultados NaN/infinito admitidos.
- NFR-6: latência sensor→vibração abaixo de 100 ms é meta inicial da #4, não
  orçamento inventado desta função. WCET/erro/RAM do núcleo no ESP permanecem
  pendentes de perfil aprovado e medição; sem promessa temporal no hardware.

## API Contracts — interface local proposta

Não há endpoint nesta entrega. O `POST /v1/inference` já existente é mencionado
somente para deixar explícito que não integra a interface abaixo nem muda.
Notação TypeScript para leitura; tradução C++17 em arrays/optionals,
sem serialização JSON ou parser novo nesta etapa.

```ts
type UInt64 = bigint; // tradução futura uint64_t; não é JSON/Number
interface Zone {
  index: number;                 // inteiro 0..63
  radial_range_m: number | null; // finito >0 quando utilizável
  quality: "usable" | "missing" | "invalid" | "no_return";
}
interface ToFFrame {
  distance_kind: "radial" | "axial" | "unknown"; // somente radial é compatível
  boot_session: UInt64; acquisition_id: UInt64; captured_at_us: UInt64;
  calibration_id: UInt64;
  zones: Zone[];                 // exatamente 64 índices únicos
}
interface Orientation {
  boot_session: UInt64; captured_at_us: UInt64; reference_id: UInt64;
  quality: "usable" | "missing" | "unreliable";
  head_to_reference_wxyz: number[]; // quatro finitos, norma validada
}
interface FixtureAssociation {
  source: "controlled_fixture_same_point";
  previous_acquisition_id: UInt64;
  links: { current_zone: number; previous_zone: number; point_id: UInt64 }[];
  // até 64 pares de zonas válidos/únicos, ligados ao mesmo ponto físico da fixture
}
interface LocalInput {
  boot_session: UInt64; now_us: UInt64;
  tof: ToFFrame | null; orientation: Orientation | null;
  calibration: Calibration; geometry_profile: GeometryProfile;
  risk_profile: RiskProfile | null;
  association: FixtureAssociation | null; // evidência da fixture, não da VM
}
interface SectorResult {
  sector: "left" | "center" | "right";
  assessment: "known" | "limited" | "unavailable" | "unconfigured";
  // known significa somente conjunto de observações utilizável, nunca área inteira segura
  reasons: string[];
  coverage: { frame_zones: 64; frame_usable: number; frame_invalid: number;
              projected_in_sector: number };
  source_zone: number | null;
  nearest_observed_range_m: number | null;
  observed_band: "outside_thresholds" | "attention" | "urgent" | null;
  closing_rate_m_s: number | null;
  radial_ttc_candidate_s: number | null;
  time_to_protection_s: number | null;
  motion_basis: "controlled_fixture" | "unsupported";
}
interface LocalResult {
  boot_session: UInt64; acquisition_id: UInt64 | null;
  reference_id: UInt64; calibration_id: UInt64;
  geometry_profile_id: UInt64; risk_profile_id: UInt64 | null;
  captured_at_us: UInt64 | null; orientation_at_us: UInt64 | null;
  sectors: SectorResult[]; // exatamente três
}
```

Erro de configuração, amostra ou referência é resultado com motivos/optionals;
MUST NOT lançar avaliação `outside_thresholds` por entrada inválida. Erros de
programação não são evidência de ausência de risco. Não há campo `caminho_livre`. IDs são handles locais uint64, sem strings dinâmicas:
boot/referência/calibração/perfil devem ser não zero; aquisição pode começar em zero.
Frame/orientação de outra sessão ou frame de outra calibração são inválidos;
o chamador não pode reidentificar silenciosamente dados antigos. Uso de handles
no núcleo não altera IDs string do contrato remoto. Adaptador futuro deve tratar
wrap do relógio/contador antes de entregar tempos monotônicos uint64.

### Geometria e fronteiras propostas

- Referencial da simulação: **x à frente, y à esquerda, z para cima**, sistema
  de mão direita. Não define eixos/ordenação físicos do ToF ou IMU.
- `p_head = R_tof_to_head * (range * unit_ray) + translation_tof_to_head`;
  `p_reference = R_head_to_reference * p_head`. Não há posição global ou
  direção de caminhada derivada da IMU. Referência de orientação não mede translação.
- Só pontos com x>0 e altura dentro de `[z_min,z_max]` integram o volume proposto.
  Setor usa `angle=atan2(y,x)`: `angle>alpha` esquerda, `angle<-alpha` direita,
  limites `[-alpha,+alpha]` centro. `0<alpha<pi/2` vem do perfil explícito.
- Quaternion é rotação própria em mão direita; `q` e `-q` são equivalentes.
  Normalizar só dentro da tolerância configurada; fora dela, rejeitar.
- Distância usada em proximidade/derivada é **alcance radial do sensor**, não
  norma do ponto transformado, distância ao corpo ou profundidade axial.
- `age=now-captured`: futuro/regressão invalidam. `age>=max_age` está vencido;
  sincronização é inválida se `abs(t_tof-t_imu)>max_skew`.
- Derivada exige `dt_min<=dt<=dt_max`, mesmo alvo da fixture, mesmo perfil,
  sessão, referência e calibração. Perfil novo também reinicia o histórico.
- Cobertura é contagem de retornos, não área observada: `frame_usable+frame_invalid=64`;
  `projected_in_sector` conta somente pontos válidos efetivamente projetados
  nesse setor. Não atribuir zonas sem distância a um setor presumido; guardar
  a falta de cobertura no quadro completo. Feixes/calibração não comprovam 360°.
- Sem ponto válido no setor, `assessment=unavailable`. Com ponto válido e alguma
  zona inválida no quadro, `limited`. Com os 64 retornos utilizáveis e projeção
  válida, `known` só qualifica os retornos, sem garantia entre feixes. Perfil
  de risco ausente/inválido torna avaliação de risco `unconfigured`, mantendo
  dados/contagens geométricos válidos. Motivos de falha permanecem explícitos.
- `observed_band` deriva apenas do alcance mínimo atual: <=urgent é urgent;
  caso contrário <=attention é attention; acima disso outside_thresholds.
  Sem perfil válido, é ausente. Banda positiva próxima pode existir com
  assessment limitado; outside_thresholds nunca libera as zonas desconhecidas.
- Taxa/TTC do setor só usam a zona `source_zone` da observação mínima atual,
  ligada explicitamente à zona anterior do **mesmo ponto físico** pela fixture.
  Sem esse par, os campos são ausentes mesmo se outro ponto no setor tiver par.
  A associação referencia a aquisição anterior exata; não usar mínimo anterior,
  mesmo ID de objeto, zona coincidente ou tracking visual como substituto.

## Data Models — modelos e parâmetros explícitos

| Entidade/campo | Tipo / unidade | Restrições propostas |
| --- | --- | --- |
| ToFFrame | 64 Zone, IDs uint64, us uint64 | Índices únicos; sessão/calibração devem coincidir com o chamador |
| Calibration.id | uint64 local não zero | Mudança invalida histórico |
| Calibration.unit_rays | 64 vetores | Finitos, unitários na tolerância configurada; sem FoV inventado |
| Calibration.tof_to_head | rotação + translação m | Rotação ortonormal própria; eixos/origem documentados |
| Orientation.reference_id | uint64 local não zero | Comparável, mesma sessão; não significa heading da caminhada |
| GeometryProfile.id | uint64 local não zero | Mudanças invalidam histórico |
| max_tof_age_us, max_imu_age_us | inteiros >0 | Sem padrão; idade igual ao limite vence |
| max_skew_us | inteiro >=0 | Igual ao limite é admitido |
| dt_min_us, dt_max_us | inteiros >0 | dt_min<=dt_max; limites inclusivos |
| center_half_angle_rad | número finito | Entre 0 e pi/2, exclusivo |
| z_min_m, z_max_m | finitos | z_min<=z_max; não definem faixa física sem bancada |
| unit_norm_tolerance | finito, 0<valor<1 | Tolerância matemática configurada; não erro físico |
| RiskProfile.id/stage | uint64 não zero, `fixture` | Nenhum perfil operacional nesta proposta |
| urgent_range_m, attention_range_m | finitos >0 | urgent<attention; igualdade entra na banda mais urgente |
| protection_range_m | finito >=0 | Configuração independente; nome tempo até proteção |
| min_closing_rate_m_s | finito >=0 | Taxa igual ao mínimo não autoriza TTC |
| FixtureAssociation | origem controlada, aquisição anterior, até 64 pares e ID uint64 de ponto | Pares únicos; ponto conhecido da fixture; mesmo objeto/mesma zona não provam ponto |
| State | até 128 registros locais | Nenhum histórico de rede/imagem; reset explícito por mudança |
| SectorResult | três observações limitadas | Optionals ausentes têm motivos; sem valores sentinela |

O adaptador futuro deve documentar quais status reais do VL53L5CX são utilizáveis,
se a medida é radial, ordenação das zonas, FoV, extrínsecos e qualidade do BNO085.
Se distância real for axial ou convenção desconhecida, este perfil é incompatível;
não converter ou adotar outra interpretação silenciosamente.

## Acceptance Criteria — critérios Given/When/Then

Todos os números abaixo são **fixtures artificiais**, sem calibração/limiar de
segurança aprovado. IDs `fixture` não podem promover perfil para dispositivo.

### AC-1: setores e fronteiras (FR-3, FR-5; NFR-4)
Given raios/extrínsecos artificiais e alpha=20 graus; When projetar pontos
(1,1,0), (1,0,0), (1,-1,0); Then obter esquerda/centro/direita. Pontos exatamente
em ±alpha pertencem ao centro; repetir imediatamente dos dois lados da fronteira.

### AC-2: inclinação controlada (FR-3, FR-4; NFR-4)
Given ponto em cabeça (sqrt(3),0,1) m e rotação de 30 graus sobre +y;
When compensar para a referência; Then obter (2,0,0) m dentro da tolerância,
com resultado idêntico para q/-q. Não inferir caminhada ou orientação real da placa.

### AC-3: orientação não utilizável (FR-4, FR-8)
Given orientação ausente, ruim, não finita ou com norma incompatível;
When avaliar; Then direção compensada fica indisponível, com motivo, sem setor válido inventado.

### AC-4: aquisição ausente/inválida (FR-2, FR-6, FR-8)
Given ausência de matriz ou 64 zonas não utilizáveis; When atualizar;
Then três setores indisponíveis, nenhuma distância/TTC e nenhum `safe/clear`.

### AC-5: cobertura parcial com observação próxima (FR-6, FR-7, FR-8)
Given um retorno radial utilizável próximo e 63 zonas inválidas; When avaliar;
Then manter a evidência observada, frame_usable=1, frame_invalid=63,
projected_in_sector=1 e cobertura limitada, sem liberar o restante.

### AC-6: idade e sincronização (FR-4, FR-8)
Given max_age de 100 ms e max_skew de 10 ms, só na fixture;
When usar idades 99/100/101 ms ou skew 10/11 ms; Then admitir idade 99 e skew 10,
invalidar idade>=100 e skew>10, sempre com motivo explícito.

### AC-7: primeira amostra e tempo regressivo (FR-9, FR-10)
Given primeira aquisição, duplicata ou tempo não crescente; When atualizar;
Then não produzir taxa/TTC; duplicata não substitui histórico válido e regressão
invalida a comparação, sem subtração unsigned com underflow.

### AC-8: intervalo temporal e lacuna (FR-9, FR-10)
Given dt_min=10ms e dt_max=100ms só na fixture, com ponto associado;
When usar dt9/10/100/101ms; Then admitir derivada nos limites10/100 e recusar
9/101. Proximidade atual pode continuar válida mesmo quando taxa/TTC ficam ausentes.

### AC-9: aproximação associada artificial (FR-10, FR-11, FR-12)
Given mesmo ponto conhecido da fixture, alcances 3 m e 2 m em 1 s e proteção 0,5 m;
When aplicar hipótese linear; Then taxa 1 m/s, TTC radial candidato 2 s e tempo até
proteção 1,5 s, claramente distintos e válidos só sob as hipóteses declaradas.

### AC-10: afastamento e imobilidade (FR-11, FR-12)
Given ponto da fixture com alcance crescente ou constante; When avaliar;
Then taxa pode ser não positiva, TTC permanece ausente, sem colisão iminente declarada.

### AC-11: troca de superfície sem associação (FR-10)
Given queda do mínimo do setor, mesmo ID de objeto ou retorno da mesma zona
sem o mesmo ponto comprovado;
When atualizar; Then não produzir taxa/TTC de alvo associado.

### AC-12: nova sessão/referência/perfil (FR-9, FR-15)
Given alteração de qualquer ID de continuidade; When atualizar;
Then reiniciar histórico e não misturar os referenciais, preservando observação atual válida.
Dados antigos com sessão/calibração incompatível ficam indisponíveis, mesmo
quando seus timestamps aparentem ser recentes.

### AC-13: parâmetros ausentes ou inválidos (FR-7, FR-13)
Given perfil de risco ausente, NaN ou urgent>=attention; When avaliar;
Then risco fica não configurado/inválido, sem criar limiar padrão; dados
geométricos válidos não viram declaração de caminho livre.

### AC-14: independência local (FR-1, FR-14, FR-15; NFR-1, NFR-3)
Given mesmos ToF/IMU/calibração/perfis/estado; When repetir com câmera, rede e VM
indisponíveis no restante do sistema; Then resultado local é idêntico e não há
I/O, espera externa ou comando para atuador na função.

### AC-15: limites, não finitos e repetibilidade (FR-2, FR-15; NFR-2, NFR-5)
Given 64 zonas com valores ausentes/NaN/infinito/zero/negativos, e índices repetidos;
When validar; Then recusar o frame estruturalmente inválido ou a zona inválida
segundo o motivo, não emitir números não finitos e produzir os mesmos resultados
em repetições de fixture/estado iguais, com buffers limitados.

### AC-16: volume observado (FR-5, FR-6, FR-8)
Given pontos com x<=0 ou fora da altura configurada; When projetar;
Then indicar exclusão/limitação sem declarar região frontal livre. Mudança de
cabeça que retire cobertura frontal não é ausência de obstáculo.

## Edge Cases — falhas e limites

- EC-1: ToF ausente, status desconhecido/no_return, distância zero/negativa/não finita.
- EC-2: quaternion degenerado, orientação atrasada, referência/qualidade desconhecidas.
- EC-3: distância axial apresentada como radial, calibração inválida ou raios não unitários.
- EC-4: tempo futuro, regressão, duplicata, reboot/sessão nova e mudança de perfil.
- EC-5: setor parcialmente observado, cabeça inclinada e pontos fora do volume.
- EC-6: mínimos trocando alvo/superfície; movimento de cabeça sem associação comprovada.
- EC-7: taxa não positiva, abaixo/igual ao mínimo, ou denominador temporal inválido.
- EC-8: risco sem parâmetros; geometria não vira classificação padrão segura.
- EC-9: nenhum driver/rede/arquivo é dependência externa do núcleo; falhas desses
  subsistemas não podem fornecer evidência falsa às entradas normalizadas.

## Out of Scope — exclusões

- OS-1: drivers, pinos, tarefas FreeRTOS, PlatformIO e atuação física; dependem
  de interfaces/componentes e bring-up autorizados nas respectivas issues.
- OS-2: limiares operacionais e margens físicas; exigem aprovação do grupo e bancada.
- OS-3: associação automática de alvo real, direção da caminhada, convergência ou
  posição global da pessoa. TTC da fixture não comprova essas capacidades.
- OS-4: fusão de risco com classes/track_id daVM, mudança do contrato 0.1 ou uso de Edge.
- OS-5: detecção de degraus/buracos pela matriz sem demonstração física, padrão
  de vibração/voz e avaliação com participantes; pertencem às outras frentes.

## Aprovação e execução

Bryan aprovou o desenho de simulação e a correção da arquitetura antes do código.
O núcleo/fixtures C++17 estão em [firmware/](../firmware/README.md), com testes
AC-1 a AC-16 e comandos efetivamente executados. Não há drivers/tasks nem build
para placa. A #9 continua aberta até entrega/revisão e verificação dos critérios.

Detalhes de tradução: `reasons` vira máscara fixa `Reason`; listas viram arrays
limitados, com `count` validado para associações. Ausência de observação tem
precedência `unavailable`; `unconfigured` aplica-se quando há geometria válida
mas falta perfil de risco. Contagens de quadro não validado são 0/64 conservadoras,
não diagnóstico do status bruto do sensor. Pontos excluídos limitam a avaliação
mesmo que outros pontos do quadro sejam utilizáveis. Empates escolhem menor índice.

Estado guarda uma aquisição (64 alcances), instantâneos da calibração/perfis e
relógio local. Além dos IDs, mudanças de conteúdo invalidam continuidade;
parâmetros não podem mudar silenciosamente com ID reutilizado. Frames inválidos
quebram continuidade, duplicatas não substituem alcances válidos, regressões não
viram base de comparação. Taxa explicitamente associada pode existir sem perfil
de risco; TTC e banda permanecem ausentes nesse caso. O resultado inclui os
timestamps de origem. Nenhum código remoto altera risco ou atuação local.

A aprovação não cobre limiares operacionais, calibração real, precisão float,
RAM/WCET no ESP, aquisição física, vibração ou segurança física. Bryan é o
responsável humano pela proposta; revisão da frente de firmware/bancada permanece
pendente, assim como commit/push/PR desta entrega.
