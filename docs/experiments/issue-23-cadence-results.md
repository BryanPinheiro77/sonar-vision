# #23 — diagnóstico da cadeira e recuperação operacional

09/10/2026. Responsável: Bryan, com apoio de IA. Comparação de seis fases
concluída; reboot, carga após recuperação, expiração real e limpeza concluídos.
Publicação e aceite desta continuação ainda pendentes.

## Resultado da comparação

Mesma VM CPU4 em São Paulo, um cliente, imagem imutável construída do commit
`d27d3922bf4fb256a65cf5ee7b5de4ec658e0ab0`, YOLO geral e R21 fixos. Confiança,
imgsz, IoU, timeout e contrato preservados. Cliente experimental executado a partir
do checkout modificado; isso não equivale a release já revisada.

[Plano e critérios antes da comparação](issue-23-cadence-plan.md) ·
[Agregados por fase](issue-23-cadence-comparison.json) ·
[Simulação contrafactual](issue-23-cadence-replay.json).

Cada fase teve 30 s de aquecimento e 60 s de medição. JPEG95: 63.925 bytes;
JPEG85: 36.166 bytes, recodificado do JPEG95 original, mesma dimensão 640×360.

| Fase | Entrada/cadência | FPS na janela | P95/P99 até admissão, ms | Trabalho P95, ms |
| --- | --- | --- | --- | --- |
| 1 | JPEG95, periódica | 9,80 | 85,19 / 104,83 | 58,58 |
| 2 | JPEG95, quando disponível | 9,65 | 85,04 / 103,08 | 60,96 |
| 3 | JPEG85, periódica | 9,90 | 82,06 / 98,83 | 57,12 |
| 4 | JPEG85, quando disponível | 9,67 | 81,86 / 95,93 | 57,91 |
| 5 | JPEG95, quando disponível | 9,67 | 81,41 / 96,98 | 58,61 |
| 6 | JPEG95, periódica | 9,93 | 84,73 / 97,04 | 59,25 |

Todas as fases tiveram zero falhas de tentativa, logs correlacionados completos,
continuidade válida e valores dentro das metas experimentais já aprovadas.
Snapshots retornaram `chair` e dois `unknown` em ambas as compressões. Isso não
é avaliação de precisão: não houve nova anotação independente ou avaliação de
escadas com JPEG85. CPU/RAM constam nos agregados do servidor, sem atribuir
recursos do cliente à VM; warmup foi excluído por timestamps do servidor.

## Decisão para o próximo uso

**Preservar a cadência periódica e JPEG95 aprovados.** A alternativa não trouxe
vantagem nesta rodada; a menor compressão não é necessária para atingir 8 FPS
com esta entrada. Não alterar padrões, treinar ou trocar de VM a partir disso.
A opção quando-disponível permanece apenas como ferramenta de reprodução do
experimento, explicitamente optativa, sem mudança do cliente físico/firmware.

Os 7,08 FPS anteriores não se repetiram. O mecanismo de descarte foi explicado:
175 chamadas acima do intervalo de 100 ms produziam espera por outra oportunidade
na grade periódica. A simulação dos tempos históricos reproduz aproximadamente
7,10 FPS e estima 9,21 com outra cadência; pressupõe durações invariantes.
**Não identifica a causa da diferença entre dias nem prova ganho real de 9,21.**
Rede, transporte, cadência e condições do teste podem interagir. Não atribuir
as falhas ao detector ou a uma camada específica sem experimento correspondente.

## Reprodução e software

[Revisão local desta continuação](issue-23-followup-review.md).

Usar as instruções de endpoint da [operação AWS](../aws-operation.md), mesmos
hashes e versões. O benchmark existente continua periódico por padrão:

```sh
PYTHONPATH=src python -m sonar_vision_integration.remote_load \
  --endpoint "$ENDPOINT" --device-id glasses-01 --token-file "$TOKEN_FILE" \
  --ca-file "$CA_FILE" --fps 10 --warmup 30 --duration 60 \
  --image "$JPEG" --source-id owner-approved-clip --scheduling periodic \
  --output .local/periodic-private.json
```

Trocar só `--scheduling when_available` para a alternativa, com outro arquivo
de saída. Uma requisição ativa, nenhuma fila e captura apenas após disponibilidade,
com teto de início; não representar essa modalidade como 600 oportunidades
periódicas. Recursos/logs e agregação seguem o procedimento da #22; os relatórios
públicos preservam o modo. Não enviar MP4 como payload.

Testes cobrem teto, latência acima do intervalo, timeout com transporte ainda
ocupado, drenagem após o fim da janela e HTTPS real. API e caminhos táteis não
foram modificados. Nenhuma dependência adicional; próprios artefatos AGPL.

## Reboot, prazo real e remoção

Reboot do sistema operacional, mesma instância: boot novo, prazo absoluto e
guard preservados; partida explícita do Compose recuperou HTTPS com nova sessão
e a mesma imagem/configuração. O harness inicialmente não capturou corretamente
a desconexão SSH esperada do reboot; a captura da exceção foi corrigida e a
continuação usou as evidências anteriores, sem repetir o reboot ou prolongar prazo.

Carga periódica JPEG95 após reboot: **552 s, 9,89 FPS, 5.458 respostas admitidas,
zero falhas**, P95/P99 de admissão **82,24/99,63 ms**, trabalho P95 **58,11 ms**.
Dentro das metas desta entrada; [agregado completo](issue-23-post-reboot-load.json).

Timer instalado para13:02:54UTC: último health observado válido13:02:51, primeira
indisponibilidade13:02:56 e término noEC2 confirmado, sem chamada manual de
terminate antes da observação. Reboot não renovou o prazo. Observação de health
não determina o instante exato do shutdown; [evidência](issue-23-followup-operation.json).

Auditados e removidos: zero instâncias próprias ativas/paradas, volumes, chavesSSH
e grupos de segurança. Rodada≤0,520h; agregado≤4,841h de8h autorizadas. Estimativa
VM/IP/root desta rodadaUS$0,141; agregadoUS$1,013 antes de impostos/tráfego.
Cenário agregado conservador de tráfegoUS$1,913 antes de impostos, tetoUS$15.
Não são fatura reconciliada ou saldo de créditos. Sem serviço permanente.

## Alertas, handoff e o que falta

Proprietário confirmou orçamento/alertas e recebimento/verificação do e-mail do
destinatário. Não é prova de disparo por consumo ou reconciliação da fatura.
Nenhuma permissão de administração de billing foi adicionada ao IAMoperador.
[Verificação exigida pelaAWS](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-email-recipients.html).

Pacote privado portátil de geral/R21/R20, hashes e instruções preparado para
revisão do proprietário; sem vídeo/TLS/credencial e sem envio a terceiros.
Permissão para handoff ao grupo ainda aguarda resposta. Artefatos fora doGit;
não converter isso em permissão de distribuição pública. A licença do código
não é automaticamente licença de datasets ou de pesos.

Restam entrega/revisão doPR desta continuação, permissão/acesso do grupo e
aceite da#23. Captura ESP, tracking independente, migração funcional de versões
e hardware continuam pendentes nas frentes correspondentes. Não treinar ou
ampliar classes a partir de uma comparação de desempenho bem sucedida.
