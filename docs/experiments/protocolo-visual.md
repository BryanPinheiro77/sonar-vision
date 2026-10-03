# Protocolo de coleta e avaliação visual — #7

- Data: 2026-10-01. Responsável previsto: Matheus (@Matheus-xz).
- Status: proposta para revisão; coleta real e aprovação experimental pendentes.
- Issue: [#7](https://github.com/BryanPinheiro77/sonar-vision/issues/7).
- Fontes: [escopo aprovado](../ESCOPO.md), [contrato 0.1](../protocol/eventos-semanticos.md),
  [ADR 0003](../decisions/0003-eventos-semanticos.md), [visão](../vision.md).
- Evidência anterior: [laboratório da #21](issue-21.md).
- Instrumentação: src/sonar_vision/evaluation_manifest.py e tests/test_evaluation_manifest.py.

## Entrega e limites

A #7 define cenários, coleta, anotação e comparação reproduzíveis. O escopo
confirmado exige oito classes prioritárias, escadas e condições variadas.
Procedimentos, formato de metadados e associação descritos aqui são propostas
para revisão; nenhum limiar numérico novo foi aprovado pelo grupo.

Nesta entrega existe um exemplo **sintético de metadados**, não um vídeo.
O validador não cria imagens, grava pessoas, executa modelos nem calcula acurácia.
Vídeos reais, anotações e permissões não estão disponíveis neste checkout.
Os testes locais validam a ferramenta e o procedimento estrutural.

## Matriz de cenários e coleta proposta

| ID | Cenário | Procedimento e referência |
|---|---|---|
| C01 | Aproximação | Câmera inicialmente fixa; alvo reduz distância entre marcas medidas, sem risco de contato; registrar trajetória e início/fim |
| C02 | Afastamento | Percurso inverso, mesmas marcas/configuração; registrar objeto saindo da cobertura |
| C03 | Cruzamento lateral | Alvo percorre esquerda–direita e direita–esquerda diante da câmera; não chamar isso de cruzamento da caminhada |
| C04 | Oclusão | Ocultação parcial e completa por anteparo; anotar intervalos visíveis/ocultos e retorno, sem pressupor identidade preservada |
| C05 | Múltiplos alvos | Dois ou mais alvos em cruzamento e cena estática; anotar cada identidade e trocas de associação |
| C06 | Escada de subida | Câmera observa lance de baixo para cima, em posição protegida; ninguém depende do protótipo para subir |
| C07 | Escada de descida | Observação de cima para baixo, com proteção/supervisão; incluir ângulos ambíguos e abstenção |
| C08 | Controle negativo | Cena sem classes prioritárias e com fundos/distratores; serve para observar falsos positivos |

Cada cena deve variar condição de iluminação: good (boa), low (baixa) e
public_night (noite com iluminação pública). Esses rótulos descrevem observação,
não faixas de lux. Se houver luxímetro, registrar valor, instrumento, posição e
horário; sem medição, lux=null. Exposição, ganho, foco, borrão, fontes de luz e
movimento da cabeça/câmera devem constar no diário privado da tomada.

Cobrir person, car, motorcycle, bus, bicycle, chair, dining_table e dog.
Crianças pertencem a person; não identificar idade nem recrutar menores nesta
proposta. Stairs exige avaliação separada para up/down/unknown.
Mesas detectadas como dining_table não garantem cobertura de todas as mesas.

Carros, motos, ônibus e bicicletas podem ser filmados parados em local autorizado;
movimento exige área isolada e operador supervisionado. Não encenar aproximação
de veículos em trânsito nem usar brinquedos como substituto silencioso de veículos.
Para cadeira/mesa/escada fixas, movimento da câmera deve ser identificado como
tal, sem tratá-lo como movimento físico do objeto. Animais exigem autorização do
responsável e condições adequadas, sem provocar aproximações perigosas.

O cruzamento integral classe × condição × cenário não é automaticamente viável.
O grupo deve aprovar uma matriz de aplicabilidade: cada célula contém número de
tomadas planejado/coletado ou justificativa de não aplicabilidade, nunca zero
ocultado em média. Incluir cenas com câmera fixa e movimento da cabeça, mantendo
resultados separados. Classes sem detector implementado, como escadas nos pesos
COCO atuais, devem aparecer como capacidade pendente, não ser removidas do escopo.

## Aprovações antes da avaliação final

| Decisão do grupo | Estado atual |
|---|---|
| Matriz de aplicabilidade por classe, cenário e iluminação | Pendente |
| Número mínimo de tomadas independentes por célula, duração e repetições | Pendente |
| Distâncias inicial/final, faixas e tolerâncias de medição | Pendente |
| Critério de iluminação observada e condições medidas | Pendente; sem faixas de lux inventadas |
| Intervalo/regra de seleção de frames e tratamento de frames ilegíveis | Pendente |
| IoU de associação, confiança, tratamento de oclusão e anotação | Pendente |
| Limiares de aceitação por classe/condição e escadas | Pendente |
| Orçamento de latência visual e procedimento de medição integrada | Pendente |
| Responsáveis pela coleta/anotação, revisor e supervisão | Matheus previsto; demais a designar |
| Ética, consentimento, acesso, retenção e descarte | Pendente para coleta real |

Congelar esses parâmetros e registrar referência de aprovação antes de abrir o
teste independente. A meta local <100 ms da #4 e validade de 1000 ms da #12
não constituem limiar aprovado de acurácia ou latência da inferência nesta issue.
Não ajustar parâmetros depois de ver o teste e continuar chamando-o independente.

## Separação das evidências e conjuntos

- Exploratory/exploration: vídeos antigos ou exploração sem controle completo.
  A evidência da #21 permanece nesta categoria; não reclassificar automaticamente.
- Controlled/tuning: tomada planejada usada em ajustes/treino, escolha de modelo,
  confiança, parâmetros de tracker e política.
- Controlled/test: conjunto independente congelado, com referência anotada e
  parâmetros aprovados antes de avaliar. Não selecionar só frames favoráveis.
- Integrated/demo ou integrated/test: protótipo com captura e retorno reais;
  laboratório no computador não comprova uso nos óculos.
- Kind=synthetic, split=synthetic: fixture para software; não conta como vídeo
  coletado, cobertura de classes reais ou evidência de segurança.

source_group_id agrupa a tomada original e todos os seus recortes/transcodificações.
Agrupar também sessões/fontes correlacionadas quando necessário; não dividir
frames vizinhos ou recortes do mesmo vídeo entre tuning e test.
O validador rejeita source_group_id ou SHA-256 compartilhados entre test e
exploration/tuning,
mas não detecta automaticamente recortes com hash novo ou IDs de grupo incorretos.
A revisão humana deve assegurar independência, incluindo atores/locais quando
isso for exigido pelo desenho aprovado. Não publicar IDs pessoais.

## Fluxo reproduzível de uma tomada

1. Obter autorização de uso/gravação, consentimento quando aplicável, supervisão
   e avaliação ética institucional. Registrar revisão, inclusive dispensa formal,
   em armazenamento restrito; consentimento sozinho não substitui avaliação ética.
2. Identificar tomada com ID opaco, procedimento C01–C08 e grupo de origem.
   Registrar data, câmera/modelo, orientação/espelhamento, codec, resolução,
   FPS, duração, cenário, condições e configuração no diário de coleta.
3. Marcar e medir distâncias em metros quando possível. Não estimar distância real
   por tamanho de caixa monocular. Na falta de medida, usar null e justificar em
   measurement_method; registrar instrumento e referência da medida no diário.
4. Gravar após aprovações; interromper diante de risco, retirada de consentimento
   ou presença de terceiros sem autorização. Não depender dos óculos para locomoção.
5. Guardar original privado, calcular SHA-256 e gerar manifesto não identificável.
   Vincular recortes ao grupo original; registrar intervalos/transformações.
6. Anotar/revisar referência, definir split e congelar versão. Registrar exclusões
   e razões antes da avaliação; não descartar falhas retrospectivamente.
7. Rodar validação de metadados. Executar modelos com pesos, software, dispositivo
   e configurações registrados; repetir sobre exatamente as mesmas capturas.
8. Relatar contagens, denominadores, falhas e limitações por classe/condição,
   sem apresentar resultado agregado como aprovação de todas as classes.

## Metadados e armazenamento

Formato local de trabalho v1: [manifest-example.json](manifest-example.json).
Não é contrato de mensagens do ESP32, não altera a versão 0.1.
Approval registra status e referências da aprovação e do protocolo congelado;
o script verifica presença/estrutura, não autenticidade da aprovação.

Cada clip registra ID, source_group_id, kind/stage/split, data ISO,
câmera, width/height, fps/duration_s, scenario, classes, lighting, lux,
distance_start_m/distance_end_m, measurement_method, procedure_id,
sha256, permission_reference, ethics_reference e annotation_reference.
Não incluir nomes, rostos, contatos, caminhos pessoais ou documentos de consentimento.
As referências devem ser códigos internos opacos. O diário privado detalha
configuração, local, horários, medidas, participantes e revisões quando necessário;
manifesto público só após revisão manual de privacidade.

Vídeos e anotações ficam localmente em videos/issue-7/ e datasets/issue-7/,
já ignorados pelo Git. results/ local guarda relatórios; não versionar mídia,
trajetórias identificáveis, datasets ou termos. Essas pastas não são criadas
pela fixture. Conferir regras com git check-ignore antes de qualquer inclusão.
Um caminho ignorado não oferece controle de acesso ou criptografia.

Compartilhamento exige decisão registrada do grupo sobre repositório restrito,
responsável por acesso, participantes autorizados, prazo de retenção, exclusão
e cópia de segurança. Nenhum provedor externo é escolhido nesta entrega.
Até essa decisão, manter os arquivos privados sem upload. Consentimentos ficam
separados da mídia; um termo não deve acompanhar um PR público.

Registrar origem e permissão de cada vídeo. AGPL-3.0-only do projeto não licencia
automaticamente imagens, vídeos, datasets ou pesos. Não redistribuir material de
terceiros ou participantes presumindo licença livre; revisão específica é necessária.

## Anotação e métricas propostas

Referência por frame: clip_id, índice/tempo do frame, classe, caixa na imagem
original, identidade local anotada, visibilidade/oclusão e, para escadas, sentido
up/down/unknown. Identidades são locais à tomada, sem identificação civil.
Registrar versão da anotação e revisão por outro integrante; resolver desacordos
sem usar a predição do modelo como verdade.

Para detecção, associar caixas por classe e IoU com associação um-para-um.
O algoritmo de associação, limiar e regra de empate serão congelados na revisão.
Uma predição só corresponde a uma referência; duplicatas viram FP.
Referência avaliável sem correspondência vira FN; predição sem correspondência
vira FP; correspondência válida vira TP. Classe errada gera FP da classe predita
e FN da verdadeira. Oclusão/ignore e frames ilegíveis exigem regra aprovada;
reportar exclusões e abstenções, sem contá-las como acertos.

Precision=TP/(TP+FP); recall=TP/(TP+FN). Denominador zero produz não aplicável,
não 100%. Informar contagens e denominadores por classe, cenário e iluminação.
AP/mAP exigem anotações e protocolo de confiança/IoU apropriados; não são
calculados por contar detecções ou pelo benchmark de latência atual.
Estas definições seguem a [documentação oficial de métricas Ultralytics](https://docs.ultralytics.com/guides/yolo-performance-metrics/);
não mudam pesos nem dependências do projeto.

Escadas: separar detecção da escada de classificação do sentido. Apresentar
matriz verdade up/down × resposta up/down/unknown e falhas de detecção à parte.
Abstenção e confusão não são acertos; reportar cobertura de respostas e acertos
sobre todas as instâncias avaliáveis, além de resultados condicionais às detectadas.
Não afirmar localização da borda do primeiro degrau.

Tracking: revisar associações contra identidade anotada. Reportar ID switches,
fragmentações e perdas com regra de reassociação/oclusão congelada; não usar
quantidade de IDs nem events lost/recovered do núcleo como métrica de qualidade.
Comparações padronizadas podem seguir [definições do MOTChallenge](https://motchallenge.net/results/MOT17/);
IDF1/HOTA exigem ferramenta/protocolo próprios, não implementados nesta entrega.

Latência: separar detecção/tracking/normalização, decodificação, rede e captura
até alerta. Usar intervalos no mesmo relógio monotônico; não subtrair relógio
da VM do ESP32. Registrar warmup, carregamento excluído/incluído, número de
amostras, média, P50/P95 nearest-rank e FPS=frames/tempo corrido.
Registrar timeouts, descartes, falha de decode e interrupções, sem apagar falhas.
O benchmark existente mede processamento e FPS com decode, sem rede/hardware.
Na integração, verificar expiração desde captura, giro >15 graus e rede/VM
desligadas, mantendo vibração local. Esses testes físicos continuam pendentes.

## Comandos disponíveis e verificação

Na raiz, PowerShell, sem novas dependências:

```powershell
$env:PYTHONPATH = 'src'
python -B -m sonar_vision.evaluation_manifest docs/experiments/manifest-example.json
python -B -m unittest discover -s tests -p test_evaluation_manifest.py -v
python -B -m unittest discover -s tests -v
git diff --check
git check-ignore videos/issue-7/example.mp4 datasets/issue-7/annotations.json
```

Validador: sucesso retorna 0 e resumo estrutural; erro retorna 2, sem imprimir
valores pessoais. Missing_recorded_* representa somente cobertura marginal,
não adequação das combinações, amostras ou qualidade. Metadata_valid não aprova
ética, licença, desempenho ou prontidão para avaliação final.

O benchmark com vídeo autorizado já documentado em ../vision.md pode ser usado
quando mídia e pesos estiverem disponíveis. Não há novo comando de acurácia,
firmware ou deploy inventado aqui. A ferramenta apenas lê manifesto;
não acessa sensores, rede, áudio ou risco, preservando independência tátil.

## Evidência desta entrega

Execução em Windows, Python 3.13.5, em 2026-10-01:

- 14 testes novos do manifesto passaram, incluindo CLI, metadados inválidos,
  separação de fontes, permissões/revisão ética e exemplo sintético.
- Suíte completa: 56 testes encontrados, 52 passaram e 4 testes do ByteTrack
  real foram ignorados por ausência das dependências opcionais.
- CLI sobre manifest-example.json: saída 0, metadata_valid=true,
  approval_status=pending, recorded=0 e synthetic=1.
- git check-ignore confirmou exclusão de videos/issue-7/example.mp4 e
  datasets/issue-7/annotations.json; nenhum desses arquivos foi criado.
- git diff --check sem erros; links locais e espaços finais dos novos
  artefatos foram verificados separadamente.

| Aceitação #7 | Artefato/evidência e pendência |
|---|---|
| Cenas e classes | Matriz C01–C08 e vocabulário; coleta real pendente |
| Iluminação/distância | Registro de condição e valores opcionais medidos; faixas pendentes |
| Metadados | Manifesto v1, CLI e 14 testes sintéticos |
| FP/FN, latência e tracking | Procedimento e definições; avaliação real/anotações pendentes |
| Armazenamento | Pastas locais ignoradas; compartilhamento/retenção a aprovar |
| Ética/consentimento | Pré-requisitos e referências; revisão institucional da coleta pendente |
| Amostras/limiares/teste independente | Lista de aprovações e proteção contra mistura de fontes; quantitativos pendentes |
| Diferenciar evidências | stage/split/kind verificados; nenhum teste integrado realizado |

Nenhum vídeo
real foi coletado ou validado nesta sessão. Coleta, anotações, aprovação dos
parâmetros e avaliação final continuam pendentes; não encerrar #7 com a fixture.

A opção de um documento e manifesto leves evita adicionar framework de datasets
ou serviço de armazenamento antes de necessidade aprovada. O validador oferece
checagens repetíveis de estrutura e separação; revisão manual cobre aquilo que
referências e hashes não comprovam. Não há mudança de arquitetura ou novo ADR.
