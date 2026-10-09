# #4 — perfil experimental de feedback háptico e protocolo de latência local

- Data: 2026-10-09.
- Status: **planejamento e perfil experimental de bancada aprovados por Bryan
  em 2026-10-09**; implementação, montagem e validação física permanecem pendentes.
- Registro: Bryan respondeu “tenho q aprovar essa proposta? aprovo entao” após
  revisar a proposta disponibilizada nos Downloads. O aceite cobre os padrões,
  prioridades e protocolo abaixo para a etapa experimental; não aprova limiares
  de risco, amplitude elétrica, pinos ou validação com participantes.
- Responsável pela proposta: Bryan, com apoio de IA. Revisor de firmware e
  responsável pela bancada/usabilidade: a designar pelo grupo.
- Issue: [#4](https://github.com/BryanPinheiro77/sonar-vision/issues/4).
- Relacionadas: #1 (componentes/interfaces), #9 (evidência geométrica),
  #18 (arbitragem de áudio), #19 (validação integrada).
- Decisão experimental: [ADR 0020](../decisions/0020-feedback-haptico-local.md).
- Perfil legível: [haptic-local-proposal.json](haptic-local-proposal.json).
- Registro em branco: [haptic-latency-template.csv](../experiments/haptic-latency-template.csv).

## 1. Objetivo, requisitos confirmados e hipóteses

**Confirmado pelo [escopo](../ESCOPO.md), ADR 0003 e #4:** a vibração é local,
independente de câmera, internet, VM, catálogo e inferência visual; áudio não
bloqueia sua iniciação. Comunicar direção, proximidade e urgência com dois LRA
previstos. Meta inicial de latência **inferior a 100 ms**, ainda não medida.
Nenhum retorno remoto decide risco, TTC ou atuação.

**Perfil experimental aprovado nesta entrega:** poucos padrões temporais,
prioridades e procedimento reprodutível de bancada. Os tempos e a matriz foram
aceitos para essa etapa; **não são padrões operacionais, calibração ou resultados
validados**. A execução exige interfaces, montagem e parâmetros elétricos/locais
confirmados conforme as condições abaixo.
Não há driver, pino, tarefa, comando de firmware ou acionamento implementado.

A [#9](https://github.com/BryanPinheiro77/sonar-vision/issues/9) entrega setores,
cobertura e alcance observado. Seu [PR #57](https://github.com/BryanPinheiro77/sonar-vision/pull/57)
contém núcleo C++17 simulado, aprovado em revisão, com CI verde e integrado à
main em 2026-10-09. Seus perfis `fixture` não autorizam limiares ou atuação física. O TTC
artificial não deve ser promovido a gatilho operacional de urgência.

## 2. Componentes confirmados e bancada pendente da #1

**Informação confirmada por Bryan em 2026-10-09:** foi comprado um módulo
**TCA9548A** e **dois módulos DRV2605L, um para cada LRA**, conforme resposta
“Dois DRV2605L, um por LRA”. Essa confirmação registra os componentes comprados;
não comprova montagem elétrica, calibração ou funcionamento.
Os canais **E** e **D** são atuadores dos dois lados dos óculos, com posições/
acoplamento a definir; não são pinos nem direção da caminhada.

**Esquema lógico com os componentes informados, um driver por LRA:**

```text
ESP32-S3 ─ I2C ─ TCA9548A ─ ramal E ─ DRV2605L E ─ LRA esquerdo
                          └ ramal D ─ DRV2605L D ─ LRA direito
```

E/D são rótulos lógicos; porta física, pinos, endereço, tensão, pull-ups e
montagem serão conferidos na #1. O TCA9548A seleciona ramais I2C e permite
separar dispositivos com endereço coincidente; **não controla a potência do
LRA**. [Datasheet TI TCA9548A](https://www.ti.com/lit/ds/symlink/tca9548a.pdf).

Cada DRV2605L tem um par diferencial OUT+/OUT− para seu atuador. Em RTP, o
comando de amplitude fica no driver; essa opção de controle existe, mas modo,
limites elétricos e calibração dependem do LRA/montagem. Potência elétrica e
intensidade percebida não devem ser tratadas como uma mesma medida linear.
[Datasheet TI DRV2605L, seções 5 e 8.3.5.3](https://www.ti.com/lit/ds/symlink/drv2605l.pdf).

Para comandos independentes a drivers com mesmo endereço, selecionar somente
o ramal desejado durante a transação. Seleção e acesso devem ser indivisíveis
perante tarefas concorrentes. Selecionar ambos não permite leitura independente.
O driver pode continuar reproduzindo após mudar o ramal I2C: desmarcar um ramal
não é comando para parar seu LRA. Assim, com dois drivers, ambos podem atuar
mesmo que o acesso seja sequencial; **não prometer início simultâneo** sem medir
o atraso E/D. Esta é inferência da combinação do switch e do playback da TI.

Não ligar um LRA a cada terminal OUT de um único driver. Cada LRA usa o par
diferencial do seu próprio DRV2605L. Não alterar topologia ou comprar componentes
silenciosamente. Registrar variantes dos módulos, alimentação, parâmetros/
calibração de cada LRA, capacidade de reprodução conjunta e medição de sincronismo
na #1; pinos, portas do multiplexador e pull-ups continuam não definidos.

Para a proposta inicial, a amplitude continua constante após calibração;
codificar proximidade pela força seria uma alternativa de UX ainda a avaliar,
não uma alteração automática motivada pela capacidade do driver. Sem canais
funcionais e calibração, o perfil físico continua pendente de validação.

## 3. Vocabulário candidato

### Direção

| Evidência geométrica local atual | Canal proposto | Significado a ensinar |
| --- | --- | --- |
| Esquerda observada | E | Evidência à esquerda dos óculos |
| Direita observada | D | Evidência à direita dos óculos |
| Centro observado | E e D, mesmo pulso | Evidência frontal, relativa aos óculos |
| Esquerda e direita simultâneas | E e D, mesmo pulso | Evidência bilateral; pode ser indistinguível de frontal |
| Direção indisponível | Nenhum setor inventado | Usar o estado de percepção degradada abaixo |

**Ambiguidade explicitada:** dois atuadores simultâneos não distinguem centro
isolado de dois obstáculos laterais. A mensagem tátil conjunta significa
“frontal ou bilateral”; registrar os setores originais na telemetria local.
Não vender o padrão como identificação perfeita de três situações diferentes.
Avaliar essa ambiguidade antes de aprovar o uso; um código temporal adicional
para bilateral seria outra proposta, não está implementado aqui.

### Proximidade e urgência

Proximidade é a evidência local (alcance/banda/cobertura) de origem. Urgência é
o nível escolhido pela futura política local aprovada, e determina prioridade
mais cadência. Não usar intensidade como distância contínua nesta primeira
proposta: fixar amplitude por atuador na calibração de bancada, com limites do
LRA/driver, e registrar o valor. **Nenhuma tensão, amplitude ou limiar de risco
é escolhido neste documento.** Ausência de pulso não significa caminho livre.

| Estado candidato | Pulso ativo | Período entre inícios | Pausa no ciclo | Interpretação |
| --- | ---: | ---: | ---: | --- |
| Atenção local válida | 80 ms | 800 ms | 720 ms | Evidência que exige atenção |
| Urgência local válida | 80 ms | 300 ms | 220 ms | Maior prioridade e repetição |
| Percepção degradada, sem urgência válida | Dois pulsos de 80 ms, separados por 120 ms | 1500 ms | 1220 ms após o segundo pulso | Percepção local indisponível/incompleta; não informa obstáculo frontal |

Todos esses tempos são **parâmetros experimentais aprovados para bancada**, sem comprovação de
perceptibilidade, conforto ou adequação. Os 80 ms são duração do pulso, **não
espera antes de iniciá-lo** nem orçamento de latência. A latência de início
é medida separadamente. Nenhum padrão é comando de locomoção (“desvie/pare”).

## 4. Arbitragem, cobertura e falhas — proposta

1. A cada atualização local utilizável, iniciar ou atualizar o padrão adequado
   sem esperar fase final do ciclo anterior, áudio, rede, disco ou resposta visual.
   Uma nova urgência preempta atenção/degradação; não entra em fila de efeitos antigos.
2. Com setores em diferentes níveis, prioridade global: **urgência válida >
   percepção degradada > atenção válida**. Durante urgência, tocar os setores
   atualmente urgentes; conservar cobertura/motivos no registro. Isso não afirma
   que outros setores estão livres e pode suprimir um alerta lateral de atenção.
3. Sem urgência, se houver falta/invalidez/atraso ou cobertura incompleta que
   impeça avaliar os setores, sinalizar degradação em ambos os canais disponíveis;
   não transformar `unavailable`, `unconfigured` ou `limited` em ausência de risco.
   A degradação não codifica direção; registrar eventual proximidade positiva.
4. Uma observação válida urgente continua positiva mesmo em quadro parcial;
   degradação não a apaga nem atrasa. Sem urgência e com percepção configurada/
   utilizável, atenção usa os setores com evidência atual de atenção.
5. Perda de orientação ou mudança de referência invalida direção compensada.
   Nova sessão/relógio/calibração/perfil inválido exige percepção degradada.
   Limites de idade, histerese, liberação de urgência e perfil de risco precisam
   de especificação/aprovação local; não copiar os 15° ou timeouts da API/áudio.
6. Um estado urgente anterior não prova obstáculo atual após perda de amostras.
   Sem evidência válida, registrar a perda e mudar para degradação, sem indicar
   “risco acabou”. A política de retenção/liberação e usabilidade dessa transição
   permanece candidata a revisão; não implementar uma retenção sem prazo.
7. Urgência informa a arbitragem de áudio local e interrompe fala informativa,
   conforme [ADR 0003](../decisions/0003-eventos-semanticos.md) e
   [interface de áudio](audio-local.md). A vibração não espera a interrupção.
   Esta entrega não adiciona frases/IDs ao catálogo nem modifica contrato 0.1.
8. Atuador/driver com falha não comprova alerta entregue. Registrar erro local,
   parar o canal defeituoso segundo orientação elétrica aprovada e indicar
   indisponibilidade aos operadores de bancada. Não trocar E por D e apresentar
   o outro lado como correto. Sem dois canais funcionais, o perfil direcional
   completo não é validado; nenhum recurso remoto é pré-requisito de diagnóstico.

Estas regras foram aprovadas como desenho experimental, especialmente
para comparar degradação e interrupção em bancada. A #9 produz evidência;
sua banda de fixture não é autorização de atuação. Implementar a integração
física só após especificar/aprovar limiares e interfaces elétricas aplicáveis.

## 5. O que medir e quais relógios usar

Para a proposta de aceite físico, medir no conjunto montado, com alvo de bancada
controlado e sem participante caminhando. Um gatilho externo marca a mudança
física conhecida de cena que requer a resposta, sob geometria e perfil aprovados.

| Marco | Definição | Uso |
| --- | --- | --- |
| `t_scene` | Gatilho externo da mudança física na cobertura aprovada, com referência de posição/instante verificável | Início principal, inclui fase do ciclo do sensor |
| `t_ready` | Disponibilidade do resultado ToF, se observável com instrumento; se for polling, registrar como `t_poll` | Decomposição; polling não é início físico da aquisição |
| `t_read_done` | Resultado ToF/IMU normalizado disponível no ESP | Leitura e preparação |
| `t_decision` | Política local identifica estado/canais desta aquisição | Decisão local |
| `t_command` | Primeiro comando de início enviado ao driver selecionado | Somente marco elétrico/software |
| `t_vibe_E`, `t_vibe_D` | Início mecânico detectado independentemente em cada LRA selecionado | Fim físico da resposta |

**Métrica principal proposta:**
`L_scene_to_vibe_ms = (max(t_vibe dos canais selecionados) - t_scene) / 1000`.
Para E ou D, usar seu canal; para ambos, usar o mais tardio e também registrar
separadamente os dois. O atraso entre canais deve ser registrado; seu limite
perceptivo aceitável ainda não foi aprovado.

**Meta inicial confirmada:** `<100 ms`. **Refinamento de medição proposto:**
verificar essa meta por tentativa na métrica acima, incluindo sensor e início
mecânico. Registrar mediana, P95, P99 amostral, máximo, tentativas sem resposta,
falhas e incerteza. Não revisar a meta para P95<100 ms silenciosamente.

`L_ready_to_vibe`, leitura, cálculo, agendamento e driver→movimento são métricas
auxiliares; nunca substituem a principal. O código da ST distingue verificar
resultado pronto de obter dados: [driver oficial VL53L5CX](https://github.com/STMicroelectronics/stm32-vl53l5cx/blob/main/vl53l5cx.c).
Logo, iniciar a medição só após leitura omite a aquisição/fase do sensor;
essa conclusão é uma inferência do caminho de medição, não resultado de bancada.

- Usar um relógio comum de instrumento para `t_scene` e sinais mecânicos.
  Para marcos ESP, registrar marcador capturado pelo mesmo instrumento ou
  correlação/erro medidos entre relógios. Não subtrair UTC/host/VM/ESP sem isso.
- Timestamp de comando I2C, biblioteca “effect started”, corrente ou tensão
  não comprova início mecânico. Medição principal exige instrumentação mecânica
  adequada disponível na bancada; não exige adicionar um sensor ao produto.
- Registrar instrumento, resolução temporal, taxa, banda, montagem, método de
  detecção e incerteza. Proposta de resolução temporal: até 1 ms; erro total
  deve ser medido e reportado, não presumido pela taxa de amostragem.
- Preparar limiar de detecção mecânica a partir de repouso e resposta conhecida
  de **cada** atuador/montagem, antes de rodadas. Registrar unidades e margem
  sobre ruído, janela/filtro e critério de persistência; congelar o método antes
  de analisar latências. Não reajustar o limiar para salvar um resultado >100 ms.
- Instrumento não disponível: registrar **medição física pendente**. Logs
  simulados/software não demonstram esta meta. LRA deve partir de repouso para
  teste de início; preempção/repetição com LRA já ativo têm ensaio separado.

## 6. Matriz, repetições e procedimento candidatos

**Proposta para avaliação inicial de bancada:** 100 tentativas programadas por
célula; 3 direções × 2 níveis × 4 condições = **2400 tentativas**, além de 10
preparações por célula, registradas separadamente. Não descartar falhas e repetir
até obter “100 boas”. Quantidade/matriz aprovadas para planejamento experimental;
execução condicionada à montagem, instrumentação e parâmetros de bancada.

| Condição | Configuração a registrar | Verificação |
| --- | --- | --- |
| C0 | Caminho visual disponível em simulador/serviço autorizado; LRA inicialmente em repouso | Referência |
| C1 | Rede dos óculos desconectada | Resposta local inicia normalmente |
| C2 | Rede disponível, serviço visual inacessível | Resposta local não espera timeout |
| C3 | Câmera/transporte de teste e fala local ativos; provocar urgência local | Preempção e ausência de bloqueio sob carga |

C3 para atenção mede concorrência com áudio/mídia; para urgência também mede
interrupção. Não há autorização para novos recursos AWS; usar bancada/local ou
infra já autorizada quando disponível. Não presumir C0/C3 prontos sem #17/#18.

1. Confirmar componentes/canais/montagem e seleção do multiplexador (#1), parâmetros locais e perfil de
   bancada autorizados, instrumento/método, software/build e responsável.
2. Congelar perfil de risco, duração/cadência/amplitude, configuração/calibração
   ToF/IMU, multiplexador e drivers, método de início mecânico e critérios antes das rodadas.
   Incluir repositório/commit, versões, modelo/ID de cada componente e condição
   de alimentação; não publicar identificadores pessoais/credenciais.
3. Executar teste em repouso sem estímulo para ruído/falsos inícios e preparar
   10 tentativas por célula; guardar essas evidências fora dos 100 ensaios.
4. Medir período efetivo do sensor e distribuir as 100 tentativas da célula
   por 10 fases desse ciclo, 10 por fase, com ordem alternada/documentada.
   Se a fase não for controlável, registrar essa limitação em vez de afirmar
   cobertura de pior fase. Uma cena não é reiniciada até o LRA retornar ao repouso.
5. Por tentativa, capturar marcos, canais/estado, cobertura, latências, resultados
   mecânicos, falhas e incerteza. Não usar a data de recepção como aquisição.
6. Qualquer latência observada `>=100 ms` viola a meta inicial nessa tentativa.
   Ausência de vibração/canal necessário, marcador perdido ou timestamp não
   comparável não é sucesso nem latência zero: resultado falha/inconclusivo,
   com motivo e denominador de todas as tentativas planejadas.
7. Se intervalo de incerteza alcançar 100 ms, marcar inconclusivo para a meta.
   Resumo deve contar todos os casos; não emitir aceite global enquanto houver
   falha/inconclusivo nas células exigidas. P99 amostral não garante cauda futura.
8. Para liberação de estímulo, troca de setor e preempção do padrão de atenção/
   degradação por urgência, planejar 30 repetições por cenário/condição aplicável,
   em bloco separado. Registrar tempos de troca, término e preempção; limites
   adicionais de liberação, sincronismo e repetição são pendentes, sem inventar
   metas novas nesta entrega. Inicio urgente segue a meta principal onde houver
   novo estímulo físico observável.
9. Relatar preparação, tentativas válidas, falhas e inconclusivos separadamente;
   congelar nova versão se mudar configuração, sem juntar medições não comparáveis.

Não foram executadas essas 2400 tentativas nem os ensaios suplementares. Repetição
proposta não demonstra confiabilidade geral ou segurança física.

## 7. Registro de dados e resumo

O [CSV em branco](../experiments/haptic-latency-template.csv) não tem resultados
fabricados. Preencher uma linha por tentativa, incluindo falhas; tempos em us
monotônicos do domínio identificado. Para dados ausentes, campo vazio com motivo,
nunca 0 como resultado. Tempo 0 legítimo exige domínio/origem registrados.

- IDs: rodada, célula, tentativa, fase e versão dos perfis; setor/urgência/canais.
- Configuração: commit/build, calibração, configuração do sensor/IMU/multiplexador/drivers,
  montagem, amplitude, condição de rede/mídia e referência do instrumento.
- Marcos principais: `scene_us`, `vibe_left_us`, `vibe_right_us`; auxiliares
  somente se tiverem correlação conhecida. `ready_kind` distingue pronto/poll.
- Resultados: latência principal, incerteza, resultado (`pass`, `fail`,
  `inconclusive`), motivo, estado/cobertura e canais realmente observados.
- Resumo por célula: planejadas/executadas/preparação, sucessos/falhas/
  inconclusivos, mediana/P95/P99/máximo, método de quantil e sincronismo.
  Percentis apenas de latências observáveis, com denominador e falhas ao lado;
  não apagar falhas do aceite. Para a proposta, usar quantil por ordem
  `ceil(p*n)` sobre amostra ordenada, indicando n e ausência se n=0.

## 8. Compreensão, conforto e hipóteses a avaliar

Após bancada e autorização ética/consentimento/supervisão aplicáveis, avaliar
se a pessoa distingue E/D/frontal-ou-bilateral, atenção/urgência e degradação;
registrar confusões, incompreensão, conforto/fadiga e percepção do sincronismo.
Não executar testes caminhando, em escadas ou trânsito nesta etapa documental.
Quantidade de participantes, inclusão, duração, estímulos e critérios de
usabilidade precisam de protocolo próprio aprovado; não há taxa de acerto ou
limiar de conforto confirmado aqui. A detecção mecânica não prova percepção.

Preferir amplitude calibrada constante e ritmo antes de adicionar mais códigos.
Mudanças após revisão de UX precisam de perfil versionado e nova comparação;
nenhum padrão candidato deve ser comunicado como validado ou decisão final.

## 9. Rastreabilidade da #4 e estado da entrega

| Critério da issue | Evidência documental | Estado |
| --- | --- | --- |
| Mapeamento esquerda/direita/frontal | Seção 3 | Perfil experimental aprovado; TCA + 2 drivers informados, bancada pendente |
| Separar direção/proximidade/urgência | Seções 3–4 | Perfil experimental aprovado; limiares/amplitude pendentes |
| Início/fim da latência | Seção 5 | Protocolo experimental aprovado com fim mecânico |
| Repetições/registro | Seções 6–7 e CSV | Planejamento aprovado, sem resultados |
| Meta inferior a 100 ms | Seções 1/5/6 | Meta inicial preservada, não medida |
| Validação hardware/usabilidade | Seções 2/8 | Pendente, limites explícitos |
| Iniciar sem resposta VM | Seções 1/4/6 | Requisito confirmado; procedimento físico pendente |

A entrega da #4 é o perfil/protocolo experimental aprovado, sem implementação
de driver ou aprovação de desempenho. A bancada depende da #1 e da futura
integração local; captura/reprodução físicas da #17/#18 continuam pendentes.
O PR #57 (#9) foi integrado à main. Publicação/revisão documental da #4
precedem o fechamento desta issue; o aceite do desenho já foi registrado acima.
Nenhum contrato remoto, pino ou limiar operacional foi alterado.
