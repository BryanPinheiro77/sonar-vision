# #22 — investigação de execução CPU no Free plan

Data: 07/10/2026. Responsável: Bryan, com apoio de IA. Experimentos encerrados;
recursos temporários removidos e remoção auditada. **Nenhum ajuste testado
atingiu a meta de trabalho de8admissões/s. A #22 permanece aberta.**

## Comparação na mesma EC2

Uma nova c7i-flex.large em São Paulo,2vCPU/4GiB, mesmos modelos geral+r21,
mesma API main/PR53 `adb0d2b`, mesmos pacotes/base Python do primeiro ensaio,
confiança0,35, imgsz640, IoU0,50, FP32 e upload max-edge640/JPEG95.
R20 preservado localmente para rollback. Sem treino, classe ou contrato novo.
Cliente separado por HTTPS verificado, acesso restrito ao IPv4 do operador/32.
Contêiner2CPU/3GiB, sem diagnóstico durante desempenho.

Pilotos de60s, oferta10/s, warmup30s, um frame ativo por dispositivo, sem
fila. Uma thread interna por modelo; paralelo usa dois workers para modelos
independentes, tracking/associação seguem sequenciais. Os vídeosA/B têm16
JPEGs selecionados por origem, gravados pelo Bryan; não validam tracking.

| Ensaio | Admissões/s | P95 inferência | P95 HTTPS | CPU média /2vCPU |
|---|---:|---:|---:|---:|
| serial-pilot | 4.233 | 156.28 ms | 294.64 ms | 32.83% |
| parallel-pilot | 4.483 | 147.29 ms | 258.10 ms | 60.82% |
| parallel-corpus-A | 4.950 | 119.95 ms | 189.01 ms | 54.19% |
| parallel-corpus-B | 4.883 | 117.13 ms | 194.74 ms | 54.56% |

Ganho pontual do paralelo no preto:4,23→4,48/s, aproximadamente5,9%; abaixo
 do gate exploratório de8/s. Sem falhas por tentativa, continuidade do relógio
true e zero logs ausentes. Não prolongado para três rodadas de600s.
CPU aumentou de32,83% para60,82%. Não selecionar o paralelo com base neste
piloto. [Agregados/pacotes/hashes](issue-22-parallel-aws-cpu.json).

O mesmo tipo de VM expõe uma core física e duas threads; isso é compatível
com ganho limitado dos dois modelos concorrentes, mas não demonstra causa.
A variação frente à primeira VM (4,94–5,00/s sustentados) impede atribuir
 diferenças entre instâncias apenas ao runner. Mac local teve ganho43% em
inferência, não reproduzido nesta EC2. Não extrapolar Mac→AWS.

Erro de inicialização do operador: montar o script como `operator.py` sombreou
um módulo padrão Python. Corrigido para `parallel_experiment.py` antes da
medição; não contado como desempenho/falha de detecção.

## Qualidade preservada nos casos conhecidos

Serial e paralelo por HTTPS:169/177 corretos, mesmas oito falhas do handoff,
todas as tentativas admitidas e diagnóstico presente. Predições exatamente
iguais nos177casos entre esses dois modos. Classes gerais preservadas.
[Resultado](issue-22-parallel-aws-known.json). Material de desenvolvimento
(161train/16val), sem aceite de avaliação independente, hardware ou tracking.

## Formato de memória no PyTorch

Sondagem nativa pareada, sem API ativa, sem rede, dois conjuntos de modelos
independentes, uma thread interna.60amostras por modo alternadas,5warmups
por modo. `channels_last` mantém FP32 e todos os valores dos parâmetros;
conversão dos pesos antes da janela, da entrada dentro da inferência.

Média formato atual151,9997ms; channels_last152,9278ms. Sem ganho, não levado
para ensaio HTTPS prolongado.177/177predições iguais entre os modos nativos;
ambos169/177 no critério congelado, mesmas oito falhas. Frente ao serial
HTTPS anterior, o controle nativo teve147/177predições exatamente iguais,
mas o mesmo resultado no critério congelado. Igualdade numérica entre modos
nativos não implica igualdade universal entre execuções.
[Agregados/limitações](issue-22-layout-aws-native.json).

Referência do formato: [documentação PyTorch](https://docs.pytorch.org/tutorials/intermediate/memory_format_tutorial.html).
Não houve exportação/quantização/troca de runtime, dependência ou retreino.

## Reprodução

[Perfil congelado](issue-22-r21-profile.json),
[procedimento HTTPS/coleta](issue-22-remote.md) e
[ADR experimental](../decisions/0016-benchmark-remoto-temporario.md).

Para o paralelo, montar o [runner](../../scripts/benchmark_parallel_api.py)
somente leitura em `/run/sonar/parallel_experiment.py` e alterar entrypoint
apenas no override temporário. Exportar logs/sampler com o ID concreto do
contêiner antes de recriá-lo; reiniciar a coleta para cada ID. A API padrão
não foi alterada.

```yaml
services:
  api:
    entrypoint: ["python", "/run/sonar/parallel_experiment.py"]
    volumes:
      - ../private/parallel_experiment.py:/run/sonar/parallel_experiment.py:ro
```

Sondagem de memória: [runner](../../scripts/benchmark_layout_probe.py).
Executar no mesmo ID da imagem, API parada, `--network none --cpus 2
--memory 3g --read-only --tmpfs /tmp --user 1000:1000 --cap-drop ALL
--security-opt no-new-privileges`, entrypoint `python`. Montar pesos privados
em `/models`, JPEGs congelados/manifesto em `/run/sonar/layout-input` e script
somente leitura; resultados privados em `/run/sonar/layout-results` gravável.
`known177-manifest.json` contém lista `cases` com `id`; imagens numeradas
`known177/000.jpg` a `176.jpg`. Não há dados/pesos no Git. O hash do operador
medido e do runner formatado para reprodução ficam separados no agregado.

## Custo, remoção e próximo passo

Free plan mantido; nenhuma mudança de plano/IAM. Consumo de catálogo da
nova rodada (VM/IP/disco) aproximadamenteUS$0.073; agregado com a primeira
rodada aproximadamenteUS$0.317, antes de impostos e tráfego não medido.
Tempo agregado2.267h de8h; teto aprovadoUS$15, inclusive créditos.
Estimativa não é fatura/saldo. [Cálculo/remoção](issue-22-investigation-cost.json).

VM terminada, zero discos/chaves/grupos próprios residuais. Exportação privada
local concluída.339testes passaram sem skips; Ruff/documentação/diff verificados.
Nenhum commit/push/merge nesta investigação.

**Recomendação:** comparar CPU4 antes de decidir o deploy da#23. A proposta
c7i-flex.xlarge4vCPU/8GiB já está preparada, aproximadamenteUS$0,54/2h,
com única ampliação do tipo autorizado na política IAM. Ainda não aplicada;
lançamento real/elegibilidade nesta conta não testados. Confirmar a restrição
 do Free plan antes de propor mudança para Paid plan. Não há evidência aqui
que justifique GPU, novo treino ou reduzir silenciosamente qualidade/metas.

A #22 ainda precisa selecionar capacidade e fechar critérios quantitativos;
latência real do hardware, captura/rede vestível, acurácia independente e
tracking continuam pendentes. O alerta tátil local segue independente da VM;
nenhum firmware/hardware foi alterado ou validado nesta rodada.
