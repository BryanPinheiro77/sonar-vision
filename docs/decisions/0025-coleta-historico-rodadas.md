# ADR 0025 — coleta optativa por rodada e histórico de reprodução

- Data: 2026-10-27.
- Responsável: Bryan, com apoio de IA.
- Status: ampliação da #73 autorizada por Bryan nesta conversa; implementação
  local, sem autorização para criar recursos AWS ou serviço permanente.
- Relacionadas: #73, #72, #17, #19, #23; ADR 0015 e 0024.

## Contexto e alteração de escopo

A #73 e o ADR 0024 limitavam o painel ao último frame/ToF em memória. Bryan
solicitou também rodadas para download/revisão e histórico no próprio painel,
com reprodução dos frames em sequência. Escolheu ampliar a #73 existente,
atualizada no GitHub. Confirmou limites iniciais configuráveis: 10 minutos,
3.000 imagens ou 100 MiB por rodada, o primeiro atingido; exclusão em até 24h.
A #72 continua sendo coleta local/revisão/promoção para dataset e treino.

## Decisão

Manter o modo ao vivo e sua expiração. Acrescentar coleta explicitamente
habilitada por configuração privada com origem opaca e referência de permissão.
Diretório privado em arquivos no volume da mesma API/EC2, sem banco, S3,
serviço adicional ou dependência. A mesma implantação pode ser executada no
computador para validação. Um processo é dono do diretório por lock do SO.

JPEGs são imutáveis, identificados pela origem/boot/frame/captura/hash; eventos
append-only guardam metadados, previsões originais e ToF em sequência própria.
Projeção de caixas é a mesma do diagnóstico, sem inferência adicional. Ausência
de diagnóstico fica indisponível, nunca zero detecções. Boot/epoch e lacunas
permanecem explícitos. ToF não é associado a uma caixa; o player apresenta
leitura anterior ao frame e sua defasagem, sem usar informação futura.

Worker de gravação com fila de oito itens (JPEG limitado a 512 KiB cada),
sem esperar disco na inferência. Fila cheia descarta/coleta conta motivo;
falha de escrita encerra a coleta, preservando API/ao vivo/tátil. A rodada não
é reaberta ou sobrescrita após reinício; diário parcial recupera linhas completas
e informa interrupção. Durabilidade depende do sistema de arquivos; não há
backup nem garantia de preservar buffers após falha de energia.

O teto de 100 MiB também limita a área agregada do coletor, para não multiplicar
o orçamento por rodada; guarda técnica de até 100 rodadas e índices limitados
a 3.000 frames/6.000 ToF/20.000 eventos por rodada. Metadados ocupam o mesmo
orçamento. Ao atingir capacidade, preservar existentes até vencerem e parar
novas gravações. Valores acima dos limites inicialmente autorizados são recusados.

Histórico/download são apenas leitura, com a mesma rede permitida/HTTPS e sem
tokens do ESP no navegador. Coleta é controlada pelo operador via configuração,
não por espectadores. Download e player terão concorrência/buffers limitados;
ZIP inclui JPEGs, timeline, previsões, manifesto e referências de permissão.
Exportação humana fica fora da área temporária e fora do alcance da limpeza.

Prazo é máximo desde criação, não garantia de 24h disponíveis. O worker de
retenção apaga rodadas vencidas, inclusive sem espectadores; novas consultas
recusam dados vencidos mesmo se remoção falhar. Limpeza offline tem dry-run;
recusa links simbólicos, arquivos não registrados e caminhos externos. Não
remover rodada durante download ativo válido. Outro processo precisa aguardar
encerramento da API para operar a limpeza offline.

## Alternativas e consequências

- Apenas memória: não atende revisão posterior ou histórico.
- Banco/S3/infraestrutura extra: dispensados para a capacidade experimental
  limitada, exigiriam necessidade e custos adicionais. Reavaliar após medições.
- Escrever em disco no hook: bloquearia inferência em falha/latência de disco.
- Salvar só detecções positivas: enviesaria revisão, omitindo falsos negativos.
- MP4 gerado no servidor: processamento adicional dispensável; reproduzir os
  JPEGs recebidos com timestamps, controles de posição e velocidade.
- Reprocessar frames no play: resultados diferentes e custo desnecessário;
  preservar previsões originais e referência humana separada.

## Validação e limites

Testar opt-in, identidade/hashes, validade ToF, limites, fila cheia/disco lento,
falha de gravação sem perder API, recuperação, retenção e limpeza, downloads
concorrentes e player. Comparar coleta/play/download no CPU4/R21 antes do aceite
de desempenho. Fonte simulada não valida ESP ou segurança física.

Implantação AWS continua manual por Bryan, prazo/limpeza/teto agregado US$15/8h
da #23. Destruir VM/disco pode apagar histórico antes de 24h; baixar antes.
Persistência mensal, novo orçamento, treino automático e coleta de pessoas sem
as condições do projeto não foram autorizados. Caminho tátil permanece local.
