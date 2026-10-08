# #22 — resultado do primeiro benchmark AWS com r21

Data: 07/10/2026. Responsável: Bryan, com apoio de IA. Ensaios concluídos;
instância terminada e recursos temporários removidos. **A #22 permanece aberta:**
a máquina testada não atingiu a meta de trabalho de8admissões/s; dimensionamento
permanente e demais metas quantitativas continuam pendentes.

## Perfil e reprodução

API da main/PR53 `adb0d2b`, YOLOv8n geral preservado e r21 selecionado por Bryan,
r20 disponível localmente para rollback. Sem treino, alteração de API/contrato
ou novas classes. Confiança0,35, imgsz640, CPU, IoU de associação0,50,
max-det300 e upload max-edge640/JPEG95. [Manifesto/hashes](issue-22-r21-profile.json).

São Paulo, c7i-flex.large,2vCPU/4GiB, Intel Xeon Platinum8488C: uma core visível
com dois threads. Ubuntu24.04 oficial;20GB gp3 criptografado e
DeleteOnTermination. Contêiner2CPUs/3GiB, áudio explícito, diagnóstico desligado
no desempenho. Uma thread intraop após o warmup padrão Ultralytics.

Cliente macOS separado, HTTPS direto com CA verificada/token e firewall
restrito ao IPv4 do operador/32. Túnel SSH inicial falhou; suas rodadas foram
separadas. Mac com tampa aberta e caffeinate durante as rodadas válidas.
Procedimentos e comandos: [guia AWS](../aws-start.md) e
[executor/coleta](issue-22-remote.md). Fonte do cliente é checkout dirty que
combina main/PR53 com PR50 ainda aberto e código novo; hashes e pacotes reais
estão nos [agregados](issue-22-aws-cpu.json). Não é revisão já publicada na main.

## Desempenho

Oferta10/s, um envio ativo por dispositivo, sem fila. Warmup30s por dispositivo
nas três repetições sustentadas e nos testes com dois dispositivos. JPEG preto
640×480,5427bytes. Taxa considera somente admissões concluídas dentro da oferta;
respostas após o término continuam registradas no relatório.

| Perfil | Janela | Admitidas/s por dispositivo | P95 inferência | P95 chamada HTTPS |
|---|---:|---:|---:|---:|
| Um dispositivo, repetição1 | 600s | 4,982 | 119,52ms | 179,25ms |
| Um dispositivo, repetição2 | 600s | 4,998 | 120,10ms | 137,88ms |
| Um dispositivo, repetição3 | 600s | 4,942 | 119,60ms | 143,49ms |
| Dois, alinhados | 60s | 2,30 /2,70 | 128,14ms | 138,04 /140,59ms |
| Dois, espaçados | 60s | 3,317 /3,317 | 122,52ms | 133,95 /134,08ms |
| Vídeo próprioA preencodificado | 60s | 5,483 | 98,96ms | 112,69ms |
| Vídeo próprioB preencodificado | 60s | 5,883 | 96,40ms | 115,84ms |
| Duas threads, controle sintético | 60s | 4,933 | 133,10ms | 143,51ms |

Nos três ensaios sustentados não houve falha por tentativa; cerca de metade das
6000oportunidades de cada rodada foi descartada antes da captura por cliente
ocupado. Com inferência acima do intervalo100ms, a próxima oportunidade pode
ser perdida mesmo com CPU média abaixo do limite. Não confundir ausência de
falhas HTTP com cumprimento do FPS desejado.

Dois clientes tiveram600/403respostas busy, respectivamente; espalhar fases
melhorou a divisão nesta sondagem, sem atingir8/s por cliente. Não garante
justiça para outros cenários. VídeosA/B são16JPEGs por origem, max-edge640,
com proporção preservada; suas dimensões diferem do preto640×480. Não atribuir
as diferenças de FPS apenas à presença de objetos.

CPU média do contêiner nas janelas sustentadas:29,52–29,92% da capacidade2vCPU.
RAM máxima observada nessas janelas:359242138bytes, pelo Docker sem cache;
não é RSS. Também foram amostrados MemAvailable/CPU do host. Sem OOM/restarts
nos contêineres dos ensaios. Não comprova margem para todas as cenas ou início.

Duas threads aumentaram CPU média para59,15% e não melhoraram FPS. Controle
rejeitado para seleção; não prolongado. Runner temporário reutilizou o builder
da API, ajustando torch.set_num_threads(2) após o warmup; valores efetivos1→2
foram registrados. Não adicionou opção/padrão ao produto. O [runner reproduzível](../../scripts/benchmark_threads_api.py) contém os mesmos
parâmetros do operador, organizados como script; o hash do runner privado
efetivamente medido está no agregado. Para repetir, montá-lo somente leitura
em `/run/sonar/threads_experiment.py` e usar o override abaixo depois de
exportar a linha de base. Reiniciar sampler com o novo ID do contêiner.

```yaml
services:
  api:
    entrypoint: ["python", "/run/sonar/threads_experiment.py"]
    volumes:
      - ../private/threads_experiment.py:/run/sonar/threads_experiment.py:ro
```

Não é o entrypoint selecionado para o deploy permanente.

Todos os oito relatórios têm continuidade do relógio true e zero requisições
sem correlação com os logs. Percentis da chamada HTTPS incluem transferência,
TLS, validação e agendamento; não são RTT puro. Captura física e encode do ESP32
não foram medidos. Rodadas de60s são exploratórias, não sustentação de10min.

## Qualidade do candidato fixo e outras classes

[Conferência AWS](issue-22-r21-aws-known.json):177JPEGs exatamente iguais aos
do handoff, incluindo161casos de treino/16validação do desenvolvimento.
Uma e duas threads reproduziram169/177pela regra congelada de direção/IoU,
com as mesmas oito falhas: N05-s06,D063,D023-lance-distante,D063-lance-distante,
L20-04,L20-05,NV-01,NV-03. Todas as177respostas de cada perfil foram admitidas,
sem diagnósticos ausentes. Sem regressões das escadas entre perfis nem contra
o handoff local. Não é acurácia independente ou aceitação física.

Classes/quantidades/IDs das detecções não escadas coincidiram em177/177entre
threads. Comparação numérica estrita com tolerância1e-6 coincidiu em175casos;
D057/D061 tiveram diferenças de confiança até1,88e-6, sem mudança de classes.
Não arredondar esses dados para declarar igualdade exata.

[Probe semântico](issue-22-r21-semantic-probe.json): no vídeoB, cadeira e unknown
em16/16amostras, movimento unknown e nenhuma escada. No vídeoA, nenhum objeto
reportado em16amostras; quatro amostras desse mesmo vídeo já não tinham objetos
na revisão anterior. Essa limitação do detector geral/entrada merece análise;
a presença de cadeira/mesa no vídeo não assegura detecção. Probe não mede
caixas/identidades contra referências nem qualidade temporal.

Sem treino automático: classificar falhas de modelo, compressão, tracking,
rede ou latência antes de decidir. Cenas reservadas para avaliação independente
continuam fora do treino. Pesos/vídeos/JPEGs/logs completos são privados; só
agregados e hashes entram no repositório.

## Consumo e limpeza

[Estimativa detalhada](issue-22-aws-cost.json): até1,748h de instância,
consumo de catálogo de aproximadamenteUS$0,245 antes de impostos, somando VM,
IPv4 e disco. Créditos contam no teto aprovadoUS$15. Não é fatura nem saldo
confirmado. Interface do host registrou27,26MB de saída; tráfego estimado zero
pressupõe franquia agregada mensal de100GB disponível, conforme
[preço EC2](https://aws.amazon.com/ec2/pricing/on-demand/). Reconciliação de
créditos/fatura permanece pendente; preços/fontes datados estão vinculados.

Terminação confirmada em07/10às16:42UTC; disco, chave pública e security group
removidos. Reconsulta às18:49UTC: zero instâncias/volumes/chaves/grupos com o
RunId. O registro da instância já não é retido na listagem. Não foram criados
Elastic IP, NAT, load balancer, snapshot ou recursos permanentes do deploy.

## Próximo passo e limites

Manter r21 como candidato e r20 para rollback. Antes da#23, continuar a#22 com
investigação de desempenho CPU e comparação de capacidade que preserve o perfil.
CPU4 é hipótese de próximo ensaio, sem garantia de atender8/s. A consulta AWS
marca c7i-flex.xlarge/m7i-flex.xlarge como FreeTierEligible=false, e a política
IAM atual autoriza somente os tipos large. Rever plano/permissão antes de
qualquer lançamento; orçamento existente não decide mudança de plano.
Não há evidência conclusiva de necessidade de GPU ou placa Edge.

337testes locais passaram, zero skips, com visão/API e peso geral real;
Ruff e checks de diff passaram. Documentação verificada. O caminho tátil segue
independente na arquitetura e nos testes simulados; hardware não validado.
