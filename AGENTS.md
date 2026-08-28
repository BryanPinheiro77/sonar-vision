# Instrucoes para agentes de IA

## Contexto

O Sonar Vision e um projeto academico de tecnologia assistiva. Antes de realizar qualquer tarefa, leia o `README.md`, este arquivo e os documentos relacionados ao trabalho solicitado.

## Arquitetura

- O alerta imediato de seguranca deve funcionar localmente no ESP32-S3, sem depender de internet, VM, camera ou inferencia probabilistica.
- A VM adiciona semantica, tracking e telemetria; sua indisponibilidade nunca pode interromper o feedback tatil local.
- Nao introduza uma placa Edge como requisito. Essa opcao so pode ser adotada depois de um benchmark que demonstre sua necessidade.
- Quando o firmware existir, mantenha a logica de geometria, risco e TTC independente de hardware e testavel no computador.
- Nao altere silenciosamente pinos, limiares de risco, contratos de mensagens ou criterios experimentais. Registre decisoes relevantes em `docs/decisions/`.

## Forma de trabalhar

- Nao crie codigo, dependencias ou infraestrutura antes de uma issue definir objetivo e criterio de aceitacao.
- Prefira mudancas pequenas, revisaveis e associadas a uma issue.
- Nunca versione credenciais, chaves, dados pessoais, videos de participantes, datasets brutos ou pesos grandes de modelos.
- Testes com participantes exigem consentimento, supervisao e avaliacao das exigencias eticas da instituicao.
- Nao apresente o prototipo como dispositivo medico ou substituto de bengala, cao-guia ou orientacao profissional.
- Nao faca commit, push ou merge sem solicitacao explicita de uma pessoa do grupo.

## Antes de concluir uma tarefa

- Execute as verificacoes aplicaveis e informe seus resultados.
- Verifique que o modo tatil local continua independente da nuvem.
- Atualize a documentacao quando houver mudanca de arquitetura, contrato ou procedimento.
- Informe claramente tudo que nao foi validado, especialmente quando depender de hardware.
