# #23 — operação temporária AWS, resultados

08/10/2026. Responsável: Bryan, com apoio de IA. **Ensaios operacionais
concluídos; PR/revisão e aceite da entrega pendentes. VM removida.**
Não há implantação permanente autorizada.

## Configuração e evidência

CPU4 `c7i-flex.xlarge`, São Paulo, Ubuntu24.04 AMD64, um cliente simulando
óculos. Docker:4CPU/3GiB, não root, filesystem somente leitura, TLS validado,
SSH/HTTPS restritos ao IPv4 do operador. Geral+R21, runner paralelo intraop1,
política de sugestões de áudio revisada. API/contrato e lógica tátil preservados.

- [Procedimento completo e obtenção legítima de artefatos](../aws-operation.md).
- [Manifesto, verificações, custo e limpeza](issue-23-aws-operation.json).
- [Verificação externa TLS/autenticação/JPEG](issue-23-endpoint.json).
- [Ensaio curto de carga e recursos](issue-23-load.json).
- [Docker local:12 verificações](issue-23-local-operation.json).
- [Dependências efetivamente instaladas na imagem cloud](issue-23-pip-freeze.txt).

Imagem imutável identificada no manifesto; base de código main doPR54 mais
arquivos ainda não publicados da#23, explicitamente **checkout sujo**. Hashes
dos arquivos/runner/pesos/configuração registrados. Rebuild não é bit a bit
reproduzível, pois dependências transitivas não têm lockfile. Pesos/media e
segredos estão fora do Git; código correspondente acompanha a entrega AGPL.

## Ensaios operacionais

HTTPS com CA explícita, JPEG autorizado, credencial ausente/incorreta401 e CA
incorreta rejeitada. Foto extraída de vídeo próprio de Bryan retornou `chair`
e dois `unknown`, com sugestão de áudio; nenhuma anotação de precisão nova.

Rotação confirmou nova200/anterior401. Revogação do último dispositivo bloqueou
startup. Durante recuperação foi restaurado temporariamente o snapshot atual
apenas para continuar este teste; depois houve nova rotação e ambas as credenciais
anteriores foram rejeitadas. **Procedimento recomendado após revogação é
provisionar credencial nova**, sem restaurar snapshot revogado.

Parada manual bloqueou o cliente; partida explícita recuperou com novo cliente.
Falha real do processo, provocada pelo operador no PID do contêiner próprio,
aumentou RestartCount e recuperou automaticamente. Os primeiros métodos de
injeção (`docker kill` solicitado pelo operador e sinal interno ao PID1) não
provaram crash automático: parada do operador pede recuperação manual, e PID1
com init não representou o processo da aplicação. Nenhuma falha foi ignorada
como se fosse validação; o método final foi corrigido e conferido por inspect.

Atualização/rollback por IDs imutáveis carregaram as imagens esperadas e mantiveram
a credencial inicial revogada. Mesma fonte de aplicação com labels distintas;
não foi validada migração funcional de versões. Troca de pesos reais
R21→R20→R21 com caminho+hash e resposta autorizada, mantendo YOLO geral.
Não demonstra equivalência de qualidade R20/R21.

## Carga curta — pendência de FPS para esta entrada

JPEG de cadeira640×360,63.925bytes, previamente codificado, repetido;30s de
warmup e60s de oferta10frames/s. Não é streamingMP4, capturaESP ou teste em
caminhada. Uma requisição ativa, sem fila e sem reenvio de captura antiga.

| Medida | Resultado |
| --- | --- |
| Oportunidades de oferta |600|
| Enviadas/admitidas (inclui drenagem final) |426/426|
| Descartadas antes de captura por cliente ocupado |174|
| Admitidas dentro da janela de60s |425|
| Taxa efetiva na janela |**7,08frames/s**|
| JPEG pronto até admissão P95/P99 |135,53/141,38ms|
| Trabalho servidor P95 |65,44ms|
| Logs correlacionados/faltantes |426/0|
| CPU média/máxima sobre limite4CPU |20,58%/29,72%|
| RAM máxima Docker sem cache |367.945.318bytes (~351MiB)|

Latências ficaram dentro das metas experimentais; **taxa abaixo de≥8frames/s**.
Não afirmar capacidade geral de8fps para qualquer conteúdo. 175das426chamadasHTTPS duraram mais de100ms, intervalo da oferta10Hz;
a requisição ainda ativa faz o cliente descartar a oportunidade seguinte. Isso
explica o mecanismo das174oportunidades descartadas. A causa dessas durações
(rede/transporte/conteúdo) ainda precisa de comparação controlada; este ensaio não identifica
sozinho a causa e não justifica treino, troca de placa ou aumento da VM.
A #22 permanece como aceite do benchmark documentado, com limites de corpus;
esta nova entrada deve entrar no acompanhamento de desempenho.

CPU/RAM:29amostras inteiras na janela de requisições medidas no servidor,
excluindo warmup; RAM não é RSS. Relógios cliente/servidor não foram subtraídos.
Zero falhas de tentativa e continuidade do clock válida. A coleta registra
estágios/durações, sem imagens/tokens no log padrão; retenção Docker3×10MB.

## Custos, prazo e remoção

Prazo absoluto persistente, guard antes de Docker,100min desde início do ledger,
sem renovar após reboot. **Encerramento manual antecipado**; não foi executado
reboot ou esperado o vencimento real nesta rodada. Os guards de prazo ausente,
inválido e vencido foram testados sem desligar computadores reais.

Rodada≤0,570h; agregado≤4,321h de8h autorizadas. Estimativa de VM/IP/root
US$0,154 nesta rodada; agregado US$0,873 antes de impostos/tráfego. Cenário
conservador com4GB de tráfego anterior e1GB desta rodada:US$1,623 antes de
impostos, dentro dosUS$15. Não é fatura reconciliada nem leitura de créditos.

Auditados:0instâncias próprias ativas/paradas,0volumes,0chavesSSH,0SG. Sem
ElasticIP/snapshot. Proprietário confirmou orçamento/alertas; configuração pela
API de cobrança e entrega de e-mail não verificadas. Alertas têm atraso e não
bloqueiam automaticamente gastos.

Correção transparente: o consolidado anterior da#22 usava etiqueta sem hífen.
Foi repetido com `Experiment=issue-22`, sem resíduos. Auditorias individuais da
#22 já usavam a etiqueta correta; [registro corrigido](issue-22-final-resource-audit.json).

## Software, revisão e pendências

368testes com extras/ByteTrack real e pesoYOLO:0falhas/0skips. Sem extras:
368testes,76skips opcionais esperados,0falhas. Testes adicionais de validação
de preço do provisionador passaram após revisão. Docker local12checks.
Ruff, sintaxe e links/docs verificados na entrega. [Revisão local](issue-23-review.md).

Pendências: publicação porPR/revisão/aceite; handoff legítimo dos especialistas
para integrantes que forem reproduzir; diagnóstico da taxa da cadeira; versão
funcional futura/reboot/prazo real; hardware/captura/tracking independente.
Serviço mensal exige orçamento próprio. Nenhum teste físico com participante.
