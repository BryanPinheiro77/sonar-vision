# Issue #16 — investigação de escadas e sentido

Iniciado em 2026-09-26; piloto local em 2026-09-28. Estado: **investigação
exploratória**, com integração opcional do classificador de sentido, ainda sem
ativação padrão ou avaliação formal. Responsável:
Bryan. Este documento distingue o que o contrato já exige das hipóteses que
precisam de decisão e dados.

## Requisitos confirmados

- O [escopo aprovado](../ESCOPO.md) exige reconhecer escadas e distinguir
  subida/descida, admitindo sentido inconclusivo (FR-03/AC-03).
- O [contrato 0.1](../protocol/eventos-semanticos.md) já prevê `class_name=stairs`
  e `stair_direction=up|down|unknown`; outros objetos usam `null`. Não acrescentar
  campos sem revisão do contrato.
- A #21 fornece a interface de detecção/tracking e devolve `unknown` para uma
  detecção `stairs` simulada. Os pesos COCO usados no módulo **não detectam
  escadas**; normalizar o nome da classe não cria essa capacidade.
- O alerta geométrico/tátil local no ESP32-S3 continua independente da câmera,
  rede e VM. Reconhecimento visual de escadas não mede borda do degrau, buracos,
  distância nem TTC com segurança.

## Definição dos rótulos e protocolo pendente

**Definição confirmada por Bryan para a #16 em 2026-09-29:** `up` quando a
escadaria à frente sobe a partir da posição da câmera; `down` quando desce;
`unknown` quando há escada, mas a imagem não permite determinar o sentido;
`none` quando não há escada visível. Os rótulos descrevem a cena observada,
não o movimento de uma pessoa nem uma instrução para caminhar. Anotar uma
caixa por trecho de escada visível antes de escolher a arquitetura.
Uma foto pode conter mais de um trecho e sentidos diferentes; registrar cada
um, ou marcar ambiguidade, em vez de forçar um rótulo para a imagem inteira.

A #7 não redefine o significado desses rótulos. Ela deve fixar o protocolo
de avaliação: cenas, condições, quantidade de locais independentes, métricas
e critérios quantitativos de aceitação. A regra operacional para o modelo
retornar `unknown` ainda precisa ser calibrada com dados de ajuste; isso é
diferente de definir o que `unknown` significa.

Não há mídia de escadas identificada no laboratório local em 2026-09-26.
A #7 deve definir/autorizar cenas, origem, armazenamento, licenças, consentimento
quando aplicável, tamanho de amostra, condições e limiares de aceitação **antes**
da avaliação final. Separar treino/ajuste de teste por local, escadaria e sessão
de captura; frames vizinhos do mesmo vídeo não podem aparecer nos dois lados.
Guardar imagens/vídeos/pesos fora do Git e registrar como obtê-los ou acessá-los
com permissão, sem publicar dados pessoais.

Para um **piloto exploratório**, vídeos públicos podem ser usados quando a
licença da página de **cada arquivo** permitir o uso pretendido. Uma fonte
possível é [Wikimedia Commons](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia/en),
que informa autor, licença e condições por arquivo. Registrar URL, autor,
licença, data de acesso, permissão e eventuais exigências de crédito; manter o
vídeo fora do Git. Escolher pelo menos uma vista do pé da escada (`up`), uma do
topo (`down`) e uma cena sem escada; vistas laterais ou com sentido incerto
devem ser marcadas `unknown`, não forçadas para `up/down`. Esse piloto verifica
execução e revela falhas, mas vídeos avulsos da internet não substituem o
protocolo independente da #7 nem representam automaticamente a câmera dos óculos.

### Fontes externas examinadas, ainda não aprovadas

| Fonte | O que a página informa | Pendência antes de usar |
|---|---|---|
| [Open Images V7 / YOLOv8n-oiv7, Ultralytics](https://docs.ultralytics.com/datasets/detect/open-images-v7/) | Configuração com 601 classes, incluindo `Stairs`, e peso YOLOv8n pré-treinado disponível sem baixar o dataset inteiro. Não rotula subida/descida. | Testar origem/licença dos pesos, compatibilidade com o adaptador fixado e desempenho em cenas independentes dos óculos. O dataset inteiro é grande; não baixá-lo para este piloto. |
| [Staircase Dataset, Mendeley Data](https://data.mendeley.com/datasets/7m97gp4yz9/1) | Mais de 500 imagens/XML, rótulos `upstair`/`downstair`, licença declarada CC BY 4.0. | A página aponta imagens derivadas de busca Google e outras fontes. Verificar direitos de cada origem, duplicatas, qualidade das caixas e cobertura de descida; a licença declarada do conjunto não resolve sozinha a proveniência de cada imagem. |
| [up-down stairs, Roboflow Universe](https://universe.roboflow.com/stairs-n9kkx/up-down-stairs) | 1.289 imagens, classes `upstairs`, `downstairs` e `object`, licença declarada CC BY 4.0. | Falta descrição da origem na página. Auditar proveniência, significado de `object`, split, duplicatas e condições antes de baixar, treinar ou citar desempenho publicado como resultado nosso. |
| [TAMU stair dataset](https://github.com/KangneoungLee/staircase_detection) | RGB-D, 2.276 imagens positivas e 546 negativas, voltado a escada ascendente para robôs. | Licença MIT do código não prova licença dos dados; modalidade/posição da câmera diferem dos óculos e não cobre descida declarada. Confirmar licença e adequação. |

Essas fontes são **candidatas**, não escolha de dataset, dependência ou modelo.
Priorizar uma coleta controlada do grupo se os direitos e a diversidade dos
dados públicos não forem verificáveis. Sem dados/labels auditados não há base
para afirmar precisão ou ajustar limiares.

## Abordagens para comparar, sem escolha antecipada

1. **Primeiro piloto sem treino:** avaliar o peso oficial `yolov8n-oiv7.pt`
   para presença/caixa de `Stairs` em mídia autorizada. Seu rótulo não resolve
   `up/down`; até haver classificador avaliado, transmitir `unknown`. Medir
   também compatibilidade, latência e memória frente ao detector COCO atual.
2. Detector especializado que devolva caixa e `up/down`, com abstenção
   `unknown` definida sobre evidência insuficiente. Exige dados auditados;
   não substituir o detector multiclasse sem avaliar perda das classes atuais.
3. Detectar `stairs` e depois classificar sentido em recorte da mesma imagem.
   Pode facilitar a abstenção, mas exige duas etapas e medição de custo.
4. Regras de linhas/perspectiva ou dados de profundidade são baselines de
   pesquisa; textura, oclusão e ponto de vista podem gerar confusão. O VL53L5CX
   previsto tem cobertura/resolução a validar em bancada e não deve ser tratado
   como detector de descida já disponível.

Uma prova offline pode começar com mídia autorizada e OpenCV/Ultralytics já
previstos. Nova dependência, peso ou hardware exige origem/licença e justificativa
registradas. A decisão de arquitetura e integração será documentada em ADR
depois de resultados comparáveis, não agora.

## Piloto local de presença de escadas — 2026-09-28

Bryan autorizou usar apenas localmente oito imagens baixadas para uma verificação
exploratória. Quatro mostram escadas vistas de baixo (`up`), três de cima
(`down`) e uma contém trechos que sobem e descem no mesmo quadro (`mixed`). Esses
rótulos foram atribuídos por inspeção visual humana; **não são saídas do
modelo**. Algumas imagens têm marca d'água e a licença de cada arquivo não foi
verificada. Imagens, cópias convertidas e pesos permaneceram fora do Git; os
resultados abaixo não autorizam redistribuição, treino ou uso em avaliação final.

Foi usado o peso oficial `yolov8n-oiv7.pt` da [Ultralytics/Open Images V7](https://docs.ultralytics.com/datasets/detect/open-images-v7/),
baixado do release oficial `v8.4.0` da Ultralytics. SHA-256 local:
`3851dfbf39ed2a076b1f39215cc22dba64eb5646f282bf964703785b0bed6a41`.
Ambiente: laboratório local no Mac, Ultralytics `8.4.137`, CPU, `imgsz=640`.
Primeiro, inspecionou-se a saída direta do YOLO com `conf=0.10`, sem salvar
previsões. O limiar `0.35` abaixo é o padrão atual de `VisionConfig` e foi
aplicado aos scores observados; não houve ajuste de limiar com essas imagens.

| Cena local | Maior score `Stairs` | Caixas `Stairs` com `conf=0.10` | Passaria pelo limiar padrão `0.35`? |
|---|---:|---:|---|
| Subida 1 | 0.892 | 1 | Sim |
| Subida 2 | 0.780 | 1 | Sim |
| Subida 3 | 0.652 | 1 | Sim |
| Subida 4 | 0.688 | 4 | Sim |
| Descida 1 | 0.240 | 1 | Não |
| Descida 2 | 0.754 | 1 | Sim |
| Descida 3 | nenhuma | 0 | Não |
| Mista, subida e descida | 0.279 | 3 | Não |

Assim, sete das oito imagens tiveram alguma caixa de `Stairs` no limiar
exploratório `0.10`; apenas cinco passariam pelo limiar padrão `0.35`. As três
caixas da cena mista se sobrepuseram e não isolaram de forma confiável os
trechos com sentidos diferentes. Em uma das descidas não apareceu caixa nem no
limiar baixo. Esses números **não são precision, recall ou taxa de acerto**:
faltam negativos, anotações de caixa, amostra independente e protocolo da #7.
As imagens foram selecionadas pelo usuário, têm perspectivas diferentes da
câmera prevista para os óculos e não representam desempenho em uso real.

O caminho existente `UltralyticsFactory → VisionService → observation()` foi
executado com `VisionConfig()` padrão em uma imagem de subida e uma de descida.
Ambas produziram `class_name=stairs` e `stair_direction=unknown`, com scores
0.892 e 0.754. O peso detecta presença/caixa; **não classifica subida ou
descida**. Não houve mudança de código, contrato, limiar, lógica local ou
dependência do projeto. A licença/condições dos pesos ainda precisam ser
verificadas antes de qualquer distribuição ou integração permanente.

### Primeira foto própria de subida

Bryan selecionou uma foto feita do pé da escada, sem pessoa em primeiro plano,
para o teste local. A imagem ficou apenas no anexo da sessão, fora do Git. No
caminho `UltralyticsFactory → VisionService → observation()`, com configuração
padrão e CPU, apareceu uma caixa `stairs` com score `0.770` e
`stair_direction=unknown`. A caixa normalizada foi
`(0.213, 0.154, 0.841, 0.593)`, cobrindo a região da escadaria por inspeção
visual. O tempo observado de `702.5 ms` inclui a primeira inferência e **não**
serve como benchmark de latência. É uma única cena de subida; não demonstra
generalização, descida nem classificação de sentido. Uma foto do topo da mesma
escada será útil para o próximo teste exploratório, mas as duas vistas do mesmo
local não devem ser tratadas como cenas independentes na avaliação final.

### Quatro fotos próprias da mesma escada — 2026-09-29

Bryan disponibilizou em Downloads quatro fotos originais da mesma escadaria:
uma vista de baixo (`IMG_3067.jpeg`, subida) e três vistas do topo
(`IMG_3068.jpeg` a `IMG_3070.jpeg`, descida). O sentido foi atribuído por
inspeção humana da posição da câmera. Algumas fotos mostram pessoas; Bryan
informou autorização do colega visível, mas não há registro aqui do alcance da
autorização nem de todas as pessoas ao fundo. Por isso, as fotos foram usadas
somente no Mac para este teste, sem cópia para o Git ou publicação.

Com o mesmo peso `yolov8n-oiv7.pt`, `VisionConfig()` padrão (`conf=0.35`,
`imgsz=640`, CPU) e o caminho completo
`UltralyticsFactory → VisionService → observation()`:

| Foto | Vista humana | Caixas `stairs` | Maior score `stairs` | Saída `stair_direction` |
|---|---|---:|---:|---|
| `IMG_3067.jpeg` | Subida | 1 | 0.831 | `unknown` |
| `IMG_3068.jpeg` | Descida | 0 | — | Sem objeto `stairs` |
| `IMG_3069.jpeg` | Descida | 0 | — | Sem objeto `stairs` |
| `IMG_3070.jpeg` | Descida | 0 | — | Sem objeto `stairs` |

Uma inspeção adicional da saída direta do YOLO com `conf=0.10` também não
encontrou caixas `Stairs` nas três vistas de descida. Reduzir o limiar de
`0.35` para `0.10` não resolve essas falhas observadas. As três fotos de
descida são muito parecidas e pertencem à mesma escada/sessão: isto é **um
caso de falha repetido**, não três cenas independentes nem estimativa de recall.
O resultado reforça a necessidade de incluir vistas de descida, cenas sem
escada e outras escadarias no protocolo da #7 antes de escolher/ajustar um
modelo. Nenhum limiar ou contrato foi alterado.

Foi criado `datasets/issue16-pilot/manifest.json` **apenas neste computador**;
`datasets/` é ignorado pelo Git. O manifesto aponta para os quatro arquivos em
Downloads e registra hash SHA-256, dimensões, um identificador comum de cena e
o sentido atribuído por inspeção. Ele não copia as fotos. Seu estado é
`catalog_only_not_train_ready`: faltam caixas verificadas, negativos, outras
escadarias e uma separação por local entre ajuste e teste. Não usar as três
fotos parecidas de descida como teste independente de um modelo ajustado nelas.

Como diagnóstico adicional, o mesmo peso foi executado em `imgsz=1280` e
`conf=0.10` nas três vistas de descida. Nenhuma produziu caixa `Stairs`.
Portanto, nesse caso, apenas dobrar a resolução de entrada também não resolveu
a falha. Essa execução única não é benchmark de custo ou latência e não altera
a configuração padrão `imgsz=640`.

### Lote de 17 fotos e primeiro treino exploratório — 2026-09-29

Bryan trouxe `IMG_3072.jpeg` a `IMG_3088.jpeg` e confirmou que mostram
**duas escadas diferentes da mesma casa**, com 10 vistas de subida e 7 de
descida. Incluem
variação de ângulo, distância, luz e movimento, mas várias tomadas são quase
duplicadas. Três fotos de descida (`IMG_3075` a `IMG_3077`) mostram uma etiqueta
de encomenda potencialmente identificável; ficaram fora do treino e não devem
ser compartilhadas sem revisão de privacidade. Todas as fotos continuam fora
do Git.

Com o peso original Open Images V7, `imgsz=640`, CPU e o limiar padrão `0.35`,
houve alguma caixa `Stairs` em **7/10 fotos de subida e 0/7 de descida** desse
lote. No limiar diagnóstico `0.10`, foram **9/10 de subida e 1/7 de descida**.
Esses são números descritivos do lote correlacionado, não recall: não há
verificação de IoU das caixas, negativos ou cenas independentes suficientes.
O relatório local sem pixels está em `results/issue16-baseline-own-photos.json`
(ignorado pelo Git).

Um **piloto de treino, não candidato de integração**, usou caixas aproximadas
por inspeção da IA, pendentes de revisão humana, para classes `stairs_up` e
`stairs_down`. Foram 12 imagens de treino e 2 de validação do segundo local,
com 4 imagens do primeiro local reservadas para teste fora do treino. A
validação interna compartilha local e textura com o treino, logo não mede
generalização. Não havia imagens negativas. Os links para fotos, rótulos,
manifesto e pesos ficam em `datasets/`, `results/` e `runs/`, todos ignorados
pelo Git; nenhuma foto foi copiada para o repositório versionado.

Ao trocar a saída do detector de 601 classes por duas classes neste treino, o
piloto aproveitou parte dos parâmetros pré-treinados, mas **não preservou as
601 classes do detector original**. Os dois pesos são alternativas de inferência
distintas; o piloto não é o peso original acrescido de `up/down`.

Configuração do piloto: Ultralytics `8.4.137`, `yolov8n-oiv7.pt` como ponto de
partida, 20 épocas, `imgsz=640`, batch 4, CPU, seed 16, mosaic 0. O peso local
resultante `runs/issue16-pilot/first-training/weights/best.pt` tem SHA-256
`4676a0fc38aacb53133e11857cd4b9968b139a1b2f198f86108df724a7d122fb`.
Nas quatro fotos do local reservado, o piloto produziu **zero detecções** em
`conf=0.10`; amostras do próprio treino também tiveram zero nesse limiar.
Em `conf=0.001`, scores máximos ficaram abaixo de `0.07` nas quatro amostras
inspecionadas; uma descida recebeu principalmente previsões fracas `stairs_up`.
Não reduzir o limiar para tentar declarar sucesso. O mAP de validação que a
ferramenta calculou sobre apenas duas fotos correlacionadas não contradiz essa
falha operacional. Esse primeiro peso **não melhora o baseline e não deve ser
integrado, distribuído ou usado para alertas**.

Próximos passos: revisar manualmente caixas e rótulos; obter cenas negativas e
mais escadarias de locais independentes, com subida e descida em cada local;
definir na #7 o critério de avaliação e calibrar a regra de abstenção; só então treinar
ou comparar outra arquitetura e testar em locais não vistos. Um detector de
duas classes também exigiria adaptação explícita para o contrato
`class_name=stairs` + `stair_direction`, preservando as outras classes do módulo
visual. Nada disso foi alterado pelo piloto.

### Quatro fotos de duas outras escadas — 2026-09-29

Bryan informou que fotografou as quatro imagens e confirmou que são **duas
escadas distintas**, uma interna e outra externa, cada uma vista de baixo e de
cima. A relação entre os respectivos locais físicos ainda não foi confirmada,
portanto seus IDs de local no manifesto são provisórios. O uso autorizado nesta
etapa é local; não atribuir licença de redistribuição sem registro próprio.

| Escada/vista | Peso original OIV7: melhor score `Stairs` | Peso do treino piloto |
|---|---:|---|
| Interna, subida | 0.778 | Sem caixa em `conf=0.10` |
| Interna, descida | 0.754 | Sem caixa em `conf=0.10` |
| Externa, subida | 0.532 | Sem caixa em `conf=0.10` |
| Externa, descida | Sem caixa em `conf=0.10` | Sem caixa em `conf=0.10` |

O peso original detectou três das quatro cenas no limiar padrão `0.35`; a
descida externa continua como exemplo de falha. O peso treinado localmente
falhou nas quatro. Esses resultados reforçam que **o primeiro treino não deve
ser integrado**. As quatro fotos já foram usadas nesta comparação exploratória;
se entrarem em treino/ajuste posterior, não podem ser reutilizadas como teste
final intocado. Registro local sem pixels em
`results/issue16-four-new-photos.json`, ignorado pelo Git. As fotos continuam
em Downloads e o manifesto local passou a 25 entradas. Ainda faltam cenas sem
escada, caixas revisadas e mais locais independentes para avaliar falsos
positivos, generalização e sentido.

### Revisão das caixas e cenas negativas — 2026-09-29

Foram inspecionadas visualmente as **18 caixas provisórias** usadas no primeiro
piloto, em três pranchas locais de seis fotos (`results/issue16-box-review-*.png`).
Elas abrangem degraus visíveis, mas não são rótulos confiáveis para uma nova
avaliação ou treino sem correção:

- `IMG_3078` a `IMG_3084`: parte do piso plano no pé da escada ficou dentro
  das caixas de subida, em proporções diferentes entre fotos semelhantes.
- `IMG_3085` a `IMG_3088`: as caixas de descida incluem sapato/perna de quem
  fotografou e os degraus estão parcialmente ocluídos. Uma caixa retangular
  não separa bem esse primeiro plano da escada.
- `IMG_3072` a `IMG_3074`: há margem com parede/patamar ao redor dos degraus.
  A definição da borda da escada precisa ser consistente. As caixas da
  escadaria do primeiro local parecem cobrir a maior parte dos degraus, mas
  ainda exigem revisão humana.

As anotações que geraram o peso piloto **não foram alteradas**, para preservar
a proveniência do resultado. O parecer local sem pixels está em
`results/issue16-box-review.json`. Antes de novo treino, revisar cada caixa
com uma pessoa responsável, definir se patamar/piso plano entra no alvo e
obter descidas com menos oclusão de sapato. As pranchas contêm fotos privadas,
ficam fora do Git e não são material de publicação.

Bryan acrescentou seis fotos próprias ao catálogo local: duas de corredor,
duas de piso plano e duas vistas de uma rampa contínua, todas sem escada
visível. Foram avaliadas **somente como cenas negativas** com `imgsz=640`, CPU
e `conf=0.10`, sem retreino ou ajuste de limiar. Tanto o peso original OIV7
quanto o peso do primeiro piloto produziram **0 caixas de escada em 6 fotos**;
portanto, também não há caixa que passe pelo limiar padrão `0.35` nesse lote.
Os pares ida/volta mostram as mesmas cenas, não seis locais independentes.
O resultado não demonstra baixa taxa de falsos positivos na prática, e o peso
piloto ainda falha em cenas positivas. O registro local sem pixels está em
`results/issue16-negative-photos.json`. O manifesto local agora tem 31 fotos;
essas seis já foram usadas nesta análise, portanto não são teste final intocado.
Nenhuma foto, prancha ou peso foi versionado.

### Caixas revisadas e comparação de duas etapas — 2026-09-29

Bryan pediu a correção das anotações e uma comparação que mantivesse as classes
do peso original. Foi criada **uma segunda versão local** em
`datasets/issue16-pilot/annotations-revised-v2.json`, sem sobrescrever as
anotações nem o peso do primeiro treino. A inspeção visual das pranchas locais
`results/issue16-revised-boxes-*.png` confirmou que as novas caixas se
concentram nos degraus: reduziram piso plano junto às subidas e deixaram os
sapatos fora das caixas das quatro descidas da casa. Corrigir a caixa não
remove a oclusão presente na foto nem equivale a aprovação humana do rótulo.
As imagens `IMG_3075` a `IMG_3077` permanecem excluídas por privacidade. As
quatro fotos novas de duas escadas também receberam caixas nesta versão.

O ensaio reproduzível em `scripts/issue16_direction_probe.py` conserva o
`yolov8n-oiv7.pt` de **601 classes** para detectar objetos. Em uma segunda
etapa, extrai vetores do recorte da escada dos mapas internos desse mesmo
modelo congelado e aprende dois centros (`up` e `down`) com as fotos de treino.
O segundo estágio **não muda o peso original**, mas exige uma passagem
adicional por ele. A diferença de similaridade entre os centros não é uma
probabilidade calibrada; ainda não há critério confiável para devolver
`unknown`. Esta implementação é apenas um experimento offline, sem integração
com a #21, contrato ou alerta local.

Foram usadas 16 fotos para aprender os centros (11 subidas, 5 descidas) da
casa e da escada interna nova. A comparação descritiva usou 6 fotos de duas
outras escadas (2 subidas, 4 descidas) e as 6 cenas negativas, agrupadas por
escadaria/cena. Várias fotos são quase duplicadas. Todos esses dados já tinham
sido vistos em análises exploratórias anteriores; **não são teste final
intocado**, e a independência física entre os locais novos não foi confirmada.
Parâmetros fixos nesta execução: CPU, `imgsz=640`, `conf=0.35` para os
detectores; nenhum limiar foi ajustado com as fotos de comparação.

| Abordagem | Resultado nas 6 fotos com escada | 6 cenas sem escada | Classes originais |
|---|---|---|---|
| OIV7 original sozinho | Detectou `Stairs` em 2; sentido sempre `unknown` | 0 caixas `Stairs` | 601 |
| Primeiro peso de 2 classes | 0 detecções | 0 detecções | 2 |
| OIV7 + classificador de recorte | Classificou corretamente as 2 escadas que OIV7 detectou; nas outras 4 não houve recorte para classificar | 0 chamadas de classificação; OIV7 deu 0 caixas `Stairs` | 601 preservadas |

Para separar os erros das duas etapas, o classificador também recebeu os
**recortes das caixas revisadas por inspeção visual**, mesmo onde o detector falhou: classificou
5/6 no sentido esperado; errou a descida da escadaria externa, chamando-a de
subida. Esses números são contagens do lote, não precisão generalizável. A
falha principal do fluxo completo continua sendo a detecção de escadas vistas
de cima. O primeiro peso especializado também não melhora isso. O resultado
**não autoriza integrar a classificação de sentido nem anunciar a #16 como
concluída**.

Para reproduzir no laboratório local, com o ambiente Ultralytics já instalado:

```sh
python scripts/issue16_direction_probe.py \
  --annotations datasets/issue16-pilot/annotations-revised-v2.json \
  --original yolov8n-oiv7.pt \
  --pilot runs/issue16-pilot/first-training/weights/best.pt \
  --output results/issue16-direction-probe-v2.json
```

O JSON gerado contém apenas IDs e números, sem pixels; fica ignorado pelo Git.
Uma próxima comparação precisa de fotos independentes de descida sem oclusão,
anotações revistas por pessoa responsável e regra de `unknown` definida antes
do teste. Também deve medir o custo da segunda inferência na VM e preservar as
outras classes/contrato ao integrar, se os resultados justificarem a escolha.

### Piloto adicional: detector binário em paralelo — 2026-09-29

Para verificar o gargalo da detecção, um segundo detector foi ajustado **apenas
para presença de `stairs`**, a partir do mesmo OIV7. O treinamento remapeou a
classe `Stairs` pré-treinada para a única classe de saída e preservou os demais
parâmetros transferíveis. O novo peso, por si só, possui **uma classe**; a
proposta comparada é executá-lo em paralelo com o OIV7 original de 601 classes
e usá-lo somente quando o original não detecta escada. Nenhum peso original ou
código de produção foi modificado.

O conjunto local `datasets/issue16-binary-v1/` contém **links** para as fotos
em Downloads e rótulos derivados de `annotations-revised-v2.json`. A escada da
casa forneceu 14 fotos de treino, a escada interna nova forneceu 2 de validação
(uma subida e uma descida), e 6 fotos de duas outras escadas mais 6 cenas sem
escada ficaram para comparação. As três imagens com possíveis dados pessoais
foram excluídas. Treino: Ultralytics `8.4.137`, CPU, 20 épocas, `imgsz=640`,
batch 4, seed 16, mosaic 0. O peso local
`runs/issue16-binary-v1/train/weights/best.pt` tem SHA-256
`4e3c712aa1f1ac6c6b0f7010b76591045c7a235c4ed73e1615fd0763498047cd`.
O mAP50 da validação interna chegou a `0.828`, **sobre apenas duas fotos da
mesma escada**; isso não é evidência de generalização.

Com `conf=0.35` no lote de comparação, o binário encontrou escada em **1/6**
fotos positivas (uma subida), enquanto o OIV7 original encontrou **2/6**
(duas subidas). A combinação original + binário manteve **2/6**: não recuperou
nenhuma das quatro descidas. Em seis fotos negativas, ambos tiveram zero caixas
`Stairs`. Em verificação diagnóstica com `conf=0.10`, o binário reconheceu uma
descida do próprio treino e a descida de validação, mas nenhuma das descidas
inspecionadas de outra escadaria. O resultado é compatível com ajuste excessivo
às cenas conhecidas; não atribuímos uma causa única sem mais dados.

O comparador aceita `--specialist runs/issue16-binary-v1/train/weights/best.pt`
no comando acima. A saída local sem pixels está em
`results/issue16-binary-hybrid-v1.json`. Os pesos, links, labels e resultados
ficam ignorados pelo Git. **Este piloto não melhora o fluxo nas cenas
reservadas e não será integrado.** O próximo dado que realmente falta são
descidas de mais escadarias e condições, sem o sapato cobrindo os degraus, além
de negativos de outros locais; coletar pares subida/descida da mesma escada
ajuda a separar sentido de textura/local. Repetir fotos quase idênticas da mesma
escada não substitui essa diversidade. Antes de aceitar um modelo, a #7 ainda
precisa fechar protocolo e critérios de avaliação.

### Lote próprio de 50 cenas e comparação por local — 2026-09-29

Bryan colocou `cenas-escadas-50/` em Downloads e informou que as 50 imagens
são suas, podem ser usadas em treino/teste **locais** e que cada número
representa um local diferente. Há 30 escadas vistas de cima (`down`), 10 vistas
de baixo (`up`), 5 rampas e 5 corredores (`none`). A inspeção visual confirmou
as categorias gerais; ainda não há caixas aprovadas por uma pessoa do grupo.
O catálogo local com hashes e split fica em
`datasets/issue16-new50/manifest.json`, ignorado pelo Git.

Com `imgsz=640`, CPU e o limiar padrão `conf=0.35`, o OIV7 original marcou
`Stairs` em **22/30 descidas**, **9/10 subidas** e **0/10 negativos**. O primeiro
detector binário, treinado nas escadas anteriores, marcou respectivamente
**6/30**, **7/10** e **0/10**. As caixas do OIV7 nas pranchas locais
`results/issue16-new50-oiv7-boxes-*.png` em geral cobrem degraus por inspeção;
isso não substitui IoU contra caixas aprovadas. São contagens deste lote, não
estimativas de desempenho em uso. Registro sem pixels:
`results/issue16-new50-baseline.json`.

O classificador de sentido treinado no lote antigo acertou as **9 subidas**
detectadas pelo OIV7, mas chamou de subida **todas as 22 descidas** detectadas.
O resultado rejeita a hipótese de que os poucos exemplos anteriores já
generalizavam (`results/issue16-new50-direction-probe.json`).

Antes do novo ajuste, foi fixado um split de **33 locais para treino**
(21 descidas, 7 subidas, 5 negativos) e **17 para comparação**
(9 descidas, 3 subidas, 5 negativos). A primeira leitura acima já usou os 50;
portanto, a comparação **não é teste final intocado**. Para o classificador de
sentido, somente 21 fotos de treino tinham caixa OIV7 acima de `0.35`
(15 descidas, 6 subidas). Com o mesmo método de centros e o OIV7 congelado, ele
acertou **7/10 sentidos entre escadas detectadas** na parte reservada. O
detector não encontrou as outras 2 escadas. Errou duas descidas como subida e
uma subida como descida; `unknown` continua sem limiar calibrado. O ensaio está
em `scripts/issue16_new50_probe.py`, com relatório local sem pixels em
`results/issue16-new50-trained-direction.json`.

Um detector binário **novo** foi treinado para tentar recuperar essas descidas.
O conjunto local `datasets/issue16-new50/binary-v2/` usa links para Downloads
e caixas **provisórias**: propostas pelo OIV7 quando havia detecção, ou
estimadas pela IA em sete exemplos sem caixa. Precisam de revisão humana antes
de serem tratadas como ground truth. Dentre os 33 locais de treino do catálogo,
27 entraram no treino desse detector (24 escadas, 3 negativos) e 6 ficaram na
validação (4 escadas, 2 negativos). Os 17 locais de comparação ficaram fora.
Configuração: Ultralytics `8.4.137`, 20 épocas, CPU, `imgsz=640`, batch 4,
seed 16, mosaic 0. O peso local
`runs/issue16-new50-binary-v2/train/weights/best.pt` tem SHA-256
`f6cbfafeeb1ffbdd24041e56e1547e7aa9e7f18bd7c1d7a20d13d8658e5c7f1c`.
O mAP da validação de apenas 6 fotos **não** é critério para integrar.

| Grupo reservado | OIV7 original | Binário novo | OIV7 + binário como fallback |
|---|---:|---:|---:|
| 12 fotos com escada | 10 detectadas | 11 detectadas | 12 detectadas |
| 5 fotos sem escada | 0 caixas `Stairs` | **2 falsas caixas** | **2 falsas caixas** |

As duas escadas recuperadas pelo binário eram descidas e o classificador de
sentido acertou ambas. No fluxo combinado, **9/12** sentidos esperados saíram
corretos, **3/12** saíram errados, além dos **2 falsos alertas**. As falsas
caixas foram uma rampa de garagem (`41`, score `0.587`) e um corredor de hotel
(`47`, score `0.935`); a inspeção de
`results/issue16-new50-specialist-cases.png` confirmou que não havia degraus.
Alterar o limiar depois de ver esses casos não constituiria validação. O
relatório sem pixels está em `results/issue16-new50-hybrid-v2.json`.

O novo peso **não será integrado**: recupera dois casos difíceis, mas cria
falsos alertas com confiança alta, e o sentido ainda erra. Precisamos obter
aprovação humana das anotações, ampliar negativos difíceis e reservar
locais novos depois de congelar modelo, limiar e política de `unknown`. Nenhum
firmware, contrato ou API foi alterado; o alerta tátil geométrico local segue
independente desta pesquisa visual.

### Revisão de todas as caixas do novo conjunto — 2026-09-29

Após a inspeção inicial por amostra, a IA conferiu visualmente as **28 caixas
positivas de treino e validação**. Manteve 13 e corrigiu 15 que incluíam piso
plano, começavam depois dos primeiros degraus ou cortavam parte da escada.
O antes/depois de cada caixa está em
`datasets/issue16-new50/binary-v3-agent-reviewed/box-review.json`; as quatro
pranchas locais com as caixas desenhadas estão em
`results/issue16-new50-reviewed-boxes-{1,2,3,4}.png`. São anotações revisadas
pela IA, **não ground truth independente aprovado por uma pessoa**. As 5 fotos
negativas de treino/validação continuam com rótulo vazio. Os 17 locais de
comparação não receberam caixas nem entraram no novo treino. Foram
verificados os hashes das 50 fotos e a ausência de caixas nesses 17 locais.

Repetiu-se o treino a partir do OIV7 original, com os mesmos 20 ciclos e
parâmetros do binário anterior, alterando somente as caixas de treino e
validação. Peso local:
`runs/issue16-new50-binary-v3-agent-reviewed/train/weights/best.pt`, SHA-256
`b93a73f99c00e768eae2b11c36e62c1a3e737c90525ccb21225c7e9ca8d35b94`.
Comparação exploratória nos mesmos 17 locais já observados:

| Grupo | OIV7 original | Binário v2 | Binário com caixas revisadas |
|---|---:|---:|---:|
| 12 fotos com escada: detecções | 10 | 11 | 10 |
| 5 fotos sem escada: falsas detecções | 0 | 2 | 2 |
| Combinação OIV7 + binário: detecções de escada | — | 12/12 | 10/12 |
| Combinação OIV7 + binário: sentidos corretos | — | 9/12 | 7/12 |

O novo binário deixou de detectar as descidas `14` e `29`, recuperadas pela
versão anterior. Continuou produzindo caixas falsas na rampa `41` e no
corredor `47`. Portanto, revisar as caixas **não resolveu os falsos alertas**
e mostrou que o piloto é sensível às anotações com tão poucas fotos. O
relatório local é `results/issue16-new50-hybrid-v3-agent-reviewed.json`.
Esses 17 locais já tinham sido usados em análises anteriores: nenhum dos
números acima é uma medida final de generalização. Não integrar esse peso;
antes de outro ajuste, obter mais negativos difíceis, revisão humana dos
rótulos e novos locais realmente não vistos para avaliação.

### Mais 20 locais para treino exploratório — 2026-09-29

Bryan adicionou `cenas-proximo-treino-20/` em Downloads e confirmou autoria,
permissão para treino local e **um local diferente por foto**. São 4 rampas,
4 corredores, 4 pisos planos com padrões que podem parecer degraus e 8 escadas
vistas de baixo. Os hashes das 20 fotos foram registrados em
`datasets/issue16-new70-binary-v4/new20-manifest.json`; não houve duplicata
exata nem candidata próxima pelo hash perceptual simples entre elas e as 50
anteriores. As imagens não entram no Git.

Antes do treino, nessas 20 cenas, o OIV7 original detectou **7/8 escadas**
e marcou **1/12 cenas negativas** (sombras de pergolado). Os binários v2/v3
detectaram **8/8 escadas**, mas marcaram respectivamente **9/12** e **5/12
negativos**. Relatório local: `results/issue16-new20-baseline.json`.

As 8 caixas positivas foram inspecionadas visualmente: 7 propostas pelo
OIV7 e uma estimada pela IA na escada metálica sem detecção OIV7. A prancha
local é `results/issue16-new20-reviewed-positive-boxes.png`. Os 12 negativos
têm rótulo vazio. A versão v4 usa as 33 imagens antigas de treino/validação
e as 20 novas: **43 imagens de treino e 10 de validação**, por locais
distintos. Os 17 locais antigos de comparação seguem fora do ajuste. Quatro
novos locais (2 negativos, 2 escadas) foram para validação, mas ainda contam
como dados usados na escolha do peso. As caixas são revisadas pela IA, não
ground truth independente.

Treino v4: ponto de partida OIV7 original, Ultralytics `8.4.137`, 20 épocas,
CPU, `imgsz=640`, batch 4, seed 16, mosaic 0. Peso local:
`runs/issue16-new70-binary-v4/train/weights/best.pt`, SHA-256
`64811c49dce7fe1ab597c5f45afa6100762b912ccafa999e63a52e70eeb4e7c6`.

| Comparação nos 17 locais antigos | OIV7 | Binário v3 | Binário v4 |
|---|---:|---:|---:|
| Escadas detectadas entre 12 | 10 | 10 | 9 |
| Falsas detecções entre 5 negativos | 0 | 2 | 0 |
| Cascata OIV7 + binário: escadas detectadas | — | 10/12 | 11/12 |
| Cascata OIV7 + binário: sentidos corretos | — | 7/12 | 8/12 |

O relatório é `results/issue16-new50-hybrid-v4.json`. A cascata v4 ainda
perdeu a descida `14` e errou o sentido em três cenas. Nas **20 fotos de
treino/validação**, o próprio v4 detectou 7/8 escadas e marcou 2/12 negativos,
incluindo a faixa tátil da praça com confiança `0.833`; esse é resultado de
ajuste, não teste independente (`results/issue16-new20-fit-v4.json`).

Também foi acrescentado ao classificador de sentido por centros um conjunto
de **6** recortes novos de subida que pertencem ao treino; os dois novos
recortes de validação ficaram fora. Nos mesmos 17 locais antigos, a cascata
v4 passou de 8/12 para **7/12 sentidos corretos**, sem mudar o detector.
Relatório: `results/issue16-new50-hybrid-v4-extra-direction.json`. Portanto,
mais vistas de subida neste método não bastaram para separar o sentido.

**Decisão do piloto:** não integrar o peso v4 nem a classificação de sentido.
O conjunto antigo já foi observado em várias iterações e os 20 novos foram
usados para treino/validação. A #7 precisa aprovar o protocolo, tamanho e
limiares antes de novos locais inteiramente reservados para avaliação. Também
faltam revisão humana das caixas e cenas com movimento e variação de luz.
Nenhuma mudança de visão, API ou firmware foi feita; o feedback tátil local
permanece independente da VM.

### Treino direto de subida/descida com duas classes — 2026-09-29

Para testar um caminho alternativo ao classificador de recortes, treinou-se
outro YOLO a partir do OIV7 original, com as **mesmas 43 imagens de treino e
10 de validação** do conjunto v4. As 36 caixas de escada receberam classe
`stairs_up` (15) ou `stairs_down` (21); 17 imagens sem escada mantiveram
rótulo vazio. O conjunto local está em
`datasets/issue16-new70-direction-v1/`, com origem e separação registradas em
`provenance.json`. Treino: Ultralytics `8.4.137`, 20 épocas, CPU,
`imgsz=640`, batch 4, seed 16, mosaic 0. Peso local:
`runs/issue16-new70-direction-v1/train/weights/best.pt`, SHA-256
`c687e4c9f967eade4a676a0f63c6409ed535105f133256a446364d2776a2535e`.

Com o limiar fixo `0.35`, nos **17 locais antigos já vistos em pilotos**:

| Saída direta do modelo de duas classes | Resultado |
|---|---:|
| 12 fotos com escada: sentido correto | 7 |
| 12 fotos com escada: sentido errado | 1 |
| 12 fotos com escada: sem detecção | 4 |
| 5 fotos sem escada: falsa detecção | 0 |

O erro foi uma descida de trilha (`20`) classificada como `up` com confiança
`0.7921`; por isso, a confiança do detector sozinha não fornece uma regra
segura de `unknown`. O modelo também perdeu a subida de escada metálica (`34`)
e duas descidas que o OIV7 original já perdia (`14`, `29`). Nas **20 fotos
novas usadas para treino/validação**, acertou 7/8 subidas e 0/12 negativos,
mas perdeu a escada escura do cinema (`14`) que ficou na validação. Esses
números medem ajuste/validação, não generalização independente.

Uma combinação conservadora usa o OIV7 original para presença e o modelo de
duas classes somente para sugerir sentido onde ambos marcam a mesma escada.
Neste lote, as oito caixas de direção encontradas se sobrepuseram às caixas
OIV7 (IoU de `0.7592` a `0.9498`). Entre as dez escadas encontradas pelo
OIV7, isso renderia **7 sentidos corretos, 1 errado e 2 `unknown`**; outras
duas escadas permaneceriam sem detecção. Essa combinação é **análise offline**,
não uma política implementada nem critério de aceitação. O avaliador
`scripts/issue16_two_class_probe.py` gera
`results/issue16-new50-direction-two-class-v1.json`; o ajuste nas novas cenas
está em `results/issue16-new20-direction-two-class-fit.json`.

Não substituir o peso multiclasse do módulo por esse peso de duas classes:
isso perderia as outras classes já suportadas. Ainda falta teste independente,
anotação humana e uma regra de abstenção capaz de tratar inclusive erros de
alta confiança. Nenhum peso foi integrado ou versionado.

### Primeiro teste reservado em 30 cenas — 2026-09-29

O lote `teste-independente-30-locais` contém 10 imagens rotuladas `up`, 10
`down` e 10 sem escada. Bryan informou que fotografou 30 locais reais e
autorizou o teste local. **Há uma ressalva de procedência:** na catalogação
inicial, `LEIA-ME.txt` e `rotulos.csv` diziam que as imagens eram geradas por IA.
Bryan corrigiu essa informação na conversa antes da inferência; os dois
arquivos da pasta foram corrigidos depois da primeira execução. O catálogo
local conserva as declarações originais e a correção, sem prova independente
da captura. Por isso, este lote serve como diagnóstico de imagens inéditas,
mas não como evidência verificada de validação em campo.

Antes de abrir os pixels, foram congelados pesos, hashes, regras e limiares em
`datasets/issue16-blind30/protocol-frozen.json`. O OIV7 original indica
presença de escada; o peso local de duas classes só indica sentido quando uma
caixa sua coincide com a caixa `Stairs` de maior confiança do OIV7 com IoU
`>= 0.5`. Sem caixa OIV7, a saída é `none`; sem sentido coincidente ou com
sentidos conflitantes, é `unknown`. Ambos usam confiança `0.35`, `imgsz=640` e
CPU. Não houve ajuste de limiar ou treino neste lote após ver os resultados.

| Primeira passada | Resultado |
|---|---:|
| Escadas presentes nas 20 cenas positivas (OIV7) | 11/20 |
| Sentido correto (`up` ou `down`) | 3/20 (2 `up`, 1 `down`) |
| Sentido errado | 0/20 |
| Escada detectada, sentido `unknown` | 8/20 |
| Escada não detectada | 9/20 |
| Cenas negativas com falso alerta de escada | 1/10 |

O falso positivo é a imagem `29`: sombras paralelas sobre tábuas planas foram
interpretadas como escada pelo OIV7 (`0.857`); a saída combinada ficou
`unknown`. A inspeção visual confirmou degraus na imagem `11`, que foi perdida
pelo detector. As 30 imagens e rótulos receberam inspeção visual diagnóstica;
isso não substitui anotação de caixas revisada por outra pessoa. Resultado
imutável da primeira passada em `results/issue16-blind30-first-pass.json`,
gerado por `scripts/issue16_blind30_probe.py`; catálogo, resultados e imagens
permanecem locais e ignorados pelo Git.

O resultado mostra generalização insuficiente para integrar a sugestão de
sentido ao módulo ou concluir a #16. Estas imagens já foram vistas na análise:
qualquer treino ou escolha de regra com elas exige **outro** lote reservado
para a próxima avaliação. A #7 ainda precisa definir critérios de aceitação e
avaliação de campo, inclusive localização das caixas, vídeo e latência.

### Iteração de treino com 70 e 100 locais

Após reservar outro lote, os 17 antigos locais de teste já expostos do
conjunto de 50 foram promovidos para treino. Suas 12 caixas positivas foram
inspecionadas visualmente e continuam **anotações provisórias da IA**. O
conjunto de 70 locais ficou com 60 imagens de treino e 10 de validação,
preparado por `scripts/issue16_prepare_full70.py` em
`datasets/issue16-full70-direction-v2/`. Um detector de duas classes foi
treinado por 20 épocas na CPU, inicializado do OIV7 original; o peso ficou em
`runs/issue16-full70-direction-v2/train/weights/best.pt`. No lote anterior
de 30 cenas, visto somente depois desse treino, acertou o sentido nas 20
escadas, mas produziu **4 falsos positivos entre 10 negativos**. Isso revela
o custo de aceitar diretamente suas caixas de direção como presença de
escada; validação interna com apenas 10 imagens não mostrou esse problema.
O resultado de desenvolvimento está em
`results/issue16-full70-v2-old30-development.json`. Esse lote já havia sido
testado em versões anteriores, portanto não é avaliação final independente.

Bryan autorizou promover as 30 imagens desse lote anterior para **treino
local**. Foram anotadas 20 caixas positivas por inspeção visual, usando
propostas OIV7 quando adequadas e caixas manuais/corrigidas nos demais casos;
10 cenas negativas receberam rótulo vazio. As caixas e sua origem estão em
`datasets/issue16-full100-direction-v3/provenance.json`, geradas por
`scripts/issue16_prepare_full100.py`. Este conjunto tem 90 imagens de treino
e 10 de validação. Não contém nenhuma das 30 imagens da próxima avaliação,
confirmado por hashes. A procedência das 30 imagens promovidas conserva a
ressalva documental descrita acima. A localização das caixas ainda depende de
revisão humana independente.

O detector v3 foi inicializado do peso v2 e treinado por mais 15 épocas na CPU
com Ultralytics `8.4.137`, `imgsz=640`, batch 4 e seed 16. Peso local:
`runs/issue16-full100-direction-v3/train/weights/best.pt`, SHA-256
`f994774639c5f13bfba0717c0cdc3ead762cc48b8a25d6d90f7b1facffee9a2e`.
No lote de 30 promovido a **treino**, o ajuste foi 20/20 sentidos corretos e
1/10 falso positivo; esse resultado não mede generalização.

### Primeira avaliação da versão v3 no próximo lote

Bryan entregou `proxima-avaliacao-30-locais` com 10 rótulos `up`, 10 `down` e
10 `sem_escada`. Os 30 arquivos são distintos entre si e não têm hash igual
às 100 imagens dos três lotes anteriores. O catálogo local com hashes está em
`datasets/issue16-next30/manifest.json`. Bryan confirmou que são fotos
próprias de 30 locais reais diferentes dos lotes anteriores, autorizadas
somente para teste local; a captura e a independência física dos locais não
foram verificadas por outra fonte. **Nenhuma imagem desse lote entrou no
treino ou na escolha do modelo.** Antes de abrir os pixels, foram congelados
os hashes dos pesos, confiança `0.35`, `imgsz=640`, CPU e regras em
`datasets/issue16-next30/protocol-frozen.json`.

O candidato v3 indica `up` ou `down` quando suas detecções têm somente uma
dessas classes; se houver ambas, indica `unknown`; sem detecção, `none`.
Como referência, repetiu-se a combinação antiga OIV7 + modelo v1 com IoU
`>= 0.5` e as mesmas regras do primeiro teste de 30. Ambos foram executados
uma vez, sem ajuste posterior, por `scripts/issue16_next30_probe.py`.

| Primeira passada nas 30 cenas | Candidato v3 | Referência OIV7 + v1 |
|---|---:|---:|
| Sentido correto nas 20 escadas | 17 | 6 |
| Sentido errado | 0 | 1 |
| Escada detectada, sentido `unknown` | 1 | 6 |
| Escada não detectada | 2 | 7 |
| Falsos positivos nas 10 cenas negativas | 0 | 1 |

Por sentido, o v3 acertou 8/10 subidas e 9/10 descidas. A imagem `01` contém
escada que sobe, mas gerou caixas `up` e `down` sobre ela, resultando em
`unknown`; `02` (subida) e `11` (descida) não geraram caixas. A inspeção visual
das 30 cenas confirmou esses rótulos e que as caixas positivas restantes
abrangem escadas. Não há caixas de referência independentes para calcular IoU
ou precisão de localização. O resultado imutável da primeira passada está em
`results/issue16-next30-first-pass.json`; as pranchas de inspeção ficam em
`results/issue16-next30-audit-{1,2}.png`. Esses arquivos, fotos e pesos não
estão versionados.

A melhora é promissora **para este piloto de imagens**, mas 30 cenas não
estabelecem taxa de erro operacional. A #7 ainda precisa definir os critérios
quantitativos e o protocolo de campo; faltam vídeo, latência ponta a ponta,
caixas revisadas por outra pessoa e avaliação no enquadramento/câmera do
protótipo. O peso v3 contém só `stairs_up/down`: substituí-lo diretamente pelo
detector multiclasse do módulo eliminaria as demais classes. A integração
opcional abaixo preserva o detector geral; ativação padrão ainda depende da #7.

### Compatibilidade com a interface visual existente

O módulo da #21 já aceita explicitamente qualquer peso `.pt` de detecção local
compatível. Um teste de execução do OIV7 original via `UltralyticsFactory` e
`VisionService`, com a foto própria `13-escada-terminal-balsa-baixo.png`,
produziu um objeto `stairs` com confiança `0.7527` e
`stair_direction=unknown`. Isso comprova a passagem pela interface e o
contrato sem alteração de código ou de peso padrão; não comprova qualidade
de detecção nem sentido. O procedimento opcional está em
[`docs/vision.md`](../vision.md). O binário v4 continua apenas no laboratório.

### Integração opcional na interface da #21

`UltralyticsFactory` agora aceita um segundo peso local
`stair_direction_weights` com classes `stairs_up/stairs_down`. O detector geral
e seu ByteTrack continuam fornecendo as demais classes; a segunda etapa
acrescenta escadas sem correspondência, ou sentido às caixas `stairs` já
encontradas. Conflitos resultam em `unknown`. Escadas encontradas só pelo
segundo peso ficam com `track_id=null`. `Result.observation()` transmite o
sentido no campo **já existente** do contrato. Sem o peso opcional, o
comportamento anterior (`unknown` para escadas) permanece. A arquitetura e o
limiar experimental de associação estão em [ADR 0005](../decisions/0005-sentido-escadas-opcional.md).

Um smoke test real com YOLOv8n como detector geral e v3 como segundo peso
produziu `up` na imagem `03`, `down` nas imagens `12` e `17` e nenhuma escada
na negativa `27`. Nas 30 imagens já abertas, o caminho integrado repetiu
17/20 sentidos corretos, 1 `unknown`, 2 perdas e 0/10 falsos positivos;
houve também 10 detecções não escada do detector geral. O relatório local é
`results/issue16-next30-integrated-coco-posthoc.json`. Essa é uma verificação
**posterior** da integração com imagens expostas, não outra avaliação
independente. Testes sem pesos cobrem serialização, associação e conflito;
testes com o peso real permanecem locais. O peso não é versionado nem ativado
automaticamente. Ainda faltam latência em vídeo/VM, caixas humanas e os critérios
da #7 antes de propor uso padrão.

O benchmark sem câmera, em imagens pretas de `480×640`, com 5 frames de
aquecimento e 20 medidos no Mac local (CPU), registrou P50/P95 de
`51,1/84,4 ms` com YOLOv8n geral e `81,6/90,3 ms` com o segundo peso v3.
É uma única execução curta; os relatórios locais estão em
`results/issue16-coco-blank-benchmark.json` e
`results/issue16-coco-plus-stairs-blank-benchmark.json`. Ela demonstra o
custo adicional nesta máquina, **não** latência da VM, API, rede, câmera ou
vídeo real. A opção `--stair-direction-weights` foi adicionada ao benchmark
do módulo para repetir a medição com pesos locais autorizados.

## Protocolo de avaliação proposto

Na #7, reservar cenas **independentes** por escadaria/local e sessão para teste;
registrar câmera, altura/inclinação, distância aproximada, movimento, resolução,
iluminação observada (boa, baixa, noite iluminada), oclusão, material/contraste
dos degraus e presença de pessoas. Incluir subida, descida e negativos difíceis
(linhas de piso, rampas, arquibancadas, bordas e sombras). Não inventar faixas
de lux ou metros quando não medidos.

Comparar caixas com anotações pelo critério de correspondência/IoU que o grupo
aprovar. Reportar separadamente por condição e por sentido:

- presença de escada: verdadeiros positivos, falsos negativos e falsos
  positivos em cenas negativas, com precision/recall e denominadores;
- sentido **somente entre escadas corretamente localizadas**: matriz
  `up/down/unknown`, confusões `up↔down` e taxa de abstenção. `unknown` não conta
  como acerto; ausência de detecção é falso negativo, não abstenção;
- latência média/P50/P95/P99, FPS, CPU/RAM e versão/configuração/peso, inclusive
  custo extra de uma segunda etapa. Separar decodificação e inferência, sem
  chamar teste local de latência ponta a ponta da VM.

Publicar também exemplos de falha **sem mídia pessoal** ou por acesso autorizado
ao grupo. Selecionar limiar de score e regra de `unknown` apenas com treino/ajuste;
congelá-los antes do teste independente. Reportar intervalos de incerteza quando
o tamanho da amostra permitir, sem transformar amostras correlacionadas de um
mesmo vídeo em observações independentes.

## Próximo artefato verificável

O piloto já tem dois testes reservados de 30 cenas, mas suas imagens foram
abertas e agora servem apenas para análise de falhas ou, com autorização,
ajuste futuro. Antes de marcar a #16 como feita, a #7 deve aprovar os critérios
de aceitação e um protocolo com caixas humanas, negativos difíceis, vídeo e
latência. A integração opcional preserva o detector multiclasse e entrega
`up/down/unknown/null` pelo contrato em testes locais; resta validá-la sob o
protocolo aprovado sem alterar risco, TTC ou vibração locais. Um teste posterior
de decisão precisará de cenas inéditas.
