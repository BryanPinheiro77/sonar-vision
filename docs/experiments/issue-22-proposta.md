# Proposta para concluir dimensionamento — #22

Data: 2026-10-06. Responsável: Bryan. **Proposta solicitada por Bryan, ainda
sem aprovação das metas ou autorização de gastos.** A stack e o contrato
atuais continuam sendo a baseline; a escolha final de infraestrutura será
registrada em ADR depois das medições.

## Perfil inicial proposto

Um óculos, oferta de **2 frames/s**, JPEG até 640×480, um envio ativo por
dispositivo e nenhuma fila de capturas antigas. Comparar 320×240 preservando
a proporção; registrar tamanho real dos JPEGs. Não tratar o tamanho da imagem
de inferência como resolução do upload. O ensaio com dois dispositivos é
adicional e deve revelar contenção e desigualdade de admissões.

| Métrica em rede nominal registrada | Meta proposta |
|---|---|
| Processamento no servidor, sem upload | P95 ≤ 200 ms |
| Captura até admissão, no mesmo relógio do cliente | P95 ≤ 500 ms; P99 ≤ 900 ms |
| Admissões com oferta de 2/s | ≥ 1,8/s por dispositivo no perfil aprovado |
| Falhas por tentativa | ≤ 5%, reportando também drops antes da tentativa |
| Informação inválida ou vencida admitida | Zero |
| CPU sustentada | ≤ 70% dos vCPUs alocados, com série temporal |
| RAM | ≤ 75% da memória alocada, incluindo margem para início |
| Rede ou VM indisponível | Descarte remoto e caminho tátil independente |

Estas metas deixam margem antes da validade experimental de 1000 ms. O
timeout do cliente continua 2000 ms e o do servidor 1500 ms. Elas não são
limiares de risco, acurácia ou segurança física. Admissão não significa áudio
reproduzido. Não calcular latência subtraindo relógios de máquinas distintas.

## Procedimento proposto

1. Congelar commit, hashes dos pesos/fontes, perfil, máquina e versões.
2. Medir uma linha de base local com YOLOv8n e outra com o peso opcional de
   escadas aprovado para o ensaio; vídeos de desenvolvimento servem para
   carga, mas não para acurácia independente.
3. Oferecer 1/2/5 frames/s por dispositivo; testar um e dois clientes. Para
   dois, usar inícios alinhados e espaçados: a API tem um slot global e não
   garante divisão justa de admissões.
4. Proposta para a avaliação sustentada: três repetições de dez minutos no
   perfil alvo, com aquecimento de 30 segundos separado. Testes curtos locais
   validam o executor, não capacidade sustentada da AWS.
5. Repetir na conexão prevista para a apresentação, medir erros e descartes,
   e ensaiar rede degradada/desconexão. Registrar emulação separadamente.
6. Aprovar região/capacidade em ADR só depois de medir CPU/RAM, latência,
   carga e custo. Comparar GPU apenas se houver necessidade demonstrada.

O executor `sonar_vision_integration.load_bench` usa os componentes HTTPS já
existentes. Ele cria JPEGs sintéticos em memória, não baixa mídia ou pesos,
mede recursos de cliente + servidor em loopback e deixa
`acceptance_evaluated=false`. Uma oportunidade perdida por cliente ocupado
é descartada antes da captura; ela não vira uma requisição atrasada.
O [ensaio curto executado](issue-22-load-synthetic.md) registra os resultados
e a contenção observada; ele não demonstra capacidade sustentada nem aprova metas.

```sh
python -m pip install -e '.[api,api-dev]'
PYTHONPATH=src python -m sonar_vision_integration.load_bench \
  --devices 1 --fps 2 --duration 10 --output results/load-one.json
PYTHONPATH=src python -m sonar_vision_integration.load_bench \
  --devices 2 --fps 2 --duration 10 --phase aligned --delay-ms 150 \
  --output results/load-two-aligned.json
PYTHONPATH=src python -m sonar_vision_integration.load_bench \
  --devices 2 --fps 2 --duration 10 --phase staggered --delay-ms 150 \
  --output results/load-two-staggered.json
```

Com `.[vision,api,api-dev]`, use `--weights models/yolov8n.pt` para modelo
real e remova `--delay-ms`, que só vale para o backend simulado.
Para medir o par opcional, acrescente `--stair-direction-weights` apontando
para o peso confiável documentado em [releases](../releases.md).
CPU/RSS de
loopback não são consumo do servidor remoto. O pico de RSS inclui início;
valores de memória não disponíveis na plataforma ficam null.

## Capacidade e orçamento propostos

Começar a avaliação por **c7i-flex.large, 2 vCPU/4 GiB**, se disponível e
elegível na conta; São Paulo (`sa-east-1`) é candidata inicial, e Virgínia é
comparação de custo/rede. Não presumir que distância geográfica determine
latência. Se faltar RAM, considerar m7i-flex.large (8 GiB). Se faltar CPU
sustentada, comparar família sem Flex antes de concluir necessidade de GPU.

A [AWS](https://aws.amazon.com/ec2/instance-types/c7i/) declara baseline de
40% por vCPU para c7i-flex.large: CPU abaixo de 70% não garante desempenho
sustentado acima da baseline. A [elegibilidade do Free Tier](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html)
depende da data/plano da conta; saldo, validade, cotas e região devem ser
conferidos antes do ensaio. Créditos consumidos também contam no orçamento.

Preços Linux On-Demand em USD, consultados em 06/10/2026, com catálogo,
rate codes e hashes no [registro de preços](issue-22-prices-2026-10-06.json).
Hipótese: um disco de **20 GB gp3 mantido durante um mês**, uma IPv4 pública
somente durante execução, sem IOPS/throughput adicionais.

| Região / candidato | EC2/h | Base para 8 h ativas | Base para 40 h ativas |
|---|---:|---:|---:|
| São Paulo / c7i-flex.large | US$ 0,13067 | US$ 4,13 | US$ 8,47 |
| Virgínia / c7i-flex.large | US$ 0,08479 | US$ 2,32 | US$ 5,19 |
| São Paulo / m7i-flex.large | US$ 0,15262 | US$ 4,30 | US$ 9,34 |

Fórmula: `horas × (EC2/h + 0,005 IPv4/h) + 20 × gp3/GB-mês`.
gp3 custa US$ 0,152/GB-mês em São Paulo e US$ 0,080 em Virgínia no catálogo.
Fontes: [EC2 São Paulo](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/South%20America%20(Sao%20Paulo)/Linux/index.json),
[EC2 Virgínia](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/US%20East%20(N.%20Virginia)/Linux/index.json),
[EBS](https://aws.amazon.com/ebs/pricing/) e [IPv4](https://aws.amazon.com/vpc/pricing/).

Proponho **US$ 15 de teto de consumo para o experimento inicial**, até oito
horas ativas somadas, com revisão antes de ampliar. A linha de 40 h é apenas
sensibilidade mensal, não autorização dessas horas. Os subtotais excluem
impostos/câmbio, egress pago, snapshots, domínio e serviços adicionais.
O tamanho do disco precisa caber na imagem e dependências realmente medidas.
Alertas de custo não bloqueiam gastos automaticamente. Parar a VM não apaga
o disco e uma IPv4 retida ociosa continua cobrada; o runbook deve incluir
remoção dos recursos e conferência da cobrança residual.

## Pendências que precisam de decisão

- Aprovar perfil, metas e orçamento antes de avaliação final ou gasto.
- Confirmar plano/saldo/cotas da conta e conexão da apresentação.
- Fazer as medições em AWS antes de escolher capacidade/região em ADR.
- #11/#16: congelar a parte aplicável do protocolo #7, referências revisadas
  e conjuntos independentes; dados usados para treino/ajuste não contam como
  teste novo. A ferramenta de carga não conclui avaliação de acurácia.
  O [roteiro de avaliação](proposta-avaliacao-11-16.md) propõe os lotes e
  registra as aprovações/artefatos ainda necessários.

Nenhuma instância, disco, domínio ou serviço pago foi provisionado nesta etapa.
