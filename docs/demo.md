# Roteiro demonstrativo do software — #34

Organização: Matheus. Preparação/instalação: [guia consolidado](execution.md).
Evidência: [registro local](experiments/issue-34.md).
Tempos abaixo são sugestões para organizar a apresentação, não requisito do grupo.

## Antes da apresentação

1. Registrar revisão do código e executar os testes/roteiro offline do guia.
2. Escolher outputs novos. Conferir que não há credenciais, vídeos pessoais ou
   caminhos privados visíveis. Não apresentar arquivos JSON brutos reais.
3. Anunciar o nível de evidência de cada etapa. Sem hardware, não afirmar que
   houve vibração, áudio falado, detecção real ou validação de segurança física.

## Etapa A — software sintético, sem hardware (cerca de 5 minutos)

Na raiz, PowerShell; Python >=3.11 e nenhum extra/modelo necessário:

```powershell
$env:PYTHONPATH = 'src'
python -B -m sonar_vision.simulator --fixture success --frames 1
python -B -m sonar_vision.simulator --fixture timeout --frames 1
python -B -m sonar_vision.simulator --fixture disconnect --frames 1
python -B -m sonar_vision.simulator --fixture success --current-yaw 16 --frames 1
python -B -m sonar_vision.simulator --fixture success --urgent --frames 1
python -B -m sonar_vision.audio_catalog validate docs/catalog
python -B -m sonar_vision.evaluation docs/experiments/issue-33-fixture.json --output results/issue-34/demo-evaluation-01.json --summary docs/experiments/issue-34-demo-local-01.md
python -B -m sonar_vision.smoke --output results/issue-34/demo-smoke-01.json
```

Fala sugerida: “O transporte aqui é uma fixture em memória. 100/2000 ms são
tempos virtuais conhecidos; não são latência de internet ou desempenho do modelo.
O timeout e a desconexão descartam sem inventar observação. Orientação mudou:
mantemos a observação admitida, mas rejeitamos sugestão direcional. Urgência é
entrada local sintética e bloqueia sugestão de fala; nenhum motor é acionado.”

Mostrar `distribution_ready=false`: 179 frases propostas, sem voz aprovada.
Pacote silencioso, quando gerado pelo smoke, serve somente para testar arquivos.
Mostrar a síntese agregada: TP=5, FP=2, FN=2 contra anotações **sintéticas**;
confidence não é acurácia. A avaliação não aprova o protótipo.
Mostrar `passed=true` do smoke e seus indicadores de validação real=false.
Isso prova que os cenários documentados cumpriram expectativas, não que o
sistema inteiro está pronto. Usar sufixos novos quando repetir.

## Etapa B — análise real local (condicional; cerca de 5 minutos)

Só realizar com extra vision, pesos confiáveis e vídeo autorizado obtidos conforme
[guia](execution.md). Executar benchmark real desse guia; registrar hash/versões,
configuração CPU/confiança, fonte autorizada e limitações no diário privado.
Apresentar apenas resumo sem mídia pessoal. Esse caminho executa YOLO/ByteTrack,
mas não testa API, firmware, sentido de escada, trajetória ou risco/TTC.
Não usar número de detecções ou score para declarar precisão.
Sem anotações pareadas, não existe cálculo de TP/FP/FN real. Se houver snapshot
válido/revisado da #33, executar a avaliação separadamente em results/ e revisar
privacidade da síntese antes de apresentar. Não misturar sintético e real.
Sem artefatos/dependências aprovados, anunciar **etapa não executada**.

## Etapa C — rede real e hardware (pendente #24/#28/#19)

Com API real disponível, autor fornece endpoint HTTPS, certificado e credencial
individual fora do Git; seguir [cliente #30](simulator.md). Indicar que yaw e
urgência do cliente ainda são sintéticos. Testes de timeout na etapa A não
substituem desconexão de Wi-Fi/VM real. Não inventar comando de iniciar servidor.

Para bancada física, equipe de firmware/hardware deve fornecer build,
provisionamento, procedimento seguro e evidência da #19. Demonstrar presença
de obstáculo local e feedback tátil, desligar rede/VM e verificar continuidade
do alerta local com medições e supervisão. Registrar firmware/pinos/configuração,
modo de falha e latência efetivamente medida conforme protocolo aprovado.
Nenhum procedimento de sensores/pinos ou aceitação é definido pela #34.
Não testar com participantes sem consentimento, supervisão e avaliação ética.
Sem hardware integrado, anunciar **etapa não executada**.

## Formulário de revisão de checkout limpo por outra pessoa

Preencher após executar; não é autorização automática nem revisão já realizada.
Matheus organiza a coleta, o outro integrante registra sua experiência. Guardar
logs/dados privados em results/; registrar em docs apenas síntese revisada.

| Campo | Preenchimento do revisor |
|---|---|
| Data e integrante responsável | Pendente |
| SHA/branch publicado no PR | Pendente |
| Pasta nova obtida por git clone; status inicial vazio | Pendente |
| SO, Python, pip; ambiente isolado | Pendente |
| Instalação -e . e pip check | Comando, retorno e dificuldade |
| Suíte unittest | Total, aprovados, falhas/skips e seus motivos |
| Smoke offline | Retorno; passed; cenários divergentes, se houver |
| Etapa A sem hardware e sem arquivos pessoais | Resultado observado e comparação com expectativas |
| Artefatos reais (B/C) | Executados com autorização ou explicitamente não executados |
| Origem/licenças/credenciais e outputs privados | Conferência, sem reproduzir dados sensíveis |
| Independência tátil | Preservada no desenho; evidência física ou não validada |
| Problemas encontrados/correções necessárias | Pendente |
| Conclusão sobre reprodução do guia | Pendente |

## Aceite e material para PR

| Critério #34 | Evidência | Situação |
|---|---|---|
| Reunir guias dos autores/pré-requisitos/configuração/comandos | execution.md e links aos módulos | Implementado neste branch |
| Checkout limpo com outra pessoa; simulado sem hardware | Teste local isolado e formulário acima | Outra pessoa pendente |
| Obtenção autorizada sem caminhos pessoais | Tabela de origem/licenças do guia | Procedimento documentado; real não obtido |
| Mocks, análise real, hardware, falha de rede e limitações | Etapas A/B/C e smoke | A validada; B/C não executadas |
| Verificar links/comandos e evidência | Registro em experiments/issue-34.md | Validação local; plataformas adicionais pendentes |
| Testes da implementação, sucesso/limites/falhas | tests/test_smoke.py | Resultado na evidência |
| Docs/índice/ADR quando necessário | Guias, índices e changelog | Sem mudança arquitetural; ADR adicional não necessário |
| PR revisável, independente de arquivos de Bryan | Fontes/fixtures próprias e comandos relativos | Arquivos preparados; PR ainda não aberto |
| Sem segredos/mídia/pesos; origem/licença | Artefatos sintéticos próprios; outputs ignorados | Sem aquisição/publicação de artefatos reais |

Descrição sugerida para o PR: “Relaciona #34. Consolida os guias existentes e
um roteiro que separa simulação, visão real e bancada. Adiciona smoke offline
com validação de resultados/códigos dos CLIs e testes de falhas/limites. Reutiliza
biblioteca padrão e módulos atuais, evitando serviço ou infraestrutura novos.
Evidência de execução em docs/experiments/issue-34.md; reprodução por colega,
visão real, rede e hardware pendentes.” Não marcar encerramento até completar
pendências. Pessoa responsável deve revisar e explicar implementação e riscos.
