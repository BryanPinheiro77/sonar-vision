# #11 — adoção experimental do candidato conservador

Data: 2026-10-28. Responsável: Bryan, com apoio de IA.
[Decisão de adoção](../decisions/0026-tracking-conservador.md).
Escolha operacional explícita; a #11 e a avaliação independente permanecem abertas.

## Evidência exploratória

Nove vídeos privados de iPhone, câmera móvel, total de 3371 frames.
YOLOv8n geral, peso SHA-256
`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`,
Ultralytics 8.4.137, CPU, entrada 640. Não houve treino ou anotação completa
de identidades. As fontes já foram observadas/ajustadas no desenvolvimento;
não constituem teste independente. Mídias e predições por frame ficam privadas.

No caso distante relatado por Bryan, 140 caixas antes distribuídas entre
quatro IDs passaram a um único ID. Nos três controles iniciais, dois
mantiveram seus IDs em todas as caixas de referência; o terceiro teve uma
ausência de um frame e voltou ao mesmo ID. O caso de oclusão continuou
com identidade fragmentada. A correspondência usa caixas idênticas e a
revisão parcial de Bryan, sem provar usos corretos dos IDs fora desses grupos.

Em 11694 observações pessoa/frame, a baseline atribuiu ID a 10594 e o
candidato a 10583. Essas contagens **não** medem pessoas, ID switches,
acurácia ou recuperação correta. O máximo ID emitido também não é métrica
de qualidade. Bryan relatou pouca diferença geral ao assistir à comparação.

## Configuração congelada

| Parâmetro | Perfil anterior | Candidato escolhido |
|---|---:|---:|
| Corte do detector geral | 0.35 | 0.25 |
| Corte da saída | 0.35 | 0.35 |
| ByteTrack high / low / new | 0.25 / 0.1 / 0.25 | 0.35 / 0.25 / 0.35 |
| Buffer / match / fuse_score | 60 / 0.8 / true | 60 / 0.8 / true |
| Margem para recusar reativação ambígua | desativada | 0.02 |

No perfil anterior, high/new abaixo de 0.35 não recebiam caixas dessa faixa,
pois o detector já as descartava. Na adoção, high/new efetivos são o máximo
entre o corte de saída e seu parâmetro configurado; caixas mais fracas não
iniciam IDs, mesmo se o usuário elevar o corte de saída.

## Repetição e verificações

Instalar os extras existentes e executar os testes de adaptador/core descritos
em [visão](../vision.md). Comparação de produto deve congelar commit, hashes,
configuração efetiva, fonte e referências, preservando a ordem dos frames.
Para VFR, usar tempos de apresentação; não inferir movimento com FPS médio.
O preview existente permanece apenas exploratório nesse caso.

O procedimento privado congela as detecções e reproduz os trackers com as
mesmas caixas. A implementação adotada reproduziu os IDs do candidato
nos 3371 frames; o perfil de retorno reproduziu os IDs da baseline, sem divergências.
Isso verifica integração e retorno, sem validar identidade real. Testes com
ByteTrack real também cobrem associação fraca sem saída, proibição de criar
IDs fracos, disputas ambíguas, recuperação decisiva e sessões intercaladas.

Os tempos dos replays compartilham inferência entre trackers e não são
benchmark isolado. Latência sustentada e ponta a ponta, identidades em
outros cruzamentos, câmera móvel/IMU e hardware continuam não validados.
Não houve deploy AWS ou alteração de alerta tátil, limiares de risco,
contrato de rede ou ética/permissão de coleta por esta adoção.

## Verificação da adoção

[Evidência agregada](issue-11-candidato-adocao.json): 482 testes passaram,
zero falhas/erros/skips, Python 3.11.16, com extras de visão/API e peso geral
confiável. A suíte inclui ByteTrack real e HTTP/HTTPS local; não mede rede
AWS ou hardware. Os dez testes adicionais cobrem o novo comportamento.
Ruff 0.16.10 (E4/E7/E9/F), check_docs e git diff --check passaram.
O replay da implementação integrada e do retorno explícito passou nos
3371 frames dos nove vídeos, preservando IDs exatos e valores contínuos
a cinco casas decimais. Fontes privadas e cache não foram versionados.

A revisão pré-merge também verificou compatibilidade da ordem dos argumentos
posicionais existentes de VisionConfig; novos parâmetros foram acrescentados ao final.
