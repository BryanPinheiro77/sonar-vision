# ADR 0014 — piloto offline de cadeiras e mesas

- Data: 2026-10-06.
- Status: procedimento experimental aprovado por Bryan para o piloto da #51, sem adoção do modelo.
- Responsável: Bryan.
- Issue: [#51](https://github.com/BryanPinheiro77/sonar-vision/issues/51).

## Contexto

O diagnóstico de dois locais novos com referências humanas congeladas mostrou
YOLOv8n com 5/8 cadeiras e 0/8 mesas; Open Images com 4/8 e 0/8. As capturas
originais não recuperaram as mesas. Há 9 capturas/32 caixas revisadas de um
local de desenvolvimento e 4/8 de cada um dos dois novos locais. A proposta
anterior reservava ambos os novos locais fora de treino e validação, deixando
o piloto à espera de mais mídia. Bryan pediu definir o objetivo e o procedimento.

## Decisão para o piloto aprovado

Executar um piloto supervisionado offline com classes físicas internas
chair/table, sem substituir o detector geral ou alterar o wire dining_table.
Treino usa o local antigo; validação/seleção de checkpoint usa novo local A;
comparação depois de congelar checkpoint usa novo local B. Isso altera
expressamente a reserva anterior: A/B continuam fora de treino, A vira validação.
Preservar papéis e manifestos anteriores; aplicar o novo desenho após aprovação
da [especificação](../experiments/issue-51-piloto-moveis.md).

Uma rodada CPU, até 20 épocas, imgsz 640, batch 4, seed 42. Registrar todos os
parâmetros efetivos. Meta aprovada para esta rodada no B: ≥3/4 cadeiras, ≥2/4 mesas, ≤1
previsão de móvel sem associação. Os números são hipótese do piloto, não
aceite do grupo para produto/segurança. Um resultado negativo é reportado e
rejeita o candidato; um positivo justifica investigar lote maior, sem promoção.

## Alternativas consideradas

- Esperar mais locais/negativos para qualquer treino: adequado à avaliação
  final, mas não necessário para um primeiro experimento limitado.
- Misturar frames de todos os vídeos em treino/validação: vaza contexto/objetos
  de um mesmo local e não é usado.
- Treinar em A/B também: reduziria a comparação fora do local de desenvolvimento.
- Substituir o YOLO geral por duas classes: removeria as demais classes do escopo.
- Interpretar toda mesa como dining_table no wire: requer decisão semântica
  separada e não decorre da aprovação geométrica das caixas.

## Consequências e validação prevista

A/B já foram avaliados com baseline: B não é teste final cego. Não usar B para
retuning/seleção de checkpoint. Novos locais, negativos e teste final permanecem
necessários para decidir adoção futura; a amostra atual é pequena/correlacionada
e a aprovação de caixas não certifica anotação exaustiva de todos os alvos.

Validar hashes, labels aprovados, conversão de caixas e separação física antes
de execução; medir recursos/latência e reportar falhas. Nenhuma tecnologia,
serviço pago ou dependência nova. Dataset, mídia e pesos privados fora do Git.
O caminho tátil local do ESP32-S3 continua independente do piloto e da nuvem.
A aprovação de execução foi registrada após Bryan responder “segue entao”.
A rodada terminou com candidato rejeitado; ver o
[relatório](../experiments/issue-51-resultado.md). Incorporação documental em
2026-10-17 preserva a data e a decisão do experimento original.
