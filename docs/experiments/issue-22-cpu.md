# Ensaio de threads de CPU — #22

Responsável: Bryan, com apoio de IA. Data: 2026-10-06.
A meta de trabalho autorizada por Bryan é oferecer 10 frames/s e buscar
≥8 admissões/s localmente. Outros limites, qualidade visual e gastos AWS
continuam pendentes de avaliação/aprovação.

## Hipótese e procedimento

Nos ensaios anteriores, a inferência consumiu quase toda a latência do
servidor. A hipótese é que a quantidade de threads escolhida pelo Ultralytics
contribua para a variação observada no Apple M5 (10 CPUs lógicas).
Isso não estabelece uma configuração para x86/AWS.

O benchmark aceita `--cpu-threads` opcional. O harness aquece dois frames
pretos com trackers descartáveis, no executor que realizará a inferência.
O primeiro inicializa os preditores e a seleção de CPU do Ultralytics;
depois aplica o ajuste experimental, e o segundo aquece a configuração
medida. Sem a opção, conserva a quantidade escolhida pela dependência.
O relatório registra threads efetivas nesse executor antes e depois da
carga, configuração solicitada, hardware, pesos, versões e commit.
As próximas medições também registram load average do host no início/fim,
se disponível. Essa carga geral não equivale à CPU consumida pelo processo.
As duas inferências de aquecimento não entram nos percentis da carga.

O ajuste afeta o processo PyTorch. **Executar cada repetição em processo
novo**, sem outro harness/modelo concorrente. O aquecimento é por frames,
não os 30 segundos propostos para a avaliação sustentada final. A configuração
da API de produção não foi alterada. Modelo, imagem de inferência, confiança,
tracking, validade, timeouts e política de não enfileirar permanecem iguais.
O alerta tátil local continua independente.

Instalar `.[vision,api,api-dev]` e obter pesos conforme [releases](../releases.md).
Repetir o comando com saídas novas; omitir `--cpu-threads` mede o padrão,
usá-lo com 1 ou 2 mede as alternativas. Não reutilizar um processo Python.

```sh
PYTHONPATH=src python -m sonar_vision_integration.load_bench \
  --weights models/yolov8n.pt --devices 1 --fps 10 --duration 15 \
  --cpu-threads 1 --output results/cpu-one-repetition-1.json
```

Matriz exploratória: três repetições de 15 segundos por configuração
(padrão, 1, 2), alternando a ordem entre repetições. Depois, comparar padrão
e uma thread com ambos os pesos por 30 segundos, duas repetições por perfil.
Uma thread foi alternativa exploratória, não configuração vencedora.
O JPEG preto original 640×480 não mede câmera, acurácia, tracking com alvos,
Wi-Fi ou AWS. São sondagens locais; 15/30 segundos não demonstram sustentação
por dez minutos nem generalização para vídeos reais. Não agregar os clientes
para afirmar a cadência por óculos.

`admitted_fps_within_offering_window` conta somente respostas admitidas
antes do fim da oferta. `admitted_fps_including_drain` inclui a espera final
no denominador. A métrica antiga `admitted_fps_over_offering_window` divide
todas as admissões, inclusive tardias, pela duração da oferta: é uma taxa do
lote oferecido, não comprovação de respostas concluídas dentro da janela.
Os relatórios anteriores permanecem íntegros; não inferir retrospectivamente
instantes de conclusão que não foram registrados.

## Resultados

O [relatório agregado](issue-22-cpu.json) contém 13 execuções em processos
novos, hashes dos relatórios privados, versões, pesos, recursos, desfechos e
percentis de todas as tentativas e por desfecho. Os nove ensaios gerais usam
`56ba399`; os quatro com dois pesos usam `42e5584`, que acrescenta contagem
dentro da janela e load average. Todos registraram checkout limpo e a mesma
quantidade efetiva de threads no executor antes/depois da carga. A entrada
preta é original do projeto, AGPL-3.0-only, sem participantes.

### Detector geral — três repetições de 15 segundos

| Threads efetivas | Cadência incluindo espera final, repetições 1/2/3 | P95 inferência, repetições 1/2/3 | P95 HTTPS de admitidas, repetições 1/2/3 |
|---|---|---|---|
| Padrão (8) | 3,45 / 9,00 / 9,87/s | 578,34 / 116,07 / 53,29 ms | 623,90 / 130,57 / 57,21 ms |
| 1 | 4,93 / 9,26 / 9,33/s | 225,44 / 98,80 / 97,33 ms | 272,47 / 103,82 / 102,10 ms |
| 2 | 0,75 / 7,33 / 9,93/s | 1234,48 / 159,19 / 79,36 ms | 483,78 / 165,90 / 89,01 ms |

Uma execução com duas threads teve 16 admissões, uma resposta vencida
descartada e um timeout, além de 67 oportunidades perdidas por atraso de
agendamento. O P95 de HTTPS admitidas exclui essas duas falhas; o JSON
preserva sua latência separada e o resumo de todas as tentativas. Não escolher
somente a melhor repetição nem interpretar as falhas como ausência de alvos.

O host estava sujeito a carga variável: um diagnóstico externo durante a
matriz registrou load average de 72,34 / 52,08 / 32,68 em dez CPUs lógicas,
50% de memória livre e nenhum aviso térmico registrado. Esse snapshot não
está sincronizado com cada execução e não identifica a causa dos atrasos.
Todas as configurações melhoraram nas últimas repetições; a comparação
**não permite atribuir um ganho causal ao ajuste de threads**.

### Detector geral + escadas v3 — duas repetições de 30 segundos

| Threads | Repetição | Admitidas durante oferta | Cadência dentro da janela | P95 inferência | P95 HTTPS de admitidas |
|---|---:|---:|---:|---:|---:|
| Padrão (8) | 1 | 271 | 9,03/s | 107,30 ms | 111,28 ms |
| Padrão (8) | 2 | 261 | 8,70/s | 110,06 ms | 114,43 ms |
| 1 | 1 | 163 | 5,43/s | 190,22 ms | 193,80 ms |
| 1 | 2 | 154 | 5,13/s | 213,82 ms | 219,08 ms |

No padrão, a primeira execução teve 272 respostas admitidas no lote, uma
depois da oferta. A taxa que inclui espera final foi 9,07/s; a segunda foi
8,70/s. Nenhuma tentativa destes quatro ensaios falhou, mas oportunidades
ocupadas foram descartadas. O load average de um minuto variou de 23,01 no
início do primeiro ensaio para valores próximos de 13 nos últimos; recursos
referem-se ao cliente e servidor no mesmo processo.

## Conclusão e pendências

A cadência de trabalho ≥8/s foi observada nas duas sondagens de 30 segundos
do perfil padrão com os dois pesos. Isso não valida sustentação por dez
minutos, cenas reais, rede remota ou hardware. As propostas de P95 ≤70 ms no
servidor e ≤100 ms até admissão não foram satisfeitas nesse perfil.
Forçar uma thread piorou as duas execuções com escadas; a configuração
padrão da API foi preservada. O aquecimento no executor é um procedimento
do harness; estes resultados não demonstram ganho causal sobre a API anterior.

Bryan informou que o grupo ainda não tem vídeos anotados. A próxima etapa
é coletar e revisar referências conforme o [roteiro #11/#16/#7](proposta-avaliacao-11-16.md),
antes de testar qualidade de IDs, trajetória e escadas. Depois, repetir a carga
com cenas representativas e protocolo sustentado. AWS e dimensionamento final
continuam pendentes de orçamento/aprovação; nenhum recurso pago foi criado.

## Verificação de software

Com `.[vision,api,api-dev]` e `SONAR_E2E_WEIGHTS` apontando para o peso geral
verificado, 323 testes passaram em 44,168 s, sem skips. Incluem o caminho
HTTPS real, isolamento dos trackers, falhas remotas e independência tátil
simulada, persistência do ajuste no executor após inferência e resposta
concluída somente durante a espera final. Ruff 0.16.10, verificação de
documentação e `git diff --check` passaram. Hardware vestível não foi testado.
