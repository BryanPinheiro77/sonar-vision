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
e a candidata com ambos os pesos por 30 segundos, duas repetições por perfil.
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

Resultados serão registrados após executar a matriz com o código identificado.
A decisão de infraestrutura e ativação de um ajuste no serviço permanece
pendente de evidência representativa e revisão.
