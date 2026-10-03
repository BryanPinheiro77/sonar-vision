# Catálogo versionado de frases e voz — #32

- Data: 2026-10-02. Responsável previsto: Matheus (@Matheus-xz), com apoio de IA.
- Status: proposta de textos e implementação da ferramenta; lote de vozes pendente.
- Referências: [#32](https://github.com/BryanPinheiro77/sonar-vision/issues/32),
  [política #5/#31](audio.md), [contrato 0.1](protocol/eventos-semanticos.md),
  [proposta ADR 0005](decisions/0005-catalogo-de-voz.md).
- Dependências: #25 (interface/revisão), #18 (formato/reprodução), #26 (distribuição).

## Requisitos confirmados e decisões pendentes

A issue autoriza preparar textos agora. Frases operacionais, provedor, voz,
plano/direitos e formato final exigem aprovação; nenhuma escolha é presumida.
O catálogo proposto não altera mensagens JSON 0.1 nem adiciona campos às sugestões.
A #25 deve revisar IDs/versões e eventual migração antes da integração física.

`docs/catalog/phrases.json` contém 179 propostas em português, com IDs estáveis:
3 avisos essenciais locais e 176 frases visuais completas. `manifest.json`
vincula cada ID ao texto/hash e, quando disponível, ao arquivo de áudio.
Todas as entradas iniciais têm audio=null; status=draft, perfil e aprovações nulos.
Não há arquivos de voz final, fornecedor contratado ou voz clonada nesta entrega.

| ID local proposto | Texto proposto | Origem do evento |
|---|---|---|
| local.urgent | Atenção | Estado geométrico local da #9 |
| local.visual_unavailable | Assistência visual indisponível | Estado local estabilizado da #18 |
| local.visual_restored | Assistência visual restabelecida | Recuperação local estabilizada da #18 |

São hipóteses de UX, não frases aprovadas. O aviso urgente genérico não afirma
classe nem direção; associação de objeto ao risco exige validação própria.
Não produz comandos de parar/desviar ou autorização de travessia.

As frases visuais reutilizam vocabulário da #31: classe, direção conhecida,
movimento aparente e sentido da escada conhecido quando fornecido pela #16.
Exemplos: “Pessoa”, “Pessoa à esquerda”, “Carro ao centro com aproximação
aparente”, “Escada de descida à direita”. Unknown/stable de movimento usam texto
sem movimento; não há frases para classe unknown ou semáforo. Nenhuma frase
infere idade, distância real ou TTC. Escadas no catálogo não implementam detector.

Frases completas evitam composição de arquivos que poderia alterar prosódia.
A cobertura de todas as combinações é opção de conteúdo para revisão: não afirma
capacidade de armazenar 179 WAVs no ESP32. A aprovação de tamanho e perfil pelo
firmware deve preceder o lote; reduzir vocabulário exige alinhamento com a #31.

## Implementação, formato e integridade

Ferramenta `src/sonar_vision/audio_catalog.py`: biblioteca padrão Python >=3.11,
sem rede, TTS, modelos ou dependências novas. Os testes ficam em
`tests/test_audio_catalog.py`, com unittest, conforme o padrão existente.

Formato local de trabalho v1, ainda proposto para revisão #25:

- Frases: schema_version, phrase_version, locale, approval_reference e phrases.
  Cada frase registra id, kind, event/selector, text e directional.
  kind separa essential_local de visual; selector registra classe/direção/
  movimento/sentido. IDs são únicos; textos/seletores ambíguos são rejeitados.
- Manifesto: schema_version, catalog_version, status, phrase_version,
  phrases_sha256, approval, profile e entries.
  approval contém interface_reference, firmware_reference e provider_reference.
- Entry: id, text, text_sha256 e audio. Texto deve coincidir exatamente com
  phrases.json, inclusive acentos; aceita somente NFC, sem controles/invisíveis.
- Audio: path relativo audio/*.wav, sha256, size_bytes, frames, duration_ms,
  origin, rights e review.
- Origin: kind (tts, recording, synthetic_fixture), provider, plan, voice,
  configuration, generation_version e source_reference.
  configuration aceita somente model/speed/pitch/stability/similarity/style,
  com valores escalares finitos. Não registrar token, chave, texto de participante,
  configuração secreta ou identificador pessoal.
- Rights: license, distribution_reference, voice_permission_reference e attribution.
  Usar referência opaca ao documento de direitos/plano e autorização da voz;
  attribution=null somente quando os direitos registrados dispensarem atribuição.
- Review: status, pronunciation_reference e comprehension_reference.
  approved exige referências de ambos os registros de revisão humana.
- Profile: container=wav, encoding=pcm, sample_rate_hz, channels e
  sample_width_bytes. Sem perfil operacional padrão. O validador inicial suporta
  WAV PCM; outro formato exige discussão #18/#25 e implementação explícita.

Duration_ms é ceil(frames*1000/sample_rate_hz), tamanho inclui cabeçalho WAV;
hash é SHA-256 do arquivo inteiro. Frases_sha256 usa a serialização JSON da
ferramenta (UTF-8, ensure_ascii=False, sort_keys=True, indent=2 e LF final),
evitando falso conflito por CRLF/indentação do checkout. Text_sha256 usa bytes
UTF-8 do texto exato, sem normalização silenciosa. SHA256SUMS do pacote usa
os bytes reais de cada arquivo, inclusive JSON e declaração do tipo de pacote.

Rejeita arquivos ausentes, IDs/paths duplicados, texto divergente, hash alterado,
metadados/formato incorretos, WAV truncado, chaves JSON duplicadas e NaN.
Paths absolutos, traversal, caminhos Windows/ADS e symlink para fora da raiz são
rejeitados. Limites da ferramenta: 512 frases, JSON 2 MiB, áudio individual
32 MiB, conteúdo total do pacote 64 MiB; não são orçamento de memória do ESP32.
Texto permanece limitado a 120 pontos de código pelo contrato.

Integridade não comprova autenticidade, permissão, transcrição real ou compreensão.
O validador checa referências declaradas; a pessoa responsável deve conferi-las.
Não é possível provar automaticamente que um WAV fala o texto esperado por hash.
A revisão auditiva permanece obrigatória.

## Comandos reproduzíveis

Na raiz, PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -B -m sonar_vision.audio_catalog validate docs/catalog
python -B -m unittest discover -s tests -p test_audio_catalog.py -v
python -B -m unittest discover -s tests -v
git diff --check
```

O catálogo textual válido informa metadata_valid=true, phrases=179,
essential_local=3, missing_audio=179 e distribution_ready=false.
`validate --require-release` retorna 2 para essa proposta, de forma esperada:

```powershell
python -B -m sonar_vision.audio_catalog validate docs/catalog --require-release
```

Fixtures sem provedor, credencial ou arquivos exclusivos de outro computador:

```powershell
python -B -m sonar_vision.audio_catalog fixture --output results/catalog-fixture-01
python -B -m sonar_vision.audio_catalog validate results/catalog-fixture-01
python -B -m sonar_vision.audio_catalog pack results/catalog-fixture-01 --fixture --output results/catalog-fixture-01.zip
git check-ignore results/catalog-fixture-01/audio/local.urgent.wav results/catalog-fixture-01.zip
```

Fixture gera silêncio original de 100 ms, WAV PCM16 mono 16000 Hz, apenas para
teste de arquivos/metadados. Esses números não são decisão de formato final.
Marca origin.kind=synthetic_fixture, voice=silence-not-speech e revisão pending.
Não é voz, não avalia pronúncia e não pode ser lançado como áudio operacional.
`pack --fixture` aceita somente draft com todos os arquivos synthetic_fixture;
PACKAGE_KIND.txt marca TEST FIXTURE - SILENCE - NOT FOR DEVICE.
Arquivos de teste próprios: AGPL-3.0-only. Isso não licencia áudios externos.

`draft --output results/catalog-draft-02` cria nova proposta textual sem WAV.
Comandos de geração usam diretório novo e falham se existir; pacotes nunca são
sobrescritos. Repita com sufixo novo ou revise conteúdo em cópia local controlada.
Nenhum áudio ou pacote gerado deve entrar no Git: usar results/ já ignorado.

## Preparação e atualização do lote final

1. Grupo revisa frases locais/visuais, compreensão e ausência de comandos de
   locomoção/travessia; registra aprovação #5/#25 em approval_reference.
2. Bryan e firmware revisam IDs, formato, requisitos de reprodução e tamanho;
   registrar interface_reference e firmware_reference. Medir duração em relação
   à validade visual de 1000 ms sem aumentá-la para evitar frases cortadas.
3. Aprovar provedor, plano, voz, configuração e direitos de gerar/distribuir;
   registrar provider_reference e documentos de cada artefato. Não selecionar
   ElevenLabs automaticamente nem presumir licença AGPL, voz livre, atribuição
   dispensada ou permissão de clonagem. Conferir termos oficiais vigentes do
   serviço escolhido antes da contratação/geração. Não existe chamada TTS aqui.
4. Gerar/gravar somente após essas aprovações, com credencial fora do Git/logs e
   voz autorizada. Guardar arquivos privados em results/catalog-release-VERSION/
   audio/ e origem/configuração/versão no manifesto. Nenhum download/upload
   automático. Obter arquivos por geração autorizada própria ou fonte permitida;
   não há URL de voz final porque nenhum provedor foi escolhido.
5. Converter para o perfil acordado. Preencher metadados medidos; wav_metadata
   permite inspecionar bytes no Python. Não inventar hash/duração/tamanho.
   Alinhar textos/IDs ao catálogo aprovado; registrar pronúncia/compreensão.
6. Executar revisão auditiva: ouvir cada arquivo identificado, comparar transcrição
   e acentos com phrases.json, verificar truncamento, distorção, volume, duração,
   naturalidade e compreensão. Revisor registra versão, ID, configuração, achados
   e resultado no documento privado referenciado; corrigir e reouvir rejeitados.
   Teste com participantes exige consentimento, supervisão e revisão ética.
   Nenhuma revisão humana é marcada aprovada automaticamente.
7. Incrementar phrase_version quando mudar texto/seletores/aprovação; incrementar
   catalog_version para mudanças de conteúdo, arquivos, origem ou aprovações.
   Versões de lançamento sem sufixo draft, status=released apenas após revisão.
   Manter versões anteriores imutáveis para reprodução; trocar hash/revisão quando
   regerar arquivo. `--previous` detecta reutilização de versão com conteúdo diferente.
8. Validar release e empacotar com os comandos abaixo. A #26 distribui; #18 valida
   compatibilidade, provisiona avisos essenciais nos óculos e reproduz sem rede.

```powershell
python -B -m sonar_vision.audio_catalog validate results/catalog-release-VERSION --require-release
python -B -m sonar_vision.audio_catalog pack results/catalog-release-VERSION --output results/catalog-release-VERSION.zip --previous results/catalog-release-PREVIOUS
```

VERSION/PREVIOUS são placeholders; para o primeiro lançamento, omitir --previous.
Release exige todas as frases com arquivo, direitos, revisão e aprovações
declaradas; arquivos synthetic_fixture continuam bloqueados mesmo com referências.

## Entrega para #26/#18 e comportamento esperado

Pacote ZIP determinístico contém phrases.json, manifest.json, audio/*.wav,
PACKAGE_KIND.txt e SHA256SUMS; o comando também apresenta hash SHA-256 do ZIP.
Todos os avisos essenciais fazem parte do arquivo, disponível offline após
provisionamento. Mapeamento: (catalog_version,id) -> entry.audio.path/hash -> WAV.
lookup_text associa texto exato da #31 a ID visual; “Atenção” não é um detalhe
visual. Essa é interface interna proposta, não campo novo do protocolo 0.1.

A distribuição deve usar origem confiável e versão compatível; hash sozinho
não autentica pacote. A #26 deve verificar SHA256SUMS e todos os arquivos antes
de expor atualização; a #18 decide armazenamento/instalação atômica e rollback.
Esta ferramenta produz pacote, não instala nem executa firmware.
Arquivo/aviso ausente, hash inválido ou catálogo incompatível não deve gerar
fala substituta inventada, nem download/TTS no caminho crítico. Registrar falha
e manter independência tátil; a política operacional exata deve ser consolidada
na #25/#18. Nenhum aviso local depende de inferência/rede/VM.
Validade, orientação, uma pendente e interrupções permanecem com #18.

## Matriz de aceitação e pendências

| Critério #32 | Evidência nesta entrega | Pendência |
|---|---|---|
| Frases curtas, essenciais/visuais, sem travessia | 179 propostas, classes e seleção testadas | Aprovação #5/#25 e UX |
| Provedor/voz/plano/direitos | Metadados explícitos e bloqueio de release | Escolha aprovada e geração real |
| Formato/qualidade/duração/tamanho/versão | Perfil obrigatório para arquivo, metadados WAV medidos | Formato/qualidade acordados com firmware |
| Manifesto, IDs e integridade | JSON v1, hashes e pacote offline | Revisão da interface #25 |
| Arquivos ausentes/duplicatas/divergências/hashes | Testes automatizados | Revisão auditiva real |
| Pacote #26/#18 e avisos offline | ZIP completo; fixture reproduzível | Lote final, provisionamento e teste físico |
| Testes próprios e evidências | unittest e comandos neste guia | Evidências locais registradas abaixo após execução |
| Documentação/índice/ADR | Guia, índice e ADR 0005 proposto | Revisão humana; ADR ainda não aceito |
| PR reproduzível | Fontes e fixtures próprias | Commit/push/PR não realizados sem solicitação |
| Privacidade/origem/licença | Nenhum segredo/voz externa; artifacts em results/ | Verificação dos direitos do lote real |

As pendências de aprovação, síntese e revisão auditiva impedem concluir #32.
O caminho tátil não é acessado; validação física/rede desligada ainda depende
do hardware. Não houve teste com participantes, saída sonora real ou contratação.

## Evidência local

Execução em Windows/PowerShell, Python 3.12.7, em 2026-10-02:

- 20 testes próprios do catálogo passaram, incluindo mapeamento dos 176 textos
  visuais contra AudioPolicy, limites, arquivos/hashes, traversal, versionamento,
  CRLF, direitos/revisões pendentes e empacotamento offline.
- Suíte completa: 97 testes encontrados, 93 aprovados e 4 skipped por ausência
  das dependências opcionais do ByteTrack real; tempo reportado: 11,549 s.
- validate docs/catalog retornou 0: metadata_valid=true, phrases=179,
  essential_local=3, missing_audio=179, distribution_ready=false.
- validate docs/catalog --require-release retornou 2, conforme esperado.
- Fixture local results/catalog-fixture-32-01 gerou 179 WAVs silenciosos;
  validação retornou 0 e synthetic_audio=179, auditory_reviewed=0.
- pack --fixture produziu ZIP de 183 arquivos, com SHA-256
  9245f553e50df6d34197ef97aedc35f50fa7b56b5a82ee7a8fd2f5b147187241.
  O pacote de teste permanece em results/ e fora do Git.
- pack sem --fixture rejeitou a tentativa de release com retorno 2 e não criou
  o arquivo de saída. Arquivos sintéticos nunca viraram lançamento operacional.
- git check-ignore confirmou exclusão dos WAVs/pacote em results/;
  diff --check e verificação dos novos arquivos sem erro de whitespace.
- Nenhuma voz real foi gerada ou ouvida; aprovações e formato final continuam
  pendentes. Os testes de release usam declarações fictícias somente no ambiente
  temporário para verificar a lógica, sem registrar aprovação de silêncio real.

No PR, vincular #32 como entrega parcial (não usar Closes #32), descrever problema,
escolha da biblioteca padrão/frases completas e alternativas na ADR 0005,
anexar estes comandos/resultados e manter as pendências da matriz explícitas.
Matheus deve revisar e explicar os riscos/testes. Commit/push/PR não realizados.
