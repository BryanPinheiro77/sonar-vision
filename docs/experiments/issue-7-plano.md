# Plano de avaliação de modelos — #7

Data: 2026-10-16. Preparação: Bryan; responsável previsto na issue: Matheus.
Status: **proposta, sem aprovação de amostras ou critérios finais**.
Refs [#7](https://github.com/BryanPinheiro77/sonar-vision/issues/7),
[protocolo](protocolo-visual.md), [escopo](../ESCOPO.md),
[avaliação de detecção](../evaluation.md) e [movimento](../motion-evaluation.md).

## Objetivo

Avaliar o YOLO geral junto ao especialista R21 congelado, localizar falhas e
só então decidir se precisam de treino. Esta preparação pertence a modelo/cloud;
não exige montagem, ESP, nova VM ou gravação imediata. A avaliação integrada da
#19 continua separada e depende da frente de hardware.

Não há vídeo novo, anotação real ou resultado de qualidade nesta entrega.
O caminho tátil local continua independente da câmera, dos modelos e da nuvem.

## Etapas e esforço propostos

| Etapa | Amostra proposta | Finalidade |
|---|---|---|
| Piloto de desenvolvimento | 12 tomadas de 8–12 s, boa luz | Verificar captura, anotação e exportação; roteiro da #11 |
| Detecção independente | 60 tomadas de 10 s | 10 categorias de avaliação × 3 iluminações × 2 tomadas |
| Movimento/identidade independente | 36 tomadas de 10 s | 6 procedimentos × 3 iluminações × 2 tomadas |
| Negativos independentes | 6 tomadas de 10 s | 3 iluminações × 2 tomadas, sem as classes avaliadas |

O teste proposto soma **102 tomadas, 17 minutos de mídia**. Não inclui preparação,
consentimento, anotações ou revisão. O piloto não entra nessas 102 tomadas.
Duas tomadas por célula são um mínimo descritivo proposto, não evidência de
robustez estatística. Frames de uma tomada são correlacionados; milhares de
frames não equivalem a milhares de fontes independentes.

A [matriz CSV](issue-7-matriz.csv) contém 51 células planejadas, duas tomadas
por célula e **zero coletadas**. É planejamento, não manifesto de dados reais.
Usar o manifesto v1 apenas quando existirem mídia, hash, permissões e anotações.
Não inserir caminhos, participantes ou consentimentos no CSV público.

### Aplicabilidade

Detecção: person, car, motorcycle, bus, bicycle, chair, dining_table, dog,
mais stairs/up e stairs/down como categorias de relatório, sem criar classes
novas no contrato. Nas oito classes gerais, usar C04: câmera fixa, objeto parado,
início visível, oclusão parcial por anteparo e retorno à visibilidade. Registrar
separadamente intervalos visíveis e ocultos. Para veículos, câmera/anteparo ficam
em área autorizada, com veículo estacionado; não bloquear a visão de motoristas.
C06/C07 observam escadas de posição protegida. Incluir segmentos de ângulo
ambíguo com referência unknown, sem forçar sentido e sem contá-los como acerto
de up/down. Não exigir caminhada em escadas.

Movimento: usar person nos seis procedimentos do
[roteiro #11](issue-11-coleta.md): estática, aproximação/afastamento,
cruzamento nos dois sentidos, oclusão, dois alvos e câmera móvel.
Estática usa dois alvos parados e scenario=multiple_targets; aproximação/retorno
usa scenario=approach, com os dois segmentos no diário/anotação. Câmera móvel
usa scenario=negative: controle negativo de movimento conhecido, embora haja
pessoa na imagem. O procedimento e a referência humana distinguem esse controle
de negativos de detecção sem alvo. Não adicionar valores ao manifesto v1.

Essa matriz avalia detecção das oito classes e movimento de pessoas. Movimento
de veículos/animais e trajetória de outras classes **não ficam validados** por
extrapolação. Se necessários, exigem extensão aprovada e coleta segura.

Todas as células incluem good, low e public_night, sem limites de lux inventados.
Se uma célula não for viável, registrá-la como pendente com justificativa e
submeter alternativa ao grupo; não removê-la nem atribuir zero erros.
Não usar brinquedos, telas ou fotografias como substituto de objetos reais.

### Distância e fontes

Para o piloto com pessoa, propor marcas a 2 e 4 m da câmera, tolerância de
posicionamento de 0,25 m, se o espaço for seguro. Medir com trena e registrar
valores efetivos; não inferir distância pela caixa. Para veículos, escadas e
mobiliário, registrar a distância disponível ou null com justificativa; este
plano não promete alcance mínimo de detecção.

As duas tomadas da mesma célula devem vir de grupos de origem distintos,
preferencialmente sessões/objetos/locais distintos. Duas gravações consecutivas
correlacionadas não satisfazem automaticamente independência: agrupar juntas e
coletar outra fonte. A revisão humana verifica isso; hashes não comprovam origem.

Os vídeos de cadeira/mesa A e B já foram vistos e utilizados no piloto #51;
permanecem desenvolvimento/comparação exploratória. Os vídeos conhecidos usados
na seleção de R20/R21 também não são teste independente. Recortes e transcodes
herdam a origem e o split. Não reutilizar esses dados como teste final cego.

## Configuração a congelar

Preservar o [perfil R21](issue-22-r21-profile.json): YOLO geral + R21, confiança
0,35, imgsz 640, CPU, rect=true, max_det=300, upload max-edge 640 e JPEG95.
R20 permanece rollback. Registrar hashes dos dois pesos e de cada configuração,
commit, versões de bibliotecas, ByteTrack e configuração completa da trajetória.
Não transformar o rollback em seleção do melhor resultado após abrir o teste.

Proposta de avaliação: IoU=0,50, associação max_cardinality_then_iou,
ignore_policy=exclude_invisible_overlap e minimum_sources_per_group=2.
max_gap_frames fica pendente de congelamento após verificar a cadência no piloto. O IoU de avaliação precisa de aprovação própria:
o valor 0,50 de associação do especialista não aprova este critério.
Não copiar confiança 0,50 das fixtures sintéticas; ela difere do candidato real.

Propor processamento a 10 imagens/s usando timestamps originais: selecionar o
primeiro frame disponível em cada intervalo de 100 ms, sem duplicar frames.
Preservar os índices originais; reportar intervalos sem frame e cadência real.
Rodar tracker/estimador em toda a sequência selecionada. Para detecção, propor
anotar o primeiro frame selecionado de cada segundo; para tracking/movimento,
anotar toda a sequência selecionada, preservando os frames sem detecção.
Gerar snapshots separados: não calcular continuidade na amostra esparsa de 1 Hz.
max_gap_frames usa os índices originais registrados, não segundos: documentar
os saltos causados pela seleção e aprovar um limite compatível antes do teste.
Não renumerar silenciosamente os frames para esconder gaps nem substituir
timestamps por índice/FPS médio. A regra de gaps deve constar em cada relatório.

Revisar o piloto antes de congelar essa exportação: o journal atual não contém
predições de movimento. Ainda é necessário conectar o adapter da #11 ao produtor
real e às anotações; não reconstruir movimento ausente a partir do journal.
O especialista de escadas pode produzir track_id=null; reportar ausência de
tracking, sem inventar identidade para calcular movimento de escadas.

## Anotação, métricas e decisões de aceite

Anotar sem usar predição como verdade; um segundo integrante revisa todos os
rótulos de classe/sentido, identidades e segmentos, e uma amostra proposta de
20% das caixas. Resolver discordâncias antes de abrir predições do teste.
Guardar versões, mapa de frames, exclusões justificadas e revisão em privado.
Visibilidade parcial avaliável tem caixa anotada; totalmente invisível é
visible=false. Frames ilegíveis devem ter decisão humana anterior ao resultado,
com contagem de exclusões; falhas de decode, timeout e descarte não são acertos.

| Dimensão | Relatório obrigatório | Situação do aceite |
|---|---|---|
| Detecção | TP/FP/FN, precision/recall/F1 por classe e iluminação, contagens por tomada | Percentuais finais pendentes |
| Escadas | up/down × up/down/unknown/missed, cobertura e acerto sobre toda verdade conhecida | Limites de confusão/abstenção pendentes |
| Negativos | FP por tomada, classe e minuto observado | Limite final pendente |
| Identidade | Perdas, ID ausente, trocas, fragmentações, transferências e resets | Limites finais pendentes |
| Movimento | Acerto sobre todas as referências conhecidas, unknown/missed e lateral separado | Limites finais pendentes |
| Câmera móvel/unknown | Contagem de saídas de movimento conhecido, inclusive sem match | Proposta: zero violações do bloqueio |
| Processamento/rede | FPS e P50/P95/P99 com escopo e relógio declarados | Metas experimentais da #22, quando o mesmo caminho for medido |

Não propor um percentual de qualidade sem observar a viabilidade e os problemas
de anotação no piloto. Após o piloto de desenvolvimento, o grupo deve aprovar
limiares numéricos por classe/condição, regras de anotação e a amostra final,
**antes de executar ou inspecionar predições do teste independente**. Este plano
não conclui esse critério da #7. Células sem denominador são N/A, nunca 100%.
As ferramentas não calculam mAP, IDF1 ou HOTA; não rotular outras contagens assim.

A #22 aprovou um óculos, ≥8 frames/s admitidos, P95 de trabalho no servidor
≤80 ms e JPEG pronto→admissão P95≤150 ms/P99≤250 ms. São metas de desempenho
experimental daquele caminho, não acurácia nem captura→áudio. Replay offline
não valida rede, ESP, consumo, áudio físico ou latência sensor→vibração.
Separar compressão, modelo, tracking, rede e latência ao classificar falhas.
Novo treino exige falha de modelo e exemplos aprovados; preservar o teste fora
do treino, mesmo após resultados ruins.

## Ordem de execução e pendências

1. Revisar esta proposta; designar coleta, anotação e segundo revisor no trio.
2. Registrar autorização/ética, acesso privado, retenção e descarte antes da coleta.
   A política institucional e esses responsáveis continuam pendentes.
3. Executar o piloto e concluir a ligação do produtor real com a avaliação.
4. Aprovar e congelar matriz, amostra, configurações e limiares finais na #7.
5. Coletar/anotar fontes independentes sem usar predições para escolher cenas.
6. Executar, revisar falhas e publicar só síntese agregada. Manter #7/#11/#16
   abertas até suas evidências e critérios efetivos serem atendidos.

Este PR documenta preparação. Não adota parâmetros novos, muda API/contrato,
reabre treino ou aprova uso do protótipo. A indisponibilidade da nuvem nunca
pode interromper o feedback tátil local. Testes físicos continuam com hardware.

## Verificação desta preparação

Em macOS/Python 3.14.7, em 2026-10-16:

- 54 testes existentes de manifesto, avaliação e avaliação de movimento passaram,
  sem falhas, erros ou skips.
- CSV conferido: 51 IDs únicos, 102 tomadas propostas, três iluminações com
  17 células cada, nenhuma tomada coletada ou aprovação registrada.
- check_docs: 97 Markdown, zero problemas; git diff --check sem erros.

Comandos reproduzíveis, na raiz:

```sh
PYTHONPATH=src python3 -m unittest tests.test_evaluation_manifest tests.test_evaluation tests.test_motion_evaluation -q
python3 scripts/check_docs.py
git diff --check
```

Esses testes verificam ferramentas existentes e consistência documental.
Não validam tamanho estatístico da amostra, desempenho real, ética ou hardware.
