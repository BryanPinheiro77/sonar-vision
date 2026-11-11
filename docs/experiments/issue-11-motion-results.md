# #11 — ferramenta de avaliação pareada, verificação de 16/10/2026

Responsável: Bryan. Frente: modelo/IA e cloud.
Base da implementação e verificação: `051900fbe8219262b0db6c047e101e59fa7384a8`.
A entrega publica a ferramenta; a avaliação real da #11 permanece pendente.

## Resultado de engenharia

- 13 testes novos passaram; incluem resposta correta/errada, perda, abstenção,
  rótulo humano unknown, cruzamento invertido, múltiplos alvos, segmentos,
  timestamps, alinhamento/hash, privacidade, adapter, CLI e destinos de saída.
- Regressão completa com extras/peso geral real: **389 testes passaram em
  58,748 s**, sem falhas, erros ou skips, Python 3.11.16/macOS.
- CLI executada com a fixture da #33 e sidecar sintético; relatório e revisão
  privados sob results/. Retorno 0, seis verdades conhecidas e dois acertos de
  estado. Não representa acurácia de detecção/movimento real.
- Ruff E4/E7/E9/F e git diff --check passaram. Documentação verificada por
  scripts/check_docs.py. Nenhuma dependência nova ou acesso cloud necessário.

## Resposta conhecida da fixture

| Quantidade | Resultado |
|---|---:|
| Referências visíveis | 7 |
| Movimento humano conhecido / inconclusivo | 6 / 1 |
| Respostas de movimento conhecidas, nas verdades conhecidas | 3 |
| Estados corretos | 2 |
| Estados errados, sem contar unknown/missed | 1 |
| Abstenções / perdas nas verdades conhecidas | 1 / 2 |
| Estado correto sobre todas as verdades conhecidas | 2/6 |
| Direção lateral correta sobre cruzamentos anotados | 0/1 |
| Segmentos totais / com verdade conhecida | 4 / 3 |
| Emissões com câmera não fixa | 1 |

Uma resposta crossing tem lado invertido e é contada como estado correto,
mas falha lateral; o relatório mantém as duas medidas separadas. O controle
de câmera também mantém sua falha explícita. Não ajustar parâmetros para
transformar esses controles sintéticos em afirmação de desempenho.

## Entrega e limites

[Execução, formato e leitura](../motion-evaluation.md) e
[especificação](issue-11-motion-spec.md). A fixture é própria, sintética e
AGPL-3.0-only; sem mídia, identidade pessoal ou pesos. `Result.observation()`
e API 0.1 permanecem inalterados. Predições são exportadas por adapter interno;
journal/preview não ganham exportação automática nesta etapa.

A ferramenta verifica estrutura e faz cálculos; operador ainda deve alinhar
capturas, congelar configuração e anotar/revisar referências independentes.
Nenhuma avaliação real, compensação de câmera ou hardware foi validada aqui.
Montagem/firmware e bancada ficam com Mathias, Tarcísio e Weslley. A #11 continua
aberta; a coleta pode aguardar sem transferir tarefas físicas ao trio de Bryan.
