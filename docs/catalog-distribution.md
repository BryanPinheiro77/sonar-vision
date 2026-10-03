# Distribuição do catálogo de áudio — #26

Distribuição autenticada do catálogo de vozes para os óculos, com versão e
verificação de integridade. Responsável: Julio. Decisão:
[ADR 0009](decisions/0009-distribuicao-catalogo.md). Depende da
[interface de áudio local da #25](protocol/audio-local.md) e reutiliza a API
e a credencial da [#24](api.md). Matheus prepara frases, arquivos e manifesto
(#32); o firmware (#18) armazena e reproduz.

Não implementa download durante risco urgente, geração dinâmica de voz, banco
de dados nem firmware.

## Visão geral

```text
#32 (bancada)        API #24 (HTTPS + Bearer)          óculos (#18)
pacote liberado ──►  valida e carrega na memória  ──►  baixa fora de urgência,
manifest + WAV       GET /v1/catalog/manifest          confere hash/tamanho,
                     GET /v1/catalog/files/<path>      instala de forma atômica
```

## Pacote publicado

Um diretório com:

- `manifest.json`, no formato da #32 (`schema_version`, `catalog_version`,
  `status`, `phrase_version`, `approval`, `profile`, `entries`);
- `audio/*.wav`, somente os arquivos referenciados pelo manifesto;
- opcionalmente `phrases.json`, `SHA256SUMS` e `PACKAGE_KIND.txt`, que vêm do
  pacote ZIP da #32 e **não são servidos**.

Na inicialização, a API recusa o pacote (e não sobe) quando encontra:

| Problema | Motivo registrado |
|---|---|
| Diretório ou manifesto ausente, JSON inválido ou com chave duplicada | `package_missing`, `manifest_missing`, `manifest_not_json` |
| Arquivo inesperado na raiz, ou WAV não referenciado em `audio/` | `unexpected_file`, `unreferenced_file` |
| Caminho fora do padrão `audio/<nome-minúsculo>.wav` (traversal, absoluto, drive, ADS, oculto, subpasta) | `audio_path_invalid` |
| Arquivo removido, alterado (hash ou tamanho) ou que não é WAV PCM | `audio_file_missing`, `audio_hash_mismatch`, `audio_size_mismatch`, `audio_not_pcm_wav` |
| Formato ou frames diferentes do `profile` | `audio_format_mismatch`, `audio_metadata_mismatch` |
| PCM incompleto: bytes lidos ≠ frames × canais × bytes por amostra, mesmo com hash e tamanho coerentes no manifesto | `audio_truncated` |
| Versão de schema não suportada, `status` diferente de `released`, aviso essencial ausente ou sem áudio | mesmas regras do dispositivo (#25) |
| Aprovações da interface, do firmware ou do provedor ausentes | `approval_missing` |
| **Origem ou licença não declarada**, revisão auditiva não aprovada, áudio `synthetic_fixture` | `rights_missing`, `review_not_approved`, `origin_not_distributable` |

### Origem e licença

A API só publica áudio com `rights.license`, `rights.distribution_reference`
e `rights.voice_permission_reference` preenchidos e revisão aprovada. São
**declarações humanas** registradas na #32: a API não verifica termos de
serviço. Nada aqui presume que áudio gerado por ElevenLabs ou outro provedor
possa ser relicenciado como AGPL-3.0. Conferir os termos vigentes do serviço e
a autorização da voz antes de liberar o pacote. Áudios **não** entram no Git.

## Rotas (mesma credencial da #24)

| Rota | Resposta |
|---|---|
| `GET /v1/catalog/manifest` | `200`: bytes exatos do manifesto; `ETag` com o SHA-256 do manifesto; `X-Catalog-Version`. Com `If-None-Match` igual: `304` sem corpo |
| `GET /v1/catalog/files/<path>` | `200` `audio/wav`, com `ETag` e `X-Content-SHA256` iguais ao hash declarado; somente caminhos referenciados |
| Sem credencial ou credencial inválida | `401 {"error":{"code":"unauthorized"}}` |
| Nenhum catálogo publicado | `404 {"error":{"code":"catalog_unavailable"}}` |
| Caminho fora do catálogo | `404 {"error":{"code":"not_found"}}` (mesma resposta, exista ou não no disco) |

Todas as respostas usam `Cache-Control: no-store`. Não existem URLs públicas,
assinadas ou permanentes: todo acesso exige o token individual por HTTPS
validado, e o log nunca registra o token (eventos `catalog_manifest` e
`catalog_file`, com dispositivo, versão, caminho e bytes).

## Como o firmware obtém e valida o áudio essencial

Modelo de referência executável em `src/sonar_vision_local_audio/updater.py`
(especificação, **não** firmware):

1. **Nunca baixar durante urgência local.** Checar antes do manifesto e antes
   de cada arquivo, e de novo depois da última transferência, logo antes de
   instalar. Se a urgência começar em qualquer ponto, abandonar e manter o
   catálogo e o ETag atuais (`deferred:urgent`). Atualizar no boot, em repouso ou em
   manutenção, nunca no caminho do alerta.
2. Pedir o manifesto com `If-None-Match` do catálogo instalado; `304` →
   `up_to_date`, sem baixar nada.
3. Baixar cada arquivo referenciado e conferir tamanho e SHA-256 **antes** de
   aceitar. Arquivo corrompido em trânsito é baixado de novo uma vez; se
   persistir, `failed:integrity`.
4. Instalar só pelo `install()` da #25: troca atômica, perfil idêntico ao do
   firmware, `released` e três avisos essenciais com áudio. Senão, `rejected:<motivo>`.
5. Qualquer falha (`catalog_unavailable`, rede, integridade, incompatibilidade)
   mantém o catálogo e o ETag anteriores. Se o aparelho nunca teve catálogo,
   funciona sem voz: a vibração não muda e os avisos essenciais geram só
   diagnóstico (#25).

Os avisos essenciais devem estar instalados **antes do uso**. A recomendação é
provisionar o primeiro catálogo na bancada, por cabo ou na rede do laboratório,
e não depender da primeira conexão em campo.

## Preparar e atualizar um pacote

1. Matheus gera e valida o catálogo com a ferramenta da #32
   (`validate --require-release`), com aprovações, direitos e revisão.
2. Extraia o pacote para uma pasta nova e versionada fora do Git, por exemplo
   `.local/catalog/1.0.0/`.
3. Configure `SONAR_API_CATALOG_DIR` com essa pasta e reinicie a API. Se o
   pacote for recusado, o processo para e mostra o motivo.
4. Para atualizar, publique a versão nova em **outra** pasta, troque a variável
   e reinicie. A pasta anterior serve para voltar atrás. Os óculos detectam a
   mudança pelo ETag.

## Configuração

| Variável | Padrão | Observação |
|---|---|---|
| `SONAR_API_CATALOG_DIR` | ausente | sem ela, as rotas respondem `catalog_unavailable` |

As demais variáveis estão em [api.md](api.md).

## Testes

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_catalog_distribution.py -v
```

No PowerShell: `$env:PYTHONPATH = "src"` e, depois, `python -m unittest ...`.

Os pacotes de teste são gerados em pastas temporárias com silêncio sintético
e referências `test:*`; não são vozes nem pacotes distribuíveis. Os testes
cobrem pacote válido, pacote ou manifesto ausente, caminhos fora do catálogo,
arquivos removidos, extras e corrompidos, formato e versão incompatíveis,
origem, licença e revisão ausentes, atualização sem mudança, urgência antes e
durante a transferência, catálogo indisponível, falha de rede, corrupção em
trânsito (com nova tentativa) e as rotas HTTP com e sem credencial, incluindo
a atualização de ponta a ponta pela API. Sem `.[api,api-dev]`, só as rotas HTTP
aparecem como skipped.

## Limitações

- Sem retomada parcial (`Range`): um arquivo que falha é baixado de novo inteiro.
- O pacote fica na memória do processo (até 64 MiB). Trocar de pacote exige reiniciar.
- O hash detecta alteração, mas não autentica a origem: não há assinatura do
  pacote. A confiança vem do TLS validado e de quem tem acesso ao servidor.
- Um único catálogo publicado por vez, sem negociação de versão ou perfil por
  dispositivo; o aparelho recusa o que não for compatível.
- O perfil de áudio continua candidato até a revisão da #18.
- Nada foi validado em hardware.
