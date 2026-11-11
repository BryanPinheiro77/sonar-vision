# Primeiro lote de escuta — proposta #32/#5

Data: 2026-10-17. Responsável pela preparação: Bryan.
Status: **proposta pendente de aprovação**, sem chamadas de geração ou gasto.
[Seleção e parâmetros](issue-32-primeiro-lote.json) ·
[Revisão das 179 frases](issue-32-revisao.md) · [Catálogo](../audio-catalog.md).

## Proposta imediata

Escutar uma pequena seleção **no computador**, comparar duas vozes prontas,
conferir pronúncia e medir duração antes de decidir o lote completo. Esse piloto
não é release do catálogo e não depende de montar o WM8960 ou implementar drivers.
A issue exige aprovação de conteúdo/provedor e direitos antes da geração;
“seguir com a preparação” não é autorização de cobrança ou aprovação dos textos.

### Doze textos existentes, sem alteração

| ID | Texto para revisão |
|---|---|
| local.urgent | Atenção |
| local.visual_unavailable | Assistência visual indisponível |
| local.visual_restored | Assistência visual restabelecida |
| visual.person.unknown.unknown.none | Pessoa |
| visual.person.left.unknown.none | Pessoa à esquerda |
| visual.chair.unknown.unknown.none | Cadeira |
| visual.dining_table.unknown.unknown.none | Mesa |
| visual.car.center.unknown.none | Carro ao centro |
| visual.stairs.unknown.unknown.unknown | Escada |
| visual.stairs.right.unknown.up | Escada de subida à direita |
| visual.stairs.right.unknown.down | Escada de descida à direita |
| visual.person.left.crossing.none | Pessoa à esquerda com movimento lateral aparente |

A seleção inclui três avisos locais, descrições curtas, direção, escada
conhecida/inconclusiva e uma frase longa para observar cortes. Não cobre todas
as classes/combinatórias. Textos/IDs/hashes são copiados do catálogo existente;
a escolha das doze não aprova as outras 167 nem altera manifesto ou seletor.
A alternativa “cruzando a imagem” fica fora deste primeiro lote, para não
introduzir alteração de texto junto da comparação de voz.

## Voz e custo propostos

Sugestão: OpenAI API, modelo fixado gpt-4o-mini-tts-2025-12-15,
vozes prontas **marin** e **cedar**, sem clonagem. No máximo uma geração por
frase/voz: **24 pedidos**, sem repetição automática. Após escuta, escolher uma
voz ou rejeitar ambas. Qualquer outra rodada fica fora desta proposta.

A documentação oficial recomenda marin/cedar para qualidade e lista português
entre os idiomas suportados. Também informa que as vozes são otimizadas para
inglês: isso justifica comparar a pronúncia brasileira, não presumir que está
adequada. [Guia oficial de TTS](https://developers.openai.com/api/docs/guides/text-to-speech).
O snapshot proposto é o padrão documentado do modelo na consulta; registrar
resposta/configuração efetiva ao gerar.
[Modelo e snapshots](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts).

Solicitar dicção clara, português brasileiro, tom neutro e velocidade natural,
sem palavras extras. Não acelerar automaticamente só para caber na validade.
Todos os arquivos exigem escuta humana; instruções não comprovam transcrição.

**Orçamento proposto: até US$1 de consumo para este piloto**, separado dos
US$15 da AWS. É limite de autorização solicitado, não gasto já aprovado,
estimativa de custo exato ou garantia de bloqueio pelo provedor. A tabela
consultada informa US$0,60/milhão de tokens de texto de entrada e US$12/milhão
de tokens de áudio de saída para o modelo. A cobrança depende dos tokens,
não apenas de 24 arquivos ou número de caracteres; não inventar preço por
minuto a partir de fontes externas. Conferir preços/acesso na conta antes da
geração. [Preços oficiais](https://developers.openai.com/api/docs/pricing).

Nenhum pagamento mínimo, recarga automática ou mudança de plano está autorizado
por este documento. Se a conta exigir contratar/adicionar crédito além do que
for autorizado, deixar essa etapa para Bryan. Não pedir chaves pelo chat;
credenciais, se necessárias depois, são configuradas localmente.

Alternativa de execução sem provedor pago: um integrante grava os mesmos textos
com permissão de uso da própria voz e revisão de qualidade. Isso elimina a
chamada TTS, mas exige gravação/revisão e não garante consistência/duração.
ElevenLabs permanece uma opção citada na issue, sem plano/voz/direitos escolhidos
ou comparação de preços nesta proposta. Não instalar provedor/dependência nova.

## Formato: computador agora, hardware depois

Propor retorno WAV para escuta no computador. Guardar o master recebido e medir
seu cabeçalho real, taxa, canais, bits, frames, duração, tamanho e SHA-256; não
preencher valores presumidos. O guia diferencia WAV de PCM cru e descreve PCM
cru a 24 kHz/16 bits sem cabeçalho. Isso não aprova o formato do dispositivo.

O candidato que **já existe** na #25/#18 é WAV PCM16 mono/16 kHz. Mantê-lo como
proposta para firmware validar com WM8960, clocks, armazenamento e reprodução;
não tratar a aprovação de escuta como aprovação elétrica ou de firmware.
Se for necessário converter master para esse candidato, guardar ambos e medir/
revisar o arquivo convertido. Não adicionar conversor/dependência nem criar lote
final antes de necessidade e formato aprovados.

## Procedimento após aprovação da proposta

1. Confirmar a conta/autorização do gasto, acesso ao modelo e direitos aplicáveis
   de uso/compartilhamento das vozes na fonte oficial vinculada à conta; registrar
   referência privada no manifesto. Esta consulta técnica não certificou direitos
   contratuais e não licencia o áudio como AGPL.
2. Enviar somente os 12 textos listados e instruções, sem vídeos, imagens, IDs
   de participantes ou dados pessoais. Nada de TTS durante a inferência/alerta:
   gerar arquivos previamente para reprodução local futura.
3. Gerar no máximo 24 arquivos privados, medir metadados e produzir página de
   escuta com texto, voz e duração, ainda sem marcar revisão como aprovada.
4. Escutar e comparar transcrição, pronúncia, clareza e prosódia. Rejeitar arquivo
   com palavras extras, omissão ou distorção. Registrar versão e resultado.
5. No computador, comparar áudio completo e conteúdo disponível após cortes em
   idades conhecidas, respeitando validade de 1000 ms das sugestões visuais.
   Não cortar o master nem aumentar validade. Avisos locais não herdam essa
   validade. Interrupção física/latência do hardware permanecem com #18/#19.
6. Escolher voz/conteúdo ou rejeitar o piloto. Compreensão com participantes só
   após protocolo, consentimento/supervisão e revisão ética da #5/#7.

Os arquivos ficam em bancada privada, fora do Git. O catálogo operacional
permanece draft e sem arquivos. Um subconjunto de 24 amostras não satisfaz o
release de 179 frases; não usar pacote fixture nem burlar o validador.
Em eventual apresentação do piloto, identificar a voz como sintética, conforme
o guia do provedor; isso é origem do áudio, não atribuição de autoria do código.

## O que a aprovação solicitada cobre

- Seleção dos 12 textos **para amostra de escuta**, sem aprovação operacional.
- Provedor/modelo/duas vozes prontos propostos, com revisão de direitos da conta
  antes da execução e sem clonagem.
- No máximo 24 gerações e até US$1 de consumo, sem recarga/assinatura automática.
- WAV para computador; formato final do firmware continua pendente.

Não cobre distribuição pública, uso físico, mudança de contrato, risco/TTC,
voz final, todos os 179 textos ou novos treinos. O caminho tátil local continua
independente de nuvem, câmera, áudio e TTS.
