# Revisão do catálogo e ensaio de compreensão — #32/#5

Data: 2026-10-17. Preparação: Bryan; responsável previsto pelo catálogo: Matheus.
Status: **preparação para revisão**, sem aprovação de textos, voz ou critérios UX.
[Catálogo](../audio-catalog.md) · [Política](../audio.md) ·
[Interface local](../protocol/audio-local.md) ·
[Perfil aprovado do seletor](../decisions/0023-politica-anuncios-experimental.md).

## Objetivo e entrega

Preparar o trio de modelo/cloud para revisar o conteúdo antes de gerar vozes.
O seletor experimental da #31 está concluído. Permanecem pendentes compreensão,
interrupções e carga da #5, aprovação do conteúdo e lote de voz da #32.

A [planilha](issue-32-revisao-textos.csv) apresenta os 179 textos existentes,
IDs, seletores, hashes, contagens e observações para revisão. **Todas as linhas
estão pending**, com audio_status=not_generated. Não são 179 aprovações.
O [inventário verificável](issue-32-preparacao.json) registra os hashes canônicos
conforme o formato da ferramenta, sem modificar phrases.json ou manifest.json.
Alterar a planilha não modifica o catálogo executado nem autoriza release.

| Verificação atual | Resultado |
|---|---|
| Estrutura e correspondência texto/manifesto | Válidas |
| Conteúdo | 3 avisos locais + 176 frases visuais |
| Texto mais curto/mais longo | 4/59 pontos de código, todos dentro de 120 |
| Frases visuais por estado | 44 unknown, 44 approaching, 44 receding, 44 crossing |
| Áudios gerados/revisados | 0/0; 179 ausentes |
| Distribuição operacional | Bloqueada; catálogo draft |

A contagem de caracteres não mede duração de fala nem compreensão. Não estimar
que uma frase cabe em 1000 ms por ser curta. A geração real terá de medir WAV,
idade no início, interrupções e entendimento do conteúdo cortado.

## Pontos concretos para revisar

1. **Avisos locais:** “Atenção”, “Assistência visual indisponível” e “Assistência
   visual restabelecida” são hipóteses. Verificar se distinguem urgência de
   disponibilidade e se silêncio é interpretado incorretamente como segurança.
2. **Direção:** “à esquerda/ao centro/à direita” refere-se aos óculos na captura,
   não à direção da caminhada. Observar compreensão após mudança da cabeça.
3. **Movimento:** “aproximação/afastamento aparente” pode exigir explicação.
   Não retirar a incerteza e afirmar aproximação física sem evidência.
4. **Cruzamento:** “com movimento lateral aparente” é preciso, mas comprido.
   Proposta para comparação textual posterior: “cruzando a imagem”. Por exemplo,
   comparar “Pessoa à esquerda com movimento lateral aparente” com “Pessoa à
   esquerda cruzando a imagem”. A alternativa não está no catálogo e não está
   aprovada; validar entendimento antes de propor versão nova.
5. **Escadas:** up/down conhecido permite frase de sentido; sentido unknown usa
   “Escada”. Não promete borda, distância ou passagem segura. As combinações
   textuais de movimento não demonstram tracking de escadas; hoje o especialista
   pode fornecer ID nulo, sem movimento conhecido.
6. **Unknown:** movimento unknown/stable gera frase sem movimento. Omissão não
   significa alvo parado, ausência de risco ou falha obrigatória. Classe unknown
   não tem frase visual neste catálogo; ampliar classes exige decisão própria.

Não mudar IDs, versões, hashes, seletores ou os textos operacionais nesta etapa.
Quando uma alteração de conteúdo for aprovada, atualizar catálogo e seletor
juntos conforme a #32/#25: a resolução atual exige igualdade exata do texto.
Mudar só o WAV ou a planilha causaria divergência ou fala incorreta.

## Roteiro de bancada proposto

Primeiro confirmar metadados, eventos e lógica com a simulação existente, sem
participantes ou gravação de voz. Não confundir essa verificação com teste de
compreensão. Depois, com áudio autorizado, testar os casos abaixo no computador.
Não é necessário que Bryan implemente drivers ou tenha as placas.

| Caso | Estímulo/condição | Referência a observar |
|---|---|---|
| A01 | Urgência local sem rede | Vibração independe do áudio; aviso local é hipótese separada |
| A02 | Disponibilidade perdida e oscilação | Aviso estabilizado; não anunciar cada oscilação |
| A03 | Recuperação após resultados novos | Estado atual, sem reproduzir transições antigas |
| A04 | Pessoa com direção/movimento unknown | Só “Pessoa”; não concluir que está parada |
| A05 | Pessoa à esquerda, sem movimento conhecido | Direção relativa à imagem capturada |
| A06 | Pessoa com aproximação aparente | Compreender incerteza, sem inferir TTC/distância |
| A07 | Carro com movimento lateral aparente | Cruzar imagem não autoriza atravessar |
| A08 | Escada de descida à direita | Sentido/classe não localizam borda nem risco geométrico |
| A09 | Dois IDs com mesmo conteúdo em cooldown | Registrar possível supressão de outro alvo, não contagem de pessoas |
| A10 | Frase visual alcança idade de 1000 ms | Não iniciar/continuar; registrar conteúdo efetivamente ouvido |
| A11 | Direcional com giro >15° ou orientação inválida | Cancelar; não retomar conteúdo vencido |
| A12 | Urgência local interrompe visual pendente/em reprodução | Prioridade local; sem atrasar vibração nem retomar fala antiga |

A01/A12 verificam lógica simulada no computador; apenas firmware/bancada podem
comprovar tempo sensor→vibração e reprodução física. Avisos locais P0/P1 não
herdam validade de captura de 1000 ms; ela é das sugestões visuais P2.
Uma única pendente, cooldown e expiração permanecem os já definidos, sem novo
limiar. Não ampliar validade para terminar uma frase.

### Proposta de ensaio de compreensão, ainda sem participantes

Para revisar viabilidade, propor 12 condições acima, alternando a ordem e
separando classe, classe+direção e classe+direção+movimento. Não chamar isso de
amostra mínima aprovada nem de estudo conclusivo. O grupo deverá aprovar número
de participantes/repetições e supervisão/ética antes de recrutar ou executar.

Após cada estímulo, pedir que a pessoa relate o que entendeu **antes** de
mostrar a resposta esperada. Registrar classe, direção, movimento, incerteza e
expectativa de ação como correto/incorreto/inconclusivo/não aplicável, com
numerador/denominador por condição. Separar percepção de “seguro para andar”
como interpretação indevida; não induzir navegação real no teste.

Medir início/fim/interrupção de fala, idade no início/fim, motivo de descarte,
conteúdo efetivamente ouvido e esforço percebido. Como proposta simples,
registrar esforço de 1 (muito baixo) a 5 (muito alto), sem alegar instrumento
psicométrico validado. A escala e critérios quantitativos permanecem pendentes.
Não fixar aprovação de compreensão em qualquer percentual sem decisão prévia.
Não somar clocks VM/ESP; intervalos físicos precisam do procedimento da #19.

A [ficha em branco](issue-32-ficha-compreensao.csv) organiza registros privados,
sem nomes/contatos. Campos vazios são medições pendentes, nunca zero. Copiar
para results/ antes de preencher; respostas individuais/dados pessoais não vão
ao Git. Não marcar revisão auditiva approved sem a escuta/revisão humanas.

## O que precisa ser decidido antes de gerar o lote

| Decisão | Responsável/frente | Estado |
|---|---|---|
| Aprovar textos e eventuais alternativas, mantendo IDs/mapeamento coerentes | Trio modelo/cloud e revisão #25 | Pendente |
| Voz própria autorizada ou provedor TTS, configuração, plano, direitos e orçamento se houver | Grupo; conteúdo na #32 | Pendente |
| Perfil de reprodução, tamanho/armazenamento e interface com WM8960 | Frente de firmware #18/#25 | Pendente; sem escolher taxa/PCM silenciosamente |
| Revisores de pronúncia/compreensão, amostra, escala, critérios e ética | Grupo #5/#32 | Pendente |

WAV PCM16 mono/16 kHz da fixture é somente teste de silêncio, não perfil aprovado.
Nenhum provedor foi contratado/escolhido. Direitos de voz/dados não são herdados
da AGPL do software. Conferir termos oficiais do provedor escolhido antes de
qualquer geração; esta entrega não recomenda nem compara produtos TTS.

## Próximos passos

1. Revisar a planilha e registrar propostas/discordâncias por ID.
2. Consolidar decisão sobre os textos e a interface; não aprovar lote em massa
   a partir da validação estrutural ou da aprovação do seletor #31.
3. Aprovar voz/direitos e formato, gerar amostra autorizada e medir duração/cortes.
4. Aprovar ensaio e realizar revisão auditiva/compreensão; corrigir e reouvir.
5. Gerar/validar release e entregar pacote à #26/#18 conforme os comandos
   existentes do catálogo. Sem atalhar aprovações com arquivos de silêncio.

As issues #5/#32 permanecem abertas. Não houve TTS, voz clonada, áudio real,
participante, mudança de contrato/política, nova dependência, infraestrutura ou
cobrança. O feedback tátil local continua independente de nuvem e áudio.

## Verificação reproduzível

Em macOS/Python 3.11.16, 65 testes existentes de política/HTTPS/arbitragem local/
catálogo passaram em 2,651 s, sem falhas, erros ou skips. Planilha conferida
contra os 179 IDs/textos/hashes do catálogo e manifesto; ficha sem registros.
Validação normal: metadata_valid=true, distribution_ready=false; validação de
release retorna 2 como esperado. check_docs: 103 Markdown, zero problemas;
git diff --check sem erros.

```sh
PYTHONPATH=src:tests python -m unittest test_audio test_simulator_https test_local_audio test_audio_catalog -v
PYTHONPATH=src python -m sonar_vision.audio_catalog validate docs/catalog
python scripts/check_docs.py
git diff --check
```

Confirmar também o bloqueio esperado do release incompleto (saída 2):

```sh
PYTHONPATH=src python -m sonar_vision.audio_catalog validate docs/catalog --require-release
```

Testes verificam software e integridade. Não são revisão de pronúncia,
compreensão, formato do hardware ou aprovação dos 179 textos.
