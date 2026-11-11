# #23 — diagnóstico de cadência e operação após reboot

09/10/2026. Continuação autorizada por Bryan após o merge do PR55.
Responsável: Bryan, com apoio de IA. R21 permanece fixo, YOLO geral preservado.

## Objetivo e hipóteses

Investigar os 7,08 FPS da cadeira sem novo treino. O teste anterior tinha175 das 426
chamadas acima de100 ms; o cliente periódico descartou 174oportunidades ocupado.
Hipótese: aguardar a disponibilidade e capturar uma imagem fresca, com máximo
10 inícios/s e uma requisição ativa, evita esperar o próximo ponto da grade100 ms.
Isso não altera API, timeout, validade, parâmetros dos modelos ou risco local.

Reprodução determinística dos426tempos: grade periódica modela7,10fps e captura
quando disponível modela9,21fps. **Simulação contrafactual**, sem inferência/rede;
durações são assumidas iguais sob nova cadência. Não é resultado cloud ou aceite.
Comando: `python scripts/analyze_frame_cadence.py --report TRACE_PRIVADO.json --output REPLAY_PUBLICO.json`.

## Comparação autorizada

UmaVM CPU4/São Paulo, prazo absoluto 30 min, mesmos modelos/imagem/áudio em todas
as fases. Teto vigenteUS$15/8 h somadas; uso anterior ≤4,321 h. Atualizar ledger
privado, preços eIPv4 antes da rodada; encerrar manualmente em falha e remover
recursos ao terminar. O ensaio de prazo observa término automático deliberadamente,
sem deixar um serviço permanente. Não aumentar tempo para terminar testes.

JPEG95 original já aprovado e varianteJPEG85 recodificada a partir do mesmo
JPEG, mantendo dimensão/conteúdo; registrar hashes/bytes e segunda compressão.
Fases ordenadas:95periódico,95disponível,85periódico,85disponível,95disponível,
95periódico. Cada fase:30 s de aquecimento e 60 s medição; ordem repetida limita
confusão entre melhora e variação temporal. Sem vídeos novos/dataset/treino.

`remote_load --scheduling periodic` continua sendo padrão histórico da#22.
`--scheduling when_available` é opt-in da#23, teto de início de captura; não
representa600oportunidades periódicas. Relatório/agregador registram o modo.
Nunca criar fila, reenviar captura vencida, sobrepor requests após timeout ou
apresentar essa opção como firmware pronto. Corpo enviado continua JPEG+metadata.

## Critérios de verificação

- Registrar FPS dentro da janela, drenagem, P95/P99 de admissão e estágios,
  erros/descarte, CPU/RAM e continuidade. Comparar duas fases95por cadência.
- Usar metas experimentais já aprovadas (≥8 FPS, trabalho P95 ≤80 ms,
  JPEGpronto→admissãoP95 ≤150/P99 ≤250 ms), sem reajustá-las ao observar resultado.
- Comparar classes observadas por snapshot, sem concluir precisão a partir
  de uma cadeira; compressão85 exige avaliação independente antes de adoção geral.
- Confirmar reboot real, mesma instância e mesmo prazo absoluto; recuperar
  explicitamente Compose, validar TLS, imagem/modelos e sessão nova.
- Observar expiração real e instância terminada; auditar/remover disco/chave/SG.
  Exportar evidência antes do prazo. Autoridade não pode depender de cloud para
  calcular risco ou vibrar; firmware/hardware continuam fora do ensaio.

Logs brutos e snapshots ficam privados, sem mídia/segredos emGit. Publicar
agregados, hashes, comandos e limitações emdocs. Alertas são confirmados pelo
proprietário; verificar destinatário confirmado, sem administração de billing
para IAMoperador. [AWS:verificação do destinatário](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-email-recipients.html).
