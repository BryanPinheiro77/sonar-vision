# ADR 0015 — serviço real e diagnóstico privado de avaliação

- Data: 2026-10-06.
- Status: implementação experimental autorizada por Bryan ao iniciar a #52;
  não aprova qualidade física, valores operacionais de áudio ou implantação paga.
- Responsável: Bryan, com apoio de IA.
- Issue: [#52](https://github.com/BryanPinheiro77/sonar-vision/issues/52).

## Contexto

A #6 conectou os módulos no computador, mas a inicialização pública da API
configurava só o detector geral e NullPolicy. A fábrica visual já tem um
especialista de escadas opcional. O cliente precisa de classes/IDs/sentido e
referências de captura para estudar o resultado remoto, que não é a janela
local do YOLO. O contrato 0.1 deliberadamente não leva caixas aos óculos.

## Decisão

Adicionar opções explícitas para peso de escadas, hashes esperados dos pesos,
configuração completa de AudioConfig em arquivo JSON revisado e diretório
privado de diagnóstico. A ausência das opções conserva YOLO geral/NullPolicy.
O primeiro ensaio usou v3 publicado. Após receber o handoff da #16, Bryan
autorizou integrar e avaliar o R20 como candidato experimental da #52, SHA-256
`f30ab3ee162d51322667342c1d8f38e50473aa994a573205be5ae3ff08424f3b`.
Mantém YOLOv8n geral, confiança 0,35, entrada 640 e CPU. Os 165/173 casos
conhecidos e oito falhas da #16 não constituem aceite de acurácia independente.
R20 permanece em handoff local: publicação do peso/dados não foi autorizada.
O v3 público continua disponível para reprodução/rollback. Nenhum candidato
substitui o detector geral nem é adotado automaticamente. Hashes/configuração são registrados,
ambos os modelos aquecidos antes de servir. Áudio é sugestão, não reprodução.

Diagnóstico é JSONL privado no servidor, opcional e desligado por padrão.
Cada reinício cria arquivo novo exclusivo com permissão 600; não sobrescreve
ou publica registros antigos. Guarda apenas previsões/correlação/configuração,
sem JPEGs, histórico completo, identidade do dispositivo, token ou texto de
fala. Session_id vira SHA-256; message_id/epoch/frame e hash do JPEG correlacionam
a captura com a resposta. Não é prova de admissão pelo cliente ou risco físico.

Fila própria limitada a 64 registros, máximo de 64 MiB por arquivo; escrita
em thread separada, sem bloquear a inferência. Fila cheia, limite de arquivo
ou falha de disco descarta diagnóstico. Os arquivos persistentes precisam de
retenção/limpeza pelo operador (#23); o limite por arquivo não limita todos os
reinícios. O serviço principal continua com um slot de inferência e sem fila
de frames. Falha na criação do arquivo solicitado impede início; falha durante
escrita não invalida a observação. A opção usa volume gravável separado na
configuração de avaliação, mantendo pesos/configuração somente leitura.

O cliente existente pode salvar recibos privados após validação e exibir
objetos/IDs/sentido/descarte. A associação às caixas é feita usando o arquivo
de diagnóstico obtido pelo operador, nunca por endpoint público.
Redimensionamento/cadência/compressão de upload são explícitos e registrados
no recibo. JPEG conserva padrão95 e permite opção1..100 para comparação;
ensaios95/100 revelaram perdas distintas em casos conhecidos, sem adotar
100 automaticamente ou reduzir confiança para compensar compressão. O wire 0.1
permanece igual; câmera móvel continua com trajetória unknown, sem compensação
IMU inventada. Originais/datasets permanecem locais, sem treino automático.

## Alternativas

- Colocar caixas na resposta 0.1: mudaria contrato/firmware e não foi autorizado.
- Criar endpoint público de debug: amplia exposição de dados sem necessidade.
- Gravar JPEGs ou vídeos na VM por padrão: não necessário à correlação e aumenta
  armazenamento/exposição; hashes e referências locais bastam para este ensaio.
- Escrever sincronamente por frame: disco lento poderia ocupar a inferência.
- Política automática com valores padrão: AudioConfig exige escolhas explícitas,
  e parâmetros de laboratório não equivalem a aprovação de uso físico.

## Verificação e consequências

Cobrir startup/modelos/hashes/configuração, isolação de sessões da política,
TLS/autenticação, expiração/timeout, falhas e limites do diagnóstico, reinício,
contrato sem caixas e cliente externo com contêiner real. Conferir modelo geral
mais v3 em conjunto, registrando limites dos dados e ambiente. Hardware/AWS
continuam fora desta execução. Caminho tátil local permanece independente.

O número 0014 está reservado ao piloto #51 em checkout separado; a sequência
mantém os dois registros distintos ao incorporá-los por PR.
