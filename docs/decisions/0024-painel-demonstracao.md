# ADR 0024 — painel temporário de observação e telemetria ToF

- Data: 2026-10-27.
- Status: implementação experimental da #73, solicitada por Bryan; contrato
  proposto para revisão com hardware/#17 antes da integração física.
- Responsável: Bryan, frente modelo/cloud, com apoio de IA.
- Referências: #73, #17, #19, #23, #52; ADR 0001, 0007, 0015 e 0017.

## Contexto

A apresentação precisa consultar a imagem realmente recebida pela nuvem e a
distância ToF. O contrato 0.1 não contém distância ou caixas. O diagnóstico
existente da #52 já projeta caixas/IDs e hashes sem outra inferência. A #73
autoriza o painel e sua implementação local; AWS permanece execução manual por
Bryan, sem recursos ou orçamento adicionais nesta tarefa.

## Decisão experimental

Servir HTML/CSS/JS pela FastAPI existente, optativo e desligado por padrão.
Sem framework, pacote novo, broker, banco, serviço Compose ou porta adicional.
Reutilizar autenticação individual e HTTPS para ingestão. ToF entra por
`POST /v1/demo/tof`, com esquema próprio `demo-tof-1`; inferência 0.1 fica igual.
Os detalhes, exemplos e limites estão no [contrato](../protocol/demo-tof.md).

O operador seleciona um dispositivo credenciado, uma sessão de boot e o tipo
de fonte (`simulated` ou `esp32`). Seleção é configuração privada de startup,
nunca um parâmetro controlado pelo espectador. ToF pode chegar antes de imagem.
JPEG só é publicado após validação/decodificação e admissão anti-replay, antes
de inferir. Upload rejeitado/busy não substitui o frame aceito. Reboot admitido
do dispositivo descarta ambos os canais e encerra a demonstração selecionada;
reconfigurar/reiniciar para o novo boot. `DELETE /v1/demo/session` autenticado
descarta ambos e impede repopular esse painel até reinício. Não encerra o
serviço de inferência nem altera o tracker/contrato do cliente.

Manter apenas um JPEG (no máximo o limite de upload, padrão 512 KiB), um
registro de previsões (até 20 detecções) e uma leitura ToF por processo.
Sem fila, arquivos ou histórico. Após 5 s desde recebimento, dado é atrasado;
após 30 s, descartar o payload. Uma tarefa de expiração verifica a cada 1 s,
inclusive sem espectadores; consultas e novos frames também expiram dados.
Esses são limites de demonstração, não limiares físicos. Preservar somente
marcas d'água constantes de sequência/captura para evitar replay após expiração.
Ao terminar sessão/processo, descartar os dados. Memória transitória inclui o
upload/inferência em andamento e respostas HTTP em trânsito; não promete apagar
bytes já recebidos por um espectador nem proteger contra captura de tela.

O hook de observação tenta lock sem espera e descarta observação em contenção;
falha não invalida a inferência. Usa a mesma função `prediction_record` do
diário, sem habilitar persistência. Caixas só correspondem ao mesmo dispositivo,
boot, frame, captura e SHA-256; IDs/epoch vêm do resultado original. Timeout,
falha ou projeção perdida vira inferência indisponível; após 2 s um diagnóstico
ainda pendente passa a indisponível. Resultado abandonado nunca fornece caixas.
O navegador verifica SHA-256 antes de desenhar e remove caixas na troca.

Consultas/imagens/página sem login, restritas por IP/CIDR no aplicativo **e**
Security Group na AWS. Recusar `/0`; padrão nativo só loopback. Não confiar em
`X-Forwarded-For`; proxies exigiriam decisão adicional. A lista de IPs é do
peer visto pela aplicação, podendo diferir em Docker/NAT; confirmar no ambiente.
Sem CORS, administração, upload ou credenciais no frontend. Cabeçalhos no-store,
CSP self, sem framing; página não grava localStorage, IndexedDB ou service worker.

Atualização a cada 2 s, uma consulta ativa por aba; operar com **até três abas**,
a confirmar no CPU4. Limite agregado de 3 consultas/s e 3 imagens/s por processo,
24 requisições de assets/s e 10 uploads ToF/s; excesso 429, sem fila própria.
Não é identidade ou quota por espectador: a quarta aba pode consumir a cota e
causar 429 nas outras. Não habilitar mais abas até medir. Desligar/pause/erro
do painel não depende nem interfere no laço tátil do ESP.

## Alternativas consideradas

- Novo frontend/framework/serviço: mais build, rede e consumo para uma página.
- MQTT para este primeiro ToF: requer broker ainda não necessário; HTTPS já
  existe e torna o contrato testável pelo simulador. Baseline MQTT futura intacta.
- Acrescentar campos ao wire 0.1: quebra o cliente físico; interface separada.
- Ler JSONL no navegador: expõe histórico/diagnóstico privado e acopla disco.
- Gravar todos os JPEGs: fora da #73; coleta/treino são trabalho separado da #72.
- WebSocket/stream contínuo: maior carga/complexidade antes de medir necessidade.

## Consequências e validação pendente

Fonte simulada identificada permite testar sem placa. Rotas e bytes locais não
comprovam AWS/ESP. Comparar latência e CPU/RAM com zero, um e três espectadores
no mesmo CPU4/perfil R21 antes do aceite de desempenho. Hardware deve revisar
regra de agregação, qualidade, orientação de zonas e relógio de boot; não há
driver/pino/risco/TTC novo. O tátil local continua independente da nuvem.
