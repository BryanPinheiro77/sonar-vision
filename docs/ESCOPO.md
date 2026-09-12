# Escopo da entrega acadêmica

- Data: 2026-09-12.
- Origem: requisitos discutidos com Bryan; issue #10.
- Status: aprovado pelo grupo, conforme confirmação de Bryan em 2026-09-12.
- Prazo estimado: fim de novembro/início de dezembro de 2026, a confirmar.
- Registro da aprovação: confirmação de Bryan na discussão de requisitos;
  incorporação vinculada à issue #10. Não representa validação técnica.

## Contexto

A entrega pretendida é um protótipo de óculos integrado, não apenas uma
demonstração do detector no computador. Os experimentos do laboratório ajudam
a escolher e avaliar soluções, mas não comprovam funcionamento no hardware.

Este documento define o compromisso de escopo para a apresentação final.
Requisito obrigatório não significa capacidade já implementada ou validada.
Alterações de escopo precisam de revisão do grupo e registro na issue.

## Requisitos funcionais

DEVE indica requisito obrigatório; PODE indica objetivo adicional.

- FR-01: o protótipo DEVE capturar imagens nos óculos e enviá-las para análise
  remota, retornando informações utilizáveis pelo feedback.
- FR-02: a visão DEVE ser avaliada para pessoas, carros, motos, ônibus,
  bicicletas, cadeiras, mesas e cachorros. Crianças entram como pessoa, sem
  classificação de idade. Iniciar testes por pessoa não limita o produto.
- FR-03: o sistema DEVE identificar escadas e distinguir subida de descida;
  quando a evidência for insuficiente, DEVE admitir sentido inconclusivo.
  Isso não promete localizar precisamente a borda do primeiro degrau.
- FR-04: a visão DEVE manter histórico por ID e estimar movimento aparente,
  tratando perdas e oclusões sem presumir identidade perfeita.
- FR-05: sensores e processamento local DEVEM estimar proximidade e risco de
  colisão por direção, dentro de sua cobertura validada, e acionar vibração.
  A lógica NÃO DEVE depender de câmera, internet, VM ou LLM.
- FR-06: o protótipo DEVE fornecer áudio informativo sobre objetos e direção,
  sem bloquear a vibração. Retirar áudio por falta de tempo exige redução
  explícita de escopo aprovada pelo grupo.
- FR-07: na perda da rede/VM, o caminho tátil DEVE continuar operando; o sistema
  DEVE descartar observações visuais vencidas e informar indisponibilidade
  visual, sem repetir informações antigas como atuais.
- FR-08: a entrega DEVE demonstrar funcionamento em salas e corredores da
  faculdade e incluir demonstração externa supervisionada com o protótipo
  funcionando, mostrando captura e resultados da análise.
- FR-09: o plano de validação DEVE cobrir boa iluminação, baixa iluminação e
  noite com iluminação pública. O compromisso inclui buscar funcionamento
  nessas condições e documentar o desempenho, não declarar sucesso sem teste.
- FR-10: o sistema PODE interpretar o estado observado de semáforos como extra.
  NÃO DEVE autorizar travessia ou afirmar que todos os veículos pararam.

## Requisitos não funcionais e decisões pendentes

- NFR-01: independência local deve ser verificada com desconexão de rede e
  indisponibilidade da VM. Falhas dos próprios sensores exigem tratamento
  específico; continuidade local não garante percepção completa.
- NFR-02: medir latência sensor–vibração e captura–áudio, incluindo atrasos e
  descarte. A meta inicial de latência local inferior a 100 ms está na #4;
  não é resultado já atingido. Limites de expiração e orçamento visual ainda
  precisam ser definidos nas #12 e #6.
- NFR-03: registrar falsos positivos/negativos por classe e condição, trocas de
  ID e erros subida/descida. Amostras mínimas, faixas de distância/iluminação e
  limiares de aceitação precisam ser aprovados no protocolo #7 antes da
  avaliação final. Não há percentual de acerto aprovado neste escopo.
- NFR-04: gravações e testes devem seguir consentimento, supervisão e exigências
  éticas da instituição. Não publicar imagens pessoais ou vídeos brutos no Git.

Essas pendências impedem usar este texto como especificação técnica completa
para implementação. Cada tarefa deve resolver seus parâmetros e contratos
antes de implementá-los; não escolher números silenciosamente.

## Critérios de avaliação da entrega

- AC-01 (FR-01, FR-06): dado o protótipo conectado, quando uma cena prevista
  for apresentada, então registrar captura, análise recebida e áudio emitido
  com seus tempos, sem interromper a vibração local.
- AC-02 (FR-02, FR-08, FR-09, NFR-03): dadas cenas anotadas das classes e
  condições previstas, quando avaliadas, então apresentar resultados separados
  por classe/condição, incluindo falhas, confrontados com o protocolo aprovado.
- AC-03 (FR-03): dadas cenas de subida e descida, quando analisadas, então
  registrar acertos, confusões e respostas inconclusivas separadamente; não
  contar abstenções como acertos nem como detecção da borda de um degrau.
- AC-04 (FR-04): dados múltiplos alvos e oclusões, quando ocorrerem cruzamentos,
  então revisar continuidade, perdas e trocas de identidade com referência
  visual, sem usar apenas o número de IDs como medida de qualidade.
- AC-05 (FR-05, NFR-01, NFR-02): dados obstáculos na cobertura de teste dos
  sensores, quando houver aproximação, então avaliar setor, risco e vibração
  segundo parâmetros aprovados, inclusive com rede e VM indisponíveis.
- AC-06 (FR-07): dados resultados visuais atrasados e interrupções da conexão,
  quando expirarem, então não gerar mensagens sobre o estado atual com esses
  resultados e informar a indisponibilidade sem bloquear o caminho local.
- AC-07 (FR-10): se o extra for implementado, dado um semáforo ambíguo ou
  oculto, então admitir resultado inconclusivo; nenhum resultado deve produzir
  autorização de travessia ou garantia de ausência de veículos.

## Casos de falha

- EC-01: movimento da cabeça, borrão e pouca luz podem prejudicar a visão;
  definir como reconhecer indisponibilidade sem confundir ausência de detecção
  com ausência de obstáculo.
- EC-02: oclusão pode gerar ID novo ou transferir um ID a outra pessoa.
- EC-03: rede lenta, respostas fora de ordem e VM indisponível exigem validade
  temporal e descarte; detalhes ficam no contrato #12.
- EC-04: sensor sem amostra ou fora de cobertura não significa caminho livre;
  tratamento deve ser especificado na #9.
- EC-05: escadas, buracos, paredes e desníveis são problemas geométricos,
  diferentes de classes de objetos; a viabilidade com os sensores e câmera
  previstos deve ser demonstrada, especialmente em descidas e baixa luz.

## Contratos e modelos de dados

Não são definidos nesta issue de escopo. O contrato versionado de eventos,
campos, validade e erros será especificado na #12; entradas simuladas e saídas
da geometria local, na #9. Este documento não cria API, transporte ou schema.

## Fora do compromisso desta entrega

- Escuridão total e garantia de uso autônomo seguro no trânsito.
- Autorizar travessia, afirmar que todos os veículos pararam ou prometer
  prevenção de todas as colisões.
- Inferir idade de pessoas ou tratar escala monocular como distância/TTC real.
- Detecção garantida de buracos e de todos os desníveis: não aprovada nesta
  conversa; não é consequência automática do requisito de escadas.
- LLM obrigatório: sua utilidade será comparada com regras na #3.
- Escolha definitiva de modelo, infraestrutura nova ou compra de hardware
  adicional sem avaliação e decisão próprias.

O protótipo não substitui bengala, cão-guia ou orientação profissional.
Demonstrações não devem depender dele para atravessar ruas ou usar escadas.

## Aprovação e distribuição do trabalho

A #10 termina com a proposta revisada pelo grupo e incorporada por PR, não com
todas as funcionalidades implementadas. A aprovação do escopo não fecha #7,
#9, #11 ou outras tarefas técnicas.

As issues de implementação devem apontar para este documento, contratos e
experimentos relevantes, especificar entradas/saídas e falhas, ter critérios
verificáveis e responsáveis/revisores. Evidência obtida apenas no laboratório
deve continuar identificada como tal, sem ser apresentada como teste integrado.
