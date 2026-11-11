# Consolidação da política de anúncios — #5/#31

Data: 2026-10-16. Responsável nas issues: Matheus. Preparação da revisão: Bryan.
**Status: perfil experimental de software aprovado por Bryan em 16/10/2026.**
Aprovação: resposta "aprovo" à proposta de parâmetros e ordem de desempate.
[Registro e hash](issue-31-profile-approval.json) ·
[ADR0023](../decisions/0023-politica-anuncios-experimental.md).
Referências: [política e implementação](../audio.md),
[contrato 0.1](../protocol/eventos-semanticos.md),
[interface local](../protocol/audio-local.md), [catálogo](../audio-catalog.md).

## Objetivo da revisão

Congelar uma baseline determinística para avaliar anúncios no computador e
preparar a comparação futura da #3. A API já aceita configuração explícita;
não é necessário implementar outro seletor ou esperar as placas para revisar
suas regras. A consolidação não ativa áudio por padrão, gera voz ou altera código.
O trio de Bryan cuida de modelo/cloud; reprodução e medidas físicas ficam com
Mathias, Tarcísio e Weslley. Matheus mantém a responsabilidade por #5/#31/#32.

## Decisão: preservar o perfil já exercitado no laboratório

Usar [audio-experimental-31.json](audio-experimental-31.json), cópia byte a byte
do perfil histórico [audio-lab-52.json](audio-lab-52.json), na avaliação experimental.
Registrar seu hash na rodada. A aprovação congela os valores existentes para
software; não os promove a configuração validada de uso cotidiano.

| Escolha aprovada para software | Valor e consequência |
|---|---|
| Corte de sugestão | Confiança >=0,50; um objeto pode aparecer na observação com score menor e não gerar áudio |
| Cooldown por track | 2000 ms para sugerir estado diferente; presença inalterada não gera narração periódica |
| Supressão semântica | 10000 ms para descrição equivalente entre IDs/epochs, inclusive objetos sem ID |
| Retenção | 30000 ms; presença contínua de track inalterado renova retenção |
| Estado máximo | 32 tracks e 32 descrições por instância; saturação não expulsa supressão ativa |
| Desempate de classe | person, car, motorcycle, bus, bicycle, chair, dining_table, dog, stairs |
| Mudanças de estado | Track previamente sugerido com mudança elegível precede entrada nova |
| Mesmo grupo de prioridade | Ordem de classe, depois maior score, depois ordem dos objetos recebidos |

Ordem de classe é desempate de laboratório, não classificação de risco. Por
exemplo, não garante que escada será anunciada antes de pessoa. Se o grupo
preferir outra ordem, registrar mudança e reavaliar explicitamente antes do aceite.
Os 0,50 do seletor e 0,35 do detector têm funções distintas; não são acurácia.

## Vocabulário existente e limites da aprovação

Objeto: Pessoa, Carro, Moto, Ônibus, Bicicleta, Cadeira, Mesa, Cachorro e Escada.
`unknown` e `traffic_light` não produzem sugestão nesta baseline. Não inventar
idade de pessoa, estado de semáforo ou tipo genérico de mesa não coberto pelo modelo.

Se direção for unknown, omitir lado. Se movimento for stable/unknown, omitir
movimento. Quando a fonte fornecer estado válido, usar "com aproximação aparente",
"com afastamento aparente" ou "com movimento lateral aparente". Escada pode
receber "de subida"/"de descida" do especialista experimental; unknown fica
somente "Escada". Isso não autoriza uso para decidir subir/descer ou atravessar.

Direção/movimento visual continuam unknown no uso de câmera móvel sem caminho
validado. Não preencher esses campos para obter uma frase mais completa.
O catálogo mantém 179 textos propostos, incluindo três avisos essenciais locais.
Os textos "Atenção", "Assistência visual indisponível" e "Assistência visual
restabelecida" ainda dependem da revisão de conteúdo/voz; não são áudios gerados.

## Exemplos para conferir na revisão de software

Cada sequência tem estado/relógio controlado. São expectativas de software,
não medição física ou fala realmente reproduzida.

| Situação | Resultado esperado |
|---|---|
| Pessoa nova com direção/movimento unknown e score0,8 | Sugerir "Pessoa" |
| Mesma pessoa permanece, sem mudar descrição | Silêncio, mesmo depois do cooldown |
| Novo ID/epoch com descrição igual antes de10s | Silêncio; ID novo não basta para repetir |
| Novo ID equivalente ao atingir10s | Pode voltar a ser candidato; ainda passa pelos demais filtros |
| Track muda de esquerda para direita após2s | Pode sugerir mudança; descrição não pode estar em supressão semântica |
| Mudança antes de2s | Não sugerir ainda |
| Dois objetos, um com mudança elegível e outro novo | Priorizar mudança, sem inferir urgência geométrica |
| Pessoa e escada novas elegíveis | Desempate atual favorece pessoa, independentemente de risco físico |
| Cadeira com score0,4 | Observação preservada; sem sugestão pelo corte0,50 |
| Idade mínima conhecida atinge1000ms | Sem sugestão; validade não começa na resposta |
| API não recebe arquivo de configuração de áudio | audio=null |
| Urgência local durante sugestão visual | Arbitragem local cancela fala/pendente; vibração não espera VM |

## Limitações que o aceite precisa reconhecer

- A supressão equivalente pode silenciar uma segunda pessoa ou objeto diferente
  com a mesma descrição. Não é contagem de alvos ou prova de identidade.
- O seletor registra sugestão enviada, não confirmação de reprodução. Se o ESP
  descartar uma sugestão, isso não obriga a VM a repeti-la automaticamente.
- O cooldown é por track/conteúdo, não intervalo global entre todas as frases.
  A reprodução tem fila local limitada; o seletor não controla duração de voz.
- Campos semânticos incorretos do modelo podem produzir frases incorretas.
- Texto <=120 caracteres pode durar mais que1000ms. Gerar voz e medir cortes/
  compreensão é etapa necessária; não ampliar validade para terminar a frase.
- Avisos locais e orientação vêm do firmware, não de classificação de risco na VM.

## O que permitiria avançar em cada issue

| Issue | Aceite necessário / pendência |
|---|---|
| #31, software | Perfil e desempate aprovados; compatibilidade de texto/envelope com #25 testada. Publicação/revisão desta consolidação pendente; sem alegar aprovação física |
| #5, política completa | Além do perfil, avaliar compreensão, cortes e carga conforme roteiro e critérios aprovados; não fechar só com unittest |
| #32, voz | Aprovar voz/provedor/direitos e formato com firmware, gerar lote e revisar auditivamente |
| #3, comparação opcional | Preparar eventos sintéticos já é possível; comparação depende da consolidação da baseline, e chamadas pagas exigem orçamento próprio |

A aprovação cobre o perfil e desempate experimental apresentados a Bryan; não
é aprovação adicional de todos os179 textos, avisos locais, provedor, formato
físico ou release do catálogo. A revisão de compatibilidade com #25 cobre o
envelope0.1 e correspondência exata dos textos existentes; reprodução física
permanece sujeita à revisão da frente de firmware. Não substituir pendências
da #5 por critérios mais fracos para fechá-la. Não atribuir execução física a
Bryan ou contratar provedor/ligar VM para resolver aprovação de conteúdo.

## Reprodução das verificações existentes

Na raiz, com extras de API instalados:

```sh
PYTHONPATH=src:tests python -m unittest test_audio test_simulator_https test_local_audio test_audio_catalog -v
PYTHONPATH=src python -m sonar_vision.audio_catalog validate docs/catalog
python scripts/check_docs.py
git diff --check
```

Não modifica o perfil ou o padrão NullPolicy da API. A validação do catálogo
retorna metadata_valid=true,179 textos,179 áudios ausentes e
distribution_ready=false: sucesso estrutural não é release de voz pronto.

## Resultado da verificação — 16/10/2026

65 testes passaram, zero falhas, erros ou skips. HTTPS real em loopback com
backend simulado; orientação/urgência e catálogo são entradas controladas.
A validação de catálogo confirmou os 179 arquivos de áudio ainda ausentes.
A verificação precedeu a aprovação; os mesmos bytes de configuração foram
congelados após a resposta de Bryan. Nenhuma voz gerada e nenhuma VM criada.
