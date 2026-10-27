# Coleta experimental por rodada — ampliação da #73

Responsável: Bryan, com apoio de IA. [ADR 0025](decisions/0025-coleta-historico-rodadas.md).
Ampliação autorizada em 27/10/2026: guardar JPEGs/previsões e ToF, baixar rodadas
e consultar/reproduzir histórico. Coleta desativada por padrão; não altera o
[contrato 0.1](protocol/eventos-semanticos.md) ou o descarte do [ao vivo](demo-panel.md).

## Configuração explícita

Mesmos extras e HTTPS do painel, sem pacote novo. Criar diretório privado e
uma configuração nova por rodada, antes de subir a API:

```sh
umask 077
mkdir -p .local/rounds .local/collection-config
chmod 700 .local/rounds .local/collection-config
python -m sonar_vision_api.collection configure \
  --source-id synthetic-73 --permission-ref owned-synthetic \
  --output .local/collection-config/round.json
export SONAR_COLLECTION_DIR=.local/rounds
export SONAR_COLLECTION_CONFIG=.local/collection-config/round.json
```

O comando não sobrescreve arquivo. Origem/permissão são identificadores opacos,
não nome/caminho de pessoa. O exemplo só autoriza bytes sintéticos de teste;
não declara permissão de vídeo/pessoa real. Configurar antes o dispositivo/boot
do painel. A configuração gera ID exclusivo; repetir processo com o mesmo ID
é recusado, protegendo rodada anterior. Para outra rodada, usar arquivo novo.

Limites confirmados por Bryan, também explícitos no JSON gerado: `--seconds 600`,
`--frames 3000`, `--bytes 104857600`, `--retention-seconds 86400`. Podem ser
reduzidos, permanecendo positivos; aumentar os tetos exige nova decisão. O
limite de bytes inclui metadados e reserva de status final. O primeiro limite
encerra gravação; previsões ausentes nessa fronteira continuam indisponíveis.

Sem `SONAR_COLLECTION_DIR`, nenhum JPEG/ToF é gravado. Diretório sem configuração
de rodada abre somente o histórico, sem iniciar gravação. A área inteira também
é limitada a 100 MiB e 100 rodadas para evitar crescimento entre sessões;
fila de oito itens, sem bloquear a inferência. Fila cheia conta descarte; falha
de disco encerra coleta, não o serviço. Não há amostragem por classe/confiança.

## Arquivos privados e recuperação

Cada diretório de rodada contém `manifest.json`, `events.jsonl` e
`frames/<sample_id>.jpg`. Manifesto registra origem, permissão, limites, backend,
hashes/configuração dos modelos quando reais, estado, contagens e prazo. JPEG é
o upload admitido, com dimensões e espaço de coordenadas registrados. Previsão
original tem classe/confiança/caixa/ID/epoch/hash; nunca vira anotação humana.
ToF guarda validade, qualidade, sequência/captura/recebimento e setor/agregação,
independentemente da câmera. Tokens/chaves/caminhos pessoais não são gravados.

Reiniciar API com o mesmo volume mantém rodadas. Rodada que estava gravando é
marcada interrompida; uma última linha parcial é ignorada explicitamente. Não
reabrir para escrita nem apresentar par JPEG/diagnóstico inexistente como válido.
Filesystem não é backup: interrupção de energia pode perder escritas recentes.
Não modificar manualmente a área ativa. Um lock exclusivo impede API/limpeza
offline ou dois serviços de disputar o mesmo diretório. Dentro do processo,
gravação e limpeza serializam alterações em disco e recontagem da cota, sem
bloquear a oferta de dados à fila de coleta.

## Retenção e limpeza

24h é prazo máximo desde criação. Dados vencidos somem das consultas mesmo se
disco impedir remoção. Varredura do próprio processo a cada segundo, sem depender
de espectadores. Limpeza offline somente após parar a API:

```sh
python -m sonar_vision_api.collection cleanup --directory .local/rounds
python -m sonar_vision_api.collection cleanup --directory .local/rounds --execute
```

Primeiro comando só simula. Só remove rodadas próprias registradas e vencidas;
o modo offline não inicia a varredura automática de retenção.
recusa symlinks/arquivos estranhos, sem alcançar exportações/datasets guardados
fora dessa área. Não usar pasta compartilhada com arquivos de outro módulo.
Não apagar locks de outro processo. Download ativo válido adia remoção enquanto
consome seu prazo limitado; consultas novas não recebem dados vencidos.
Com a API parada não existe worker ativo de exclusão: executar a limpeza
offline ou retomá-la ao iniciar o serviço. Em AWS, o prazo absoluto de destruição
da VM/disco continua independente da API e deve ocorrer dentro da janela da #23;
essa proteção não pode ser substituída pelo TTL da aplicação.

## Consulta e download privados

No navegador, abrir `/demo/history` ou usar **Histórico** no menu. Selecionar
rodada, reproduzir/pausar, buscar pela barra ou avançar/voltar um frame. Velocidades
0,5×/1×/2×/4×/8× seguem os timestamps originais. Rodada ainda gravando é um
snapshot; atualizar a lista para consultar novos frames. Sem intervalo temporal
entre as capturas, usar avanço manual. Não gerar MP4 ou novas previsões.

O reprodutor mantém no máximo dois JPEGs decodificados e uma requisição de
frame ativa, com teto de 10 downloads de JPEG/s por aba. Velocidade alta pode
saltar frames na exibição para respeitar esse teto, sem criar imagens ou
alterar os arquivos; revisão quadro a quadro continua disponível. Detalhes
técnicos ficam recolhidos; classes/IDs têm equivalente textual fora do canvas.

ToF mostra a última leitura **anterior ou igual** ao tempo do frame, com sua
defasagem. Não usa leitura futura; leitura inválida ou defasagem de 5s ou mais
não vira distância atual. A tabela independente permite consultar todas as
leituras, 50 por página, mesmo em rodada sem imagens. Nada associa distância a
uma caixa. Ao vencer ou falhar a seleção, limpar também identificação/posição
e link de download anteriores.

Rotas somente de leitura, sob o mesmo HTTPS/allowlist do painel; nenhuma
credencial do ESP vai para o navegador:

- `GET /v1/demo/history`: lista limitada às rodadas existentes e não vencidas;
  `enabled=false` quando o diretório não foi configurado.
- `GET /v1/demo/history/<round_id>`: snapshot da rodada, frames/previsões e
  ToF em sequências independentes. Até 3.000 imagens e 6.000 leituras,
  resposta JSON limitada a 16 MiB. Referência privada de permissão fica no
  download, não na consulta pública do painel.
- `GET /v1/demo/history/<round_id>/frames/<sample_id>`: JPEG original com hash
  conferido, nunca caminho fornecido pelo navegador.
- `GET /v1/demo/history/<round_id>/download`: ZIP com `round.json`, JPEGs,
  `sha256.json` e instrução de revisão. É um snapshot; novas capturas posteriores
  não entram nesse pacote. Não inclui chaves, tokens ou arquivos de outras rodadas.

Sem geração de MP4 ou nova inferência. Conferir integridade do ZIP e hashes
antes de usar o pacote. Exportação parcial/interrompida não é rodada completa.
Guardar o pacote baixado fora da área temporária se quiser preservá-lo.

Limites técnicos iniciais: duas leituras de arquivo/índice simultâneas, duas
consultas de metadados/s e 12 JPEGs históricos/s, agregados. Um único download,
sem fila, com prazo de 90 s e fila de dois blocos de 64 KiB, sem ZIP temporário
em disco nem rodada inteira em RAM. Excesso retorna429; prazo/desconexão
cancela o produtor. O lease de exportação impede limpeza enquanto ele lê arquivos.
Esses limites protegem recursos; desempenho CPU4 com espectadores/ZIP ainda
precisa ser medido. Ao vivo e inferência mantêm seus limites anteriores.

## Compose e AWS

Overlay `compose.collection.yaml` junto do painel. Diretórios já existentes,
privados, com UID/GID da API:

```sh
export SONAR_HOST_COLLECTION_DIR="$PWD/.local/rounds"
export SONAR_HOST_COLLECTION_CONFIG_DIR="$PWD/.local/collection-config"
export SONAR_COLLECTION_CONFIG_IN_CONTAINER=/run/sonar/collection/round.json
docker compose -p sonar73 -f compose.yaml -f compose.demo.yaml \
  -f compose.collection.yaml up -d --build --wait
```

Para somente consultar rodadas após reinício, deixar
`SONAR_COLLECTION_CONFIG_IN_CONTAINER` vazio. Mantém diretório de configuração
montado somente leitura, mesmo vazio. O diretório de rodadas é gravável somente
pelo usuário da API. Não publicar via servidor estático.

AWS: acrescentar esse overlay ao roteiro manual da #23/#73, sem nova instância,
banco ou bucket. Preservar orçamento agregado/prazo/limpeza; baixar/exportar
antes de destruir VM/disco. Histórico não sobrevive à destruição do volume e
não autoriza mantê-lo cobrando depois do ensaio. Rollback remove a opção de
gravação, preservando dados privados até exportação/limpeza autorizadas.

## Verificação

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_collection.py -v
```

Testes usam bytes sintéticos, relógio controlado e diretórios temporários.
Hardware, CPU4/R21 e AWS real permanecem pendentes. Coleta nunca treina
automaticamente; revisão, anotação e promoção para dataset seguem #72/#7.
