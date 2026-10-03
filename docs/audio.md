# Política determinística de anúncios — #5 e #31

- Data: 2026-10-01.
- Responsável previsto nas issues: Matheus (@Matheus-xz).
- Status: proposta de política e implementação experimental para revisão.
- Sem aprovação de novos parâmetros, integração física ou avaliação com pessoas.
- Issues: [#5](https://github.com/BryanPinheiro77/sonar-vision/issues/5),
  [#31](https://github.com/BryanPinheiro77/sonar-vision/issues/31).
- Referências: [escopo](ESCOPO.md), [contrato 0.1](protocol/eventos-semanticos.md),
  [ADR 0003](decisions/0003-eventos-semanticos.md), [módulo visual](vision.md).
- Dependências de conclusão: revisão do contrato/catálogo #25, API #24,
  reprodução/arbitragem #18, movimento #11 e direção/qualidade dos sensores.

## Requisitos confirmados e divisão do trabalho

A VM seleciona informação visual; o ESP32 arbitra sua admissão e reprodução.
Uma sugestão não representa entrega nem fala executada. Observação vazia,
classe desconhecida e silêncio não significam caminho livre. Confiança não
representa probabilidade de segurança. Não há dependência de LLM.

O contrato vigente limita texto a 120 pontos de código e idade a 1000 ms desde
captura (idade >= limite expira). Orientação >15 graus ou inválida cancela fala
direcional. Há uma fala atual e no máximo uma sugestão pendente; uma atualização
nova admissível substitui a pendente sem interromper automaticamente a atual.

A revisão aprovada mencionada nas #5/#25 permite aviso urgente curto **local**,
sem esperar rede. A #25 ainda deve consolidar essa regra no contrato e catálogo;
este trabalho não modifica o JSON 0.1 nem acrescenta campos de urgência.
O caminho tátil inicia independentemente de áudio, rede, TTS e seleção na VM.

| Prioridade local | Origem | Comportamento |
|---|---|---|
| Urgência | Geometria/estado local definidos na #9 | Vibração imediata; cancelar fala visual e pendente; permitir aviso local curto conforme #25/#18 |
| Disponibilidade estabilizada | Estado local da assistência visual | Aviso local respeita urgência e cooldown aprovado |
| Informação visual | Sugestão da VM | Admitir apenas se origem, idade, orientação e sessão forem válidas |

Urgência e seus níveis pertencem à #9. Nenhum objeto detectado recebe risco
geométrico por classe, confiança ou movimento aparente. Associar classe ao risco
exige associação validada; a mesma direção não é evidência dessa associação.
Não existe prioridade numérica nova no envelope 0.1.

Após urgência, o ESP32 não retoma frases canceladas e só admite capturas feitas
após a liberação. Avisos de disponibilidade usam 3000 ms sem resultado válido,
3 resultados novos consecutivos para recuperar e 10000 ms entre inícios de
avisos, conforme contrato; o seletor não implementa esse estado local.

## Vocabulário proposto para revisão de UX

| Classe | Nome falado |
|---|---|
| person | Pessoa |
| car | Carro |
| motorcycle | Moto |
| bus | Ônibus |
| bicycle | Bicicleta |
| chair | Cadeira |
| dining_table | Mesa |
| dog | Cachorro |
| stairs | Escada |
| unknown / traffic_light | Sem sugestão nesta política |

Crianças permanecem pessoa. Não inferir idade nem estado do semáforo.
Escada de subida/descida só usa valores fornecidos por uma implementação
validada da #16; unknown produz apenas “Escada”, sem inventar o sentido.

| Campo | Complemento proposto |
|---|---|
| left / center / right | à esquerda / ao centro / à direita |
| direction=unknown | Omitir localização |
| approaching | com aproximação aparente |
| receding | com afastamento aparente |
| crossing | com movimento lateral aparente |
| stable / movement=unknown | Omitir movimento |

Exemplos: “Pessoa à esquerda”, “Carro ao centro com aproximação aparente”,
“Escada de descida à direita”. Movimento é aparente na imagem, sem inferir
distância, TTC, trajetória convergente ou cruzamento da caminhada.
O módulo visual atual entrega direção e movimento unknown; assim, pode gerar
“Pessoa”, mas não uma direção ou movimento inventados.

Qualquer direção ou movimento aparente marca directional=true. Escada sem
direção/movimento não declara localização relativa. Todas as combinações de
vocabulário são verificadas quanto ao limite de 120 caracteres nos testes.

“Pare” e “Desvie” são comandos e **não são gerados** pelo seletor. Como hipótese
de aviso urgente local, “Atenção” pode ser comparado a esses comandos em teste
supervisionado. Não aprova frase operacional nem ação de locomoção.
A reprodução urgente e o catálogo permanecem na #25/#18.

## Seleção, repetição e configuração experimental

AudioPolicy exige AudioConfig: não existe política operacional implícita.
O perfil abaixo é **sugestão de laboratório**, usado nos testes, não decisão do
grupo nem limiar de segurança. Precisa de revisão antes de concluir #31.

| Parâmetro proposto | Perfil dos testes | Finalidade |
|---|---:|---|
| confidence_min | 0.50 | Admissão semântica; independente do filtro do detector |
| track_cooldown_ms | 2000 | Intervalo mínimo entre sugestões de estados diferentes do mesmo track |
| semantic_cooldown_ms | 10000 | Suprimir conteúdo equivalente entre IDs/epochs diferentes |
| memory_ttl_ms | 30000 | Expirar memória sem uso e permitir readmissão |
| max_tracks / max_semantics | 32 / 32 | Limitar estado por instância |
| class_order | person, car, motorcycle, bus, bicycle, chair, dining_table, dog, stairs | Desempate explícito para experimento; não ordenação de risco |

Algoritmo implementado:
1. Validar observação inteira, sessão, vocabulário e ordem antes de selecionar.
2. Descartar sugestão se a idade mínima conhecida já atingir a validade.
3. Excluir classes não faladas e scores abaixo do parâmetro configurado.
4. Identificar track por sessão da instância + epoch + ID. null usa somente
   supressão semântica; não inventar identidade.
5. Comparar com último estado **sugerido**, não apenas último frame. Stable e
   unknown de movimento equivalem no texto; track inalterado não é narrado
   periodicamente enquanto sua presença for renovada.
6. Aplicar cooldown por track e por conteúdo equivalente (classe, direção,
   movimento falado e sentido da escada). Troca de ID/epoch não basta para repetir.
7. Priorizar mudança de estado previamente sugerido, depois entrada nova.
   Desempatar por class_order, maior score e ordem original dos objetos.
8. Retornar uma sugestão ou None. Atualizar memória apenas da selecionada;
   presença de tracks inalterados renova sua retenção, não seu cooldown.

Limites: supressão semântica pode ocultar duas pessoas diferentes com a mesma
descrição. Não conta pessoas nem comprova identidade. Mudança de direção cria
conteúdo diferente; falso tracking ainda pode produzir fala inadequada.
Ausência prolongada expira memória, permitindo nova sugestão. Buffers cheios
rejeitam novos candidatos sem expulsar supressões ainda ativas.
Não há fila nem áudio em execução nesta classe.

## Interface e execução

Sem dependências novas, Python >=3.11. Importar explicitamente:

```python
from sonar_vision.audio import AudioConfig, AudioPolicy

# Perfil proposto de LABORATÓRIO; valores precisam de aprovação para integração.
config = AudioConfig(
    confidence_min=0.50, track_cooldown_ms=2000,
    semantic_cooldown_ms=10000, memory_ttl_ms=30000,
    max_tracks=32, max_semantics=32,
    class_order=("person", "car", "motorcycle", "bus", "bicycle",
                 "chair", "dining_table", "dog", "stairs"),
)
policy = AudioPolicy("session-from-device", config)
# observation = result.observation() do módulo visual, sessão correspondente.
audio = policy.select(observation, capture_age_lower_bound_ms=elapsed_known_ms)
response = {"observation": observation, "audio": audio}
```

Trecho de interface, não API executável. A #24 deve manter uma instância por
dispositivo autenticado/sessão, serializar chamadas e remover estado no fechamento.
Outra sessão exige outra instância; não compartilhar estado entre usuários.
O estado de tracks inclui epoch; a supressão de conteúdo atravessa resets do
tracker dentro da sessão. IDs da sugestão são novos UUIDs; uma retransmissão
deve reutilizar o envelope existente, nunca recalcular a sugestão.

capture_age_lower_bound_ms é um inteiro obrigatório que representa apenas
tempo desde captura conhecido pelo chamador. Na VM, tempo decorrido desde
entrada da requisição é um limite inferior conservador; não inclui latência
anterior de rede/captura. Não subtrair captured_at_ms do relógio da VM.
Zero é permitido quando nenhum atraso é conhecido, não prova captura recente.
A #24 deve registrar instante monotônico na entrada e computar o intervalo
conhecido ao selecionar; o ESP32 decide a idade real usando seu registro local.

A saída preserva sessão, frame, captura e observation_id; limita valid_for_ms
a min(validade da observação, 1000), **sem reiniciar validade na VM**.
Nenhum campo extra, comando de vibração, referência de arquivo ou catálogo.
Valor malformado, replay, ordem inválida ou sessão divergente gera ValueError;
a API deve tratá-lo sem reproduzir texto de erro.
O seletor não é parser JSON: limites de bytes, chaves duplicadas, autenticação,
TLS, observação de origem e cancelamento pertencem às camadas de integração.

Comandos reais na raiz, PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -B -m unittest discover -s tests -p test_audio.py -v
python -B -m unittest discover -s tests -v
git diff --check
```

A flag -B evita arquivos de bytecode. Não há comando de firmware ou TTS.

## Roteiro de compreensão e carga cognitiva — ainda não executado

Antes de testes com pessoas: responsável e supervisor definidos, consentimento,
avaliação ética institucional e possibilidade de desistência; áudio sintético
de bancada primeiro. Não publicar nomes, imagens, gravações ou dados pessoais.
Não depender do protótipo para atravessar ruas, desviar obstáculos ou usar escadas.

1. Registrar versão, perfil, catálogo/voz, volume, ambiente, ordem e duração
   das frases. O formato/catálogo real depende da #25/#18.
2. Comparar frases apenas com objeto, objeto+direção e objeto+direção+movimento.
   Alternar ordem para reduzir efeito de aprendizagem; incluir unknown e silêncio.
3. Solicitar relato do que foi compreendido: classe, direção relativa aos óculos,
   movimento aparente e incerteza. Registrar respostas corretas, incorretas e
   inconclusivas separadamente; silêncio não deve ser interpretado como segurança.
4. Comparar avisos informativos e hipótese “Atenção” com comandos “Pare/Desvie”
   em simulação supervisionada, sem exigir ação perigosa. Registrar confusão,
   expectativa de segurança, esforço percebido e distração de sons ambientais.
5. Medir início/fim de fala e idade desde captura. Variar atraso conhecido,
   fala pendente, direção da cabeça, falha de rede e urgência local.
   Não ampliar 1000 ms para terminar a frase.
6. Medir frases concluídas/interrompidas, compreensão após corte, descartes,
   tempo de resposta e avaliação de esforço em escala explicitada no protocolo.
   Apresentar numeradores/denominadores por condição, não só médias.
7. Grupo aprova previamente amostras, condições, escala de esforço e critérios
   quantitativos de aceitação; não existe percentual aprovado nesta entrega.

## Matriz de verificação e limitações

| Critério | Evidência disponível / pendência |
|---|---|
| #5 mensagens e níveis | Vocabulário proposto; urgência exclusivamente local; revisão UX pendente |
| #5/#31 cooldown, mudanças, múltiplos candidatos | Testes sintéticos do seletor; parâmetros ainda propostos |
| #31 expiração e direção indeterminada | Testes de limite inferior conhecido e unknown; idade real/orientação no ESP32 pendentes |
| #5 simultaneidade, interrupção, disponibilidade | Regras documentadas do contrato; execução local #18 não implementada |
| #5 compreensão, carga e validade curta | Roteiro acima; nenhum participante/TTS avaliado |
| #31 contrato 0.1 | Campos/referências e comprimento testados; catálogo depende #25 |
| #31 integração pela #24 | Interface documentada; API não existe neste checkout |
| #5 vibração sem atraso por áudio | Seletor não acessa hardware nem risco; teste físico/rede desligada ainda necessário |

A alternativa de narrar cada frame foi descartada por repetição e acúmulo.
Compartilhar supressão entre usuários mistura contextos; instâncias são isoladas.
LLM/TTS no seletor adicionariam dependências sem necessidade da seleção determinística.
Nenhuma arquitetura, limiar local, pino ou contrato foi alterado; não há novo ADR
aceito. Mudança do contrato/catálogo deve ser consolidada pela #25.

As issues não devem ser consideradas concluídas apenas com estes testes:
aprovação da política, revisão #25, integração #24/#18 e avaliações aplicáveis
continuam pendentes. Simulação não comprova segurança ou ausência de atraso tátil.

O [catálogo da #32](audio-catalog.md) prepara textos/IDs e valida arquivos de
voz em ferramenta local; aprovação, lote final e revisão auditiva pendentes.
Não muda o contrato 0.1 nem preenche sugestões com arquivos automaticamente.
