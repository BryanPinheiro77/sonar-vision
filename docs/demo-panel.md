# Painel de demonstração — #73

Responsável: Bryan (modelo/cloud). **Implementação e evidência local simulada;
AWS manual, CPU4 e ESP físico pendentes.** [ADR 0024](decisions/0024-painel-demonstracao.md),
[contrato ToF proposto](protocol/demo-tof.md), [referência visual aprovada](../DESIGN.md).
O outro trio revisará o contrato e implementará aquisição/envio na #17.

## Acesso por senha — extensão aprovada em 04/11/2026

[ADR 0027](decisions/0027-deploy-preservado-acesso-painel.md) registra a alteração
solicitada por Bryan para usar redes móveis. Com
`SONAR_DEMO_VIEWER_PASSWORD_VERIFIER` configurado, a raiz `/` mostra o próprio
formulário quando não há sessão e o painel quando há. Login, saída e sessão
expirada mantêm o navegador na raiz. Os GETs antigos `/demo` e `/demo/login`
encaminham para `/`; as rotas internas de dados e POSTs mantêm compatibilidade.
O formulário usa o usuário
`sonar` e a senha entregue por meio privado. Dados, JPEGs, histórico e downloads
exigem cookie de sessão; não há desafio Basic do navegador. Só os assets de
marca, CSS e login são públicos. O Bearer do ESP não substitui o login de
leitura; a sessão de leitura não permite publicar ToF, inferência ou encerrar
a sessão do dispositivo.

Esse modo substitui a checagem de IP **dos espectadores** na aplicação. Ausente
o verificador, continua o modo legado por CIDR descrito abaixo. Valor inválido
impede inicialização. Os CIDRs não devem ser abertos para `/0` como alternativa.
No modo com senha, cloud pode liberar a porta HTTPS no Security Group para
as redes móveis; SSH continua restrito e a API de ingestão continua exigindo
token individual. Não abrir as imagens anonimamente.

Provisionar a senha em arquivo privado fora do Git e obter o verificador com
`sonar_vision_api.viewer_auth.make_verifier(password)`. O servidor recebe apenas
o verificador PBKDF2-SHA256/salt, não o arquivo de senha. Ao escrever `.env`
usado por Compose e shell, colocar o **valor completo entre aspas simples**,
pois contém `$`; nunca inserir a senha em comandos, URL, frontend ou logs.
Recriar a API para aplicar/rotacionar a configuração. As sessões usam cookie Secure/HttpOnly/SameSite=Strict, com validade máxima de
8h e chave por processo; reiniciar a API invalida todas elas. Login e saída
conferem Origin; Basic não é aceito para leitura. Sair remove o cookie do
navegador, sem revogar cópias do cookie em outro cliente.

Há limite global de duas verificações novas por segundo; excesso recebe 429
com Retry-After 2. A credencial já validada usa cache constante, mantendo os
limites existentes por rota. Verificação PBKDF2 roda em worker, fora do event
loop. A senha não habilita coleta nem altera a retenção dos dados.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_viewer_auth.py -v
```

O modo de senha inicial foi implantado na instância preservada em 04/11. Dez checks
remotos passaram no hostname público, incluindo token ESP, senha de leitura,
distância, JPEG e bloqueio cruzado das credenciais. O certificado público e a
CA entregue ao ESP foram verificados. A VM fica parada quando ociosa; a bancada
física e a medição de desempenho com espectadores após a alteração continuam
pendentes. As evidências privadas estão com Bryan; não são ensaio de segurança.

## Interface da referência visual — 27/10/2026

O painel reproduz a referência enviada por Bryan: logo original do Sonar Vision,
azul-petróleo e turquesa sobre branco, cabeçalho compacto, imagem ampla,
escala ToF e gráfico recente. O arquivo `logo.jpeg` é usado no desktop e no celular, no ao vivo e no histórico.
Desktop usa imagem/sensor lado a lado; celular empilha os painéis e fixa
os links de navegação na base. Sem dependências novas ou fontes externas.

Com **fonte e backend ambos simulados**, abre a cena identificada como
**CENA SIMULADA · ILUSTRAÇÃO**. É uma apresentação estática gerada por IA,
não o JPEG nem previsões do dispositivo; a caixa ID 1 é um exemplo e o
checkbox controla sua visibilidade. Em **Detalhes da captura**, **Ver JPEG
recebido** retorna à imagem original com verificação SHA-256. Fonte/backend
real inicia no JPEG. Falhas nunca alternam automaticamente para a ilustração.
Os estados do canal sempre descrevem o recebimento real do servidor.

Distância e gráfico usam somente ToF recebido. O contrato continua em
milímetros (`distance_mm`); painel e histórico exibem **centímetros inteiros**
(arredondados), compatíveis com a precisão útil do sensor. A régua cobre
0–400 cm; acima disso mantém o número e informa que excedeu a escala. Ausência,
falha, pausa, atraso e leitura inválida ocultam marcador/curva atuais.
Não há código de cores de risco nem associação da distância à pessoa.

O gráfico mantém até **24 amostras e 30 segundos**, só em memória da aba,
sem persistência ou novas consultas. Sequências repetidas não geram amostras;
inválidas e lacunas de 5 s interrompem a curva. Troca de sessão/origem/backend,
encerramento e fechamento descartam a janela anterior. Escala vertical
automática, com valores no nome acessível. Não habilita coleta ou rodadas.

Origem de `demo_static/demo-scene.webp`: ferramenta integrada ImageGen,
gerada em 27/10/2026 para esta interface. Prompt: corredor de concreto cinza,
manequim anônimo de costas à esquerda, obstáculo retangular à direita,
renderização arquitetônica realista sem texto/caixas. Conversão local para
WebP (182 KB); avisos e caixa são HTML/CSS separados. Sem fotos de participantes.

Movimentos respeitam `prefers-reduced-motion`, sem interpolar medições ou
previsões. A nova entrada restrita na lista de assets exige reiniciar a API
ao instalar esta revisão. Mudanças posteriores só em HTML/CSS/JS exigem
recarregar a página em execução Python; no Docker reconstrua a imagem.
Não há build npm para este painel.

## Dados, estados e limites

A ampliação autorizada da #73 acrescenta [coleta experimental por rodada](collection.md),
desligada por padrão. Os limites abaixo descrevem o modo ao vivo; o arquivo
optativo possui retenção e configuração próprias, conforme ADR 0025.
O menu separa **Ao vivo** de **Histórico** (`/demo/history`), com download,
play/pausa, busca e velocidades. Organização arredondada revisada a pedido de
Bryan, usando Fleury/KPMG como referência de estrutura e mantendo a marca Sonar.

`/demo` abre sem cadastro/login, somente nas redes autorizadas. Não contém
token do ESP. Mostra JPEG obtido da **API**, com caixas/classes/IDs do diagnóstico
original, sem outra inferência. Verifica SHA-256 antes de desenhar. Fonte, boot,
frame, captura, hash e epoch identificam a imagem. `simulated` identifica a fonte;
backend `simulated` é indicação separada de previsões roteirizadas. `esp32` é
declaração do operador, não atestado criptográfico de captura física.

Imagem e ToF têm idade/estado próprios. Inválida exibe indisponível, nunca zero
ou caminho livre. Distância não é atribuída a pessoa/caixa. Diferença de captura
usa o mesmo relógio de boot exigido no contrato, não implica sincronismo.
Falha somente no JPEG mantém ToF atual disponível; falha da consulta de estado
indica desconexão de ambos. Pausa/aba oculta suspendem consultas; dados envelhecem.

| Limite inicial de demonstração | Valor |
|---|---|
| Atualização / espectadores operacionais | A cada 2 s / até 3 abas, **provisório até CPU4** |
| Snapshots / JPEGs | Limite agregado 3/s de cada por processo; excesso 429 |
| ToF / assets | 10 tentativas/s da fonte selecionada / 24 requisições/s |
| Atraso | Idade desde recebimento ≥5 s, canais independentes |
| Retenção | Descarte aos 30 s, varredura a cada 1 s mesmo sem consultas |
| Memória do painel | Um JPEG ≤limite de upload (padrão 512 KiB), até 20 previsões, uma leitura ≤2048 bytes |
| Diagnóstico pendente | Após 2 s vira inferência indisponível |

A tabela descreve a retenção do servidor. A janela gráfica da aba, limitada
a 24 amostras/30 segundos, está descrita acima.

Buffers de upload/inferência/respostas em trânsito também consomem memória;
isso não limita a RAM total do processo. Não há fila própria, histórico,
arquivo de imagem, banco ou treino automático nesse modo ao vivo. A coleta
optativa da #73 tem retenção própria; promoção para dataset segue #72/#7. Diário
da #52 permanece desligado salvo avaliação explicitamente configurada. HTTP
no-store; frontend sem armazenamento persistente. Espectador ainda pode copiar
conteúdo. O limite agregado não identifica usuários: mais de três abas pode
causar429 nas demais. Três abas não são capacidade validada.

## Executar localmente sem placa

Python≥3.11 e ambiente virtual conforme [execução](execution.md). Simulador usa
OpenCV dos extras existentes, gerando retângulos/JPEGs com rótulo sintético:

```sh
python -m pip install -e '.[vision,api,api-dev]'
umask 077
mkdir -p .local/demo73
python -m sonar_vision_api.dev_tls .local/demo73/tls
python -m sonar_vision_api.tokens demo-sim .local/demo73/tokens > .local/demo73/device.token
export SONAR_API_BACKEND=simulated
export SONAR_API_TOKENS_FILE=.local/demo73/tokens
export SONAR_DEMO_ENABLED=1
export SONAR_DEMO_DEVICE_ID=demo-sim
export SONAR_DEMO_SESSION_ID=demo-73
export SONAR_DEMO_SOURCE_KIND=simulated
export SONAR_DEMO_ALLOWED_CIDRS=127.0.0.1/32,::1/128
python -m sonar_vision_api --port 8443 \
  --certfile .local/demo73/tls/server.pem --keyfile .local/demo73/tls/server-key.pem
```

Confiar explicitamente na CA pública local no computador/navegador de teste,
verificando origem e removendo confiança após o ensaio. Não desabilitar TLS,
usar `--insecure` ou distribuir chave privada. Abrir `https://localhost:8443/demo`.
Em outro terminal, ativar o mesmo ambiente:

```sh
PYTHONPATH=src python scripts/demo_source.py \
  --endpoint https://localhost:8443 --ca-file .local/demo73/tls/ca.pem \
  --token-file .local/demo73/device.token --session demo-73 \
  --frames 20 --interval 2 --exercise-errors
```

A fonte recusa servidor sem rótulo `simulated` ou sessão correspondente.
Alterna imagens visualmente distintas, registra hashes, envia inválida a cada
três amostras e sequência repetida esperando 409. Recibos não contêm tokens.
Para interromper canais separadamente, usar `--images-only` ou `--tof-only`;
manter o outro e aguardar 5 s/30 s. Reiniciar simulador conserva o boot selecionado
e usa IDs/sequências monotônicas. Novo boot físico exige nova sessão e recriação
do serviço. ToF pode iniciar antes da primeira imagem.

`--end-session` envia DELETE autenticado, apaga ambos os canais e bloqueia sua
repopulação até reinício. Encerrar também servidor por Ctrl+C. Nenhum desses
comandos mede sensor, áudio/tátil físicos ou segurança de navegação.

## Compose local

Mesmo serviço/imagem/volumes, sem porta adicional. Variáveis acima mais:

```sh
export SONAR_HOST_TLS_DIR=./.local/demo73/tls
export SONAR_HOST_TOKENS_FILE=./.local/demo73/tokens
export SONAR_HOST_MODELS_DIR=./models
mkdir -p models
export SONAR_UID=$(id -u)
export SONAR_GID=$(id -g)
docker compose -p sonar73 -f compose.yaml -f compose.demo.yaml up -d --build --wait
docker compose -p sonar73 -f compose.yaml -f compose.demo.yaml ps
```

No Docker o peer pode ser gateway NAT. Conferir o IP efetivamente visto e incluir
somente seu CIDR/32 em `SONAR_DEMO_ALLOWED_CIDRS`; recriar serviço. Não usar `/0`
ou X-Forwarded-For. Bind continua 127.0.0.1; não publicar externamente para
contornar 403. Teste dentro do contêiner não comprova acesso externo.

```sh
docker compose -p sonar73 -f compose.yaml -f compose.demo.yaml down
```

## AWS — roteiro manual de Bryan

**Não executado nesta entrega; não criar recursos agora.** Reutilizar
[operação AWS](aws-operation.md), CPU4/R21 e runner paralelo da #22. Conferir
conta/ledger e saldo agregado **US$15/8h**, sem renovar orçamento. Preservar
prazo absoluto/timer/guard, encerramento e limpeza da #23. Painel não acrescenta
instância/disco/serviço; contabilizar CPU/RAM e tráfego extras no mesmo ledger.

1. Revisar PR/commit, obter pesos legítimos/hashes, construir imagem com assets
   empacotados e registrar ID imutável/base/versões. Seguir transferência
   verificada, arquivos privados, TLS e preflight da #23.
2. Conferir prazo/timer/guard antes da API. Preservar CPU4/3GiB, runner paralelo
   e hashes. CLI serial não equivale ao perfil CPU4 medido.
3. Security Group: SSH 22 apenas operador/32; HTTPS 8443 apenas IPs públicos/32
   dos computadores da apresentação e da origem ESP. Nunca 0.0.0.0/0 ou ::/0.
   Registrar/remover regras ao terminar. Uma rede compartilhada autorizada
   também alcança a página sem login; não usá-la para imagens pessoais.
4. Fornecer URL e CA **pública** aos espectadores; confiar na CA pelo mecanismo
   do SO/navegador, ou usar certificado público já confiável. SAN deve incluir
   host/IP. Token individual fica só no ESP/cliente; chave TLS e operação privados.
5. Selecionar dispositivo/boot e fonte `simulated` no primeiro ensaio. Allowlist
   usa peers/32 efetivamente vistos, inclusive NAT. Conferir 403 de outro IP e
   que X-Forwarded-For não permite contorno. Não adicionar proxy nesta entrega.
6. Acrescentar `-f compose.demo.yaml` em **todos** os comandos do ensaio,
   preservando os overlays paralelo/áudio da #23. Não habilitar diário persistente.
   Na VM já preparada, com release/imagem/arquivos privados existentes:

```sh
export SONAR_DEMO_DEVICE_ID=demo-sim
export SONAR_DEMO_SESSION_ID=demo-73
export SONAR_DEMO_SOURCE_KIND=simulated
# IP de documentação: substituir pelos peers/32 autorizados conferidos.
export SONAR_DEMO_ALLOWED_CIDRS=203.0.113.10/32
PYTHONPATH=src python3 scripts/check_aws_release.py --parallel --audio
docker compose -p sonar23 -f compose.aws.yaml -f compose.aws.parallel.yaml \
  -f compose.aws.audio.yaml -f compose.demo.yaml up -d --wait --wait-timeout 120
```

O preflight original valida release/modelos/TLS, não SG/painel/sessão/benchmark.
Se fonte selecionada não tiver credencial provisionada, o processo recusa startup.

7. No cliente autorizado, enviar duas imagens com `demo_source.py` usando
   HTTPS/CA da VM. Conferir hashes do recibo/painel e download da **AWS**. Testar
   inválida, replay,401/403/413, atraso independente, retenção e DELETE. Evidência
   local não satisfaz esse passo. Guardar só agregados autorizados, sem JPEG/token.
8. Comparar condições 0/1/3 espectadores abaixo. Após revisão com hardware,
   selecionar `esp32`, boot novo e demonstrar ESP → AWS → navegador com ambos os trios.
   Comprovar fisicamente que falha de página/nuvem não altera tátil local.
9. Encerrar sessão e serviço próprios; limpar/auditar recursos da #23 (instância,
   volumes, SG/chaves), remover regras adicionais/confiança na CA e atualizar custo/
   tempo acumulado. Stop da instância não é limpeza completa.

Rollback: imagem/configuração anterior sem overlay demo, preservando credenciais
vigentes e prazo. Reinício perde imagens/leituras; não restaurar boot/tracks
antigos ou credencial revogada.

## Comparar latência e recursos no CPU4

`scripts/demo_benchmark.py` envia sempre o mesmo JPEG numa fonte explicitamente
simulada, com **backend real** para CPU4. Cada invocação mede uma condição sem
sobrescrever saída. Cliente mede HTTPS completo, não CPU/RAM remotos. Coletar
na VM com `sample_container.py` e logs da API, conforme
[reprodução #22](experiments/issue-22-reproduce.md). Registrar quota CPU4/3GiB,
hashes imagem/pesos/runner/configuração, rede, duração e aquecimento.

```sh
PYTHONPATH=src python scripts/demo_benchmark.py \
  --endpoint "$BENCH_ENDPOINT" --token-file "$BENCH_TOKEN" --ca-file "$BENCH_CA" \
  --session demo-73 --spectators 0 --duration 60 --fps 10 \
  --output .local/demo73/cpu4-r1-viewers0.json
```

Repetir para 1 e 3, saídas novas; repetir a série mais duas vezes, ordens 3/1/0 e
1/0/3. Sem outras abas. Espectadores gerados consultam snapshot/JPEG a cada 2 s,
sem renderização; complementar com três abas reais. Conferir zero erros/429,
FPS admitido e P50/P95/P99, deltas de CPU/RAM. Aplicar metas existentes #22 ao perfil
congelado (≥8 admissões/s, trabalho P95≤80ms, HTTPS P95≤150/P99≤250ms), sem inventar
tolerância nova do grupo. Se houver prejuízo, suspender painel/reduzir carga e
revisar antes da apresentação. Até medir, 2 s/três abas são limite **provisório**.

## Verificações e limites de aceite

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_demo.py -v
PYTHONPATH=src python scripts/run_tests.py --report-dir .local/demo73/test-report
python scripts/check_docs.py
git diff --check
```

[Evidência local e pendências](experiments/issue-73.md). Não há comandos de
vibração ou limiares locais novos; núcleo C++ e tarefas do ESP permanecem iguais.
Falha do painel preserva a API. Independência tátil física, ToF real, AWS e CPU4
dependem dos ensaios. Não encerrar a #73 como inteiramente validada antes deles.


## Formulário aprovado — 04/11/2026

Bryan solicitou substituir o popup nativo por uma tela no estilo do painel e
revisar localmente antes de publicar. A implementação local acrescenta
`/demo/login`, com sessão de até 8h em cookie Secure/HttpOnly/SameSite=Strict,
assinada por chave efêmera por processo. Reiniciar a API invalida as sessões.
POST de login/saída exige Origin da própria aplicação. Assets de marca/CSS/login
são públicos; imagens, snapshots e histórico continuam protegidos. A saída
remove o cookie deste navegador; não há revogação individual no servidor.
Basic não é aceito no acesso de leitura. Bryan aprovou a prévia local e
solicitou PR, revisão, merge e publicação. O resultado do deploy deve ser
conferido no registro operacional privado; a decisão não garante serviço ligado.


## Prévia de compartilhamento

Bryan solicitou Open Graph em 04/11. Login e painel incluem metadados Open Graph
e Twitter com URL canônica da raiz. A imagem pública estática de 1200×630 usa
somente a marca Sonar Vision e texto sobre a demonstração; não contém capturas,
leituras, credenciais ou dados de participantes. Fonte: [card HTML](assets/og-sonar-vision.html),
exportado para `demo_static/og-sonar-vision.png` com viewport 1200×630, escala 1.
Sem biblioteca nova no runtime. A busca inicial da prévia depende de a VM estar
ligada; as plataformas podem manter cache próprio. O compartilhamento não abre
as imagens recebidas pelo ESP.


### Revisão visual do card — 04/11/2026

Bryan pediu ilustração 3D, como nas referências Fleury/aiiaLabs, e remoção do
endereço escrito no card. O novo card combina a marca original com uma
ilustração conceitual 3D dos óculos; não é foto de um protótipo montado.
A imagem visível não contém URL. Os metadados mantêm URL canônica e endereço
absoluto da imagem para o compartilhamento funcionar.
Fonte e procedência: [arte 3D](assets/og-illustration-3d.png),
[registro de geração](assets/og-illustration-3d.provenance.json) e
[composição HTML](assets/og-sonar-vision.html).

## Sugestão de áudio por frame — ampliação da #73, 11/11/2026

Bryan autorizou exibir a sugestão já decidida pela API no Ao vivo e no Histórico.
O painel mostra **texto**, sem gerar voz, executar novamente a política ou
confirmar reprodução no ESP. A atuação tátil local continua independente.

A projeção privada de previsão recebe o campo opcional `audio`, copiado da
resposta **depois** da validação do contrato. Uma sugestão rejeitada pela API
aparece como `null` também na projeção. Apenas a conclusão bem-sucedida publica
texto e caixas: timeout, falha, outra sessão/frame/hash ou resultado tardio não
podem publicar a sugestão. O contrato de inferência 0.1 não muda.

- **Frase registrada:** texto da sugestão retornada para o JPEG exibido. É um
  registro da decisão, não um comando atual: a validade de áudio permanece a
  do contrato, mesmo quando o painel consulta a cada dois segundos.
- **Sem sugestão:** a resposta trouxe `audio=null`. Não inventar o motivo da
  abstenção ou interpretar como caminho livre.
- **Áudio não registrado:** captura antiga sem esse campo. Não recalcular a
  sugestão; a política depende do estado da sessão e dos anúncios anteriores.
- Ao pausar, perder conexão/JPEG, trocar de frame ou expirar a imagem, limpar a
  frase exibida. A cena ilustrativa não recebe a sugestão do JPEG oculto.

O Histórico e o ZIP conservam a sugestão original nas novas previsões, com
validação da referência à observação, sessão, frame e captura. Reprodução
histórica só exibe o registro; não toca áudio nem envia comandos ao ESP. As
mesmas permissões, retenção e cotas de coleta continuam valendo. Sem política de
áudio configurada, a API continua devolvendo `audio=null`.

Verificação específica, sem hardware, AWS ou TTS:

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_demo_audio.py -v
```
