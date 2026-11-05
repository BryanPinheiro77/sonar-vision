# Guia para o hardware: enviar distância e imagem à API

Entrega de integração das #17/#19/#73. Cloud/modelos: Bryan e seu trio.
Aquisição, cliente HTTPS, montagem e testes físicos: Mathias, Tarcísio e Weslley.
Este guia descreve os endpoints existentes; não altera contratos ou firmware.

Para a montagem e implementação dos drivers, usar o
[mapa de fios confirmado por Bryan](hardware-wiring.md), registrado no ADR 0028.
A pinagem não altera os formatos HTTP abaixo; a aquisição física continua
responsabilidade da frente de hardware/firmware.
As [orientações por componente](firmware-integration.md) distinguem setores
locais para vibração da distância agregada enviada para o painel.

Atualização de 05/11: coleta privada habilitada neste deploy para os testes e
demonstrações autorizados por Bryan. Cada início da aplicação cria uma rodada
nova, limitada a 10 minutos, 3.000 imagens ou 100 MiB, com retenção de 24h.
O ESP não precisa mudar o pedido HTTP para isso. Consultar/exportar pelo
[histórico privado](collection.md); não há treino automático. A coleta não
amplia a janela de execução da VM e não garante gravação após atingir o limite.

## O que está disponível

| Dado | Envio do ESP | Sucesso | Consulta da apresentação |
|---|---|---|---|
| Distância ToF | `POST /v1/demo/tof`, JSON | `204`, corpo vazio | `/demo` e `GET /v1/demo/snapshot` |
| JPEG da câmera | `POST /v1/inference`, multipart | `200`, JSON com `observation` e `audio` | `/demo`, mesmo JPEG recebido e previsões correspondentes |
| Disponibilidade do serviço | `GET /healthz` | `200`, JSON | Não comprova recebimento do sensor |

São dois pedidos independentes. Pode enviar apenas distância antes de concluir
a câmera, e depois habilitar ambos. Não enviar a distância dentro de metadata,
nem imagem/base64 no JSON ToF. Não é necessário implementar MQTT para esses envios.

**Deploy de 04/11/2026:** a mesma instância está preservada e fica parada quando
ociosa. Elastic IP, DNS e certificado público foram configurados e verificados.
O endereço permanece o mesmo ao parar/ligar a VM. A disponibilidade exige uma
janela ativa combinada com cloud; VM parada não recebe pedidos. Não usar o IP
temporário anterior nem a porta 8443 dos primeiros testes.

| Uso | URL definitiva |
|---|---|
| URL base | `https://sonar-vision.bryandev.com.br` |
| Enviar distância | `https://sonar-vision.bryandev.com.br/v1/demo/tof` |
| Enviar JPEG | `https://sonar-vision.bryandev.com.br/v1/inference` |
| Abrir painel | `https://sonar-vision.bryandev.com.br/` |
| Entrada para pessoas, com redirecionamento | `https://bryandev.com.br/sonar-vision` |
| Conferir serviço | `https://sonar-vision.bryandev.com.br/healthz` |

Usar HTTPS na porta padrão **443**. CA pública e token são entregues no material
privado de conexão, fora do Git. O `ca.pem` atual contém ISRG Root X1; o hostname
e a cadeia do certificado foram verificados com ele e com a confiança pública
do sistema. O relógio de calendário do ESP precisa estar correto para validar
certificados; isso é diferente do relógio monotônico de captura.

Manter a URL base configurável no firmware. Configuração de bancada: `device_id=glasses-01`,
`session_id=boot-1`; o identificador é o boot combinado, não autenticação.
O ESP usa diretamente a URL base e os dois POSTs da tabela. Não enviar imagens
ou JSON para o caminho do portfólio nem seguir redirects com o token.
O hardware não precisa de login AWS ou chave IAM: recebe URL, CA, token e boot.
Ao ler `device.token`, remover a quebra de linha final antes de compor o Bearer.

## Informações que cloud deve entregar ao hardware

| Informação | Uso |
|---|---|
| URL base HTTPS e porta | `https://sonar-vision.bryandev.com.br`, porta 443 |
| CA pública confiável | Validar certificado e hostname/IP do servidor; nunca fornecer a chave privada |
| Token individual do dispositivo | Header `Authorization: Bearer TOKEN`; entregar por meio privado, fora do Git/logs/painel |
| `session_id` do boot selecionado | Mesmo valor no ESP e na configuração do painel |
| Credencial de visualização | Usuário `sonar` e senha separada do token ESP; usada somente no painel |
| Limites efetivos e janela de teste | Confirmar disponibilidade antes de ligar o envio e registrar prazo automático da VM |

A credencial identifica o dispositivo; `session_id` não é uma senha. No
servidor, `SONAR_DEMO_DEVICE_ID` deve corresponder à credencial e
`SONAR_DEMO_SESSION_ID` ao boot combinado. Habilitar `SONAR_DEMO_ENABLED=1` e
usar `SONAR_DEMO_SOURCE_KIND=esp32` quando houver captura física real.
O modo simulado é adequado ao ensaio de computador e deve continuar rotulado.
As duas rotas usam a mesma credencial. Sem habilitar o painel, a rota ToF não
é instalada, embora a inferência possa funcionar normalmente.

### Redes diferentes e dados móveis

A porta HTTPS aceita produtores de qualquer IPv4, mantendo Bearer obrigatório
nos dois POSTs. O modo com senha do [painel](demo-panel.md) substitui a allowlist
de espectadores e permite redes móveis sem cadastrar cada IP. A proteção já foi
implantada e testada na AWS. O token ESP e a senha de visualização são distintos.
Usuário do painel: `sonar`; senha entregue apenas no material privado. SSH 22
permanece restrito ao operador.

Não é preciso cadastrar o IP móvel do ESP ou dos espectadores nesse deploy.
Uma reconexão ainda pode interromper TCP: descartar o envio antigo e trabalhar
com aquisições novas. Testar a rede/hotspot real antes da apresentação e manter
uma alternativa ensaiada. Wi-Fi conectado, por si só, não comprova acesso HTTPS.

Cloud continua responsável pela janela de funcionamento, pelo prazo de parada e
pelo IP autorizado de SSH do operador. Mudanças de boot/configuração da API
podem exigir recriação do serviço e reiniciar o estado ao vivo/tracks; combinar
o momento. O modo legado por CIDR existe para outros ensaios, mas não é a
configuração desse deploy protegido por senha.

O painel atual acompanha um boot selecionado pelo operador. **Não existe rota
de registro automático de boot.** A cada reboot do ESP, usar uma nova sessão e
avisar cloud para selecionar esse boot e recriar o serviço. A inferência aceita
sessão nova, mas isso sozinho não reconfigura o painel/ToF. Não reutilizar sessão
antiga com contadores reiniciados. `DELETE /v1/demo/session` encerra a observação;
não é um comando para abrir ou trocar sessão.

## Relógio e contadores no ESP

- Usar milissegundos monotônicos desde o mesmo boot para imagem e ToF, com
  representação de 64 bits e tratamento do rollover do contador nativo.
  `captured_at_ms` corresponde à aquisição, não ao instante posterior do envio.
- `frame_id` e `sequence` são **strings decimais** sem zeros à esquerda, por
  exemplo `"1"`, `"2"`. Cada canal tem seu contador crescente independente.
  IDs têm até 64 caracteres; tempos são inteiros entre 0 e 2^53−1.
- Incrementar contadores mesmo se uma captura/leitura for descartada; lacunas
  são aceitáveis. Não reenviar imagem velha após falha/timeout.
- O timestamp de captura não pode regredir dentro do respectivo canal/sessão.
  Não subtrair o relógio local do ESP do UTC de recebimento da VM.

## Envio 1: distância do ToF

`POST /v1/demo/tof` com `Content-Type: application/json` e Bearer.
Salvar como `tof-valido.json` para o ensaio de computador:

```json
{
  "version": "demo-tof-1",
  "session_id": "boot-1",
  "sequence": "1",
  "captured_at_ms": 1000,
  "distance_mm": 1250,
  "valid": true,
  "quality": "good",
  "sector": "all",
  "zone": null,
  "aggregation": "min_valid_8x8"
}
```

Esse exemplo representa **1,25 m**, enviados como inteiro **1250 mm**. A
agregação significa mínimo somente das zonas válidas da matriz 8×8, com
`sector=all` e `zone=null`. O firmware deve confirmar configuração 8×8 e quais
status nativos do sensor contam como válidos; não chamar uma medida de outra
origem/agregação de `min_valid_8x8`.

Para enviar uma zona individual, usar `aggregation="zone"`, `zone` inteiro
0..63 e setor definido pelo produtor (`all` se não há setor calibrado).
A posição óptica de cada zona precisa ser confirmada pelo hardware. O servidor
aceitar esses campos não valida calibração, alcance ou orientação do sensor.

Quando não houver medida válida, salvar como `tof-invalido.json`:

```json
{
  "version": "demo-tof-1",
  "session_id": "boot-1",
  "sequence": "2",
  "captured_at_ms": 2000,
  "distance_mm": null,
  "valid": false,
  "quality": "invalid",
  "sector": "all",
  "zone": null,
  "aggregation": "min_valid_8x8"
}
```

Essa leitura também recebe `204`; o painel passa a mostrar indisponibilidade.
Não substituir falha por zero. Para leituras válidas, `quality` pode ser `good`
ou `degraded`, conforme os critérios documentados pelo firmware.

Exemplo Bash/curl, com arquivos privados fornecidos pelo operador:

```sh
export SONAR_ENDPOINT='https://sonar-vision.bryandev.com.br'
export SONAR_CA_FILE="$PWD/ca.pem"
export SONAR_TOKEN_FILE="$PWD/credenciais/device.token"
curl --cacert "$SONAR_CA_FILE" --max-time 2 --include \
  -H "Authorization: Bearer $(cat "$SONAR_TOKEN_FILE")" \
  -H 'Content-Type: application/json' \
  --data-binary @tof-valido.json "$SONAR_ENDPOINT/v1/demo/tof"
```

Executar a partir da pasta recebida com `ca.pem` e `credenciais/`. Não executar
com `set -x`, curl `-v` ou
tracing que exponha o header. Token fica num arquivo protegido, nunca no texto
copiado para o grupo. Esse comando envia um exemplo de computador; não comprova
origem física. Para testar falha do sensor, trocar apenas o arquivo por
`tof-invalido.json`. Não repetir a mesma sequência para leituras diferentes.

Limite atual: corpo JSON inteiro até 2048 bytes e até 10 tentativas/s da origem
selecionada. **Sugestão de primeiro ensaio:** 1 leitura/s, sem alterar a taxa de
aquisição ou o laço local. Essa cadência é uma proposta de bancada, não requisito
físico aprovado. Cadência final deve ser combinada entre as frentes.

## Envio 2: imagem JPEG e metadados

`POST /v1/inference` com Bearer e **multipart/form-data** contendo exatamente:

| Parte | Content-Type da parte | Conteúdo |
|---|---|---|
| `metadata` | `application/json` | JSON abaixo, sem campos extras |
| `image` | `image/jpeg` | Bytes binários do JPEG da captura correspondente |

Salvar como `metadata.json`:

```json
{
  "version": "0.1",
  "session_id": "boot-1",
  "frame_id": "1",
  "captured_at_ms": 1500
}
```

O exemplo está entre as duas capturas ToF acima, deliberadamente em outro
instante. No ESP preencher com a captura real. Não enviar MOV, vídeo contínuo,
PNG, base64 nem cabeçalhos de outro formato. O servidor recebe uma sequência
de JPEGs individuais; não é necessário transmitir um arquivo de vídeo.

```sh
curl --cacert "$SONAR_CA_FILE" --max-time 2 \
  -H "Authorization: Bearer $(cat "$SONAR_TOKEN_FILE")" \
  -F 'metadata=<metadata.json;type=application/json' \
  -F 'image=@frame.jpg;type=image/jpeg' \
  "$SONAR_ENDPOINT/v1/inference"
```

`frame.jpg` precisa existir e ser uma captura autorizada ou sintética. O curl
constrói o boundary. No firmware, a biblioteca ou implementação multipart deve
enviar boundary coerente, separadores CRLF e fechamento correto; não definir
apenas o header multipart sem construir o corpo correspondente.

Padrões atuais: corpo multipart inteiro até 524288 bytes, incluindo metadados e
separadores; imagem até 1920000 pixels. Confirmar os valores efetivos no deploy.
A entrada de 640 do modelo não é, por si só, limite da câmera/API. O perfil de
avaliação recente enviou JPEG com lado maior 640 e qualidade 95 no computador;
qualidade numérica da OV2640 não deve ser presumida equivalente. A escolha de
resolução/compressão física precisa ser medida em bancada.

Sucesso: `200 application/json`, com **ambos** os campos `observation` e `audio`.
`audio` pode ser `null` e `observation.objects` pode estar vazio. O formato
completo, IDs, referências e regras de descarte estão no
[contrato 0.1](protocol/eventos-semanticos.md). Não esperar caixas na resposta
0.1: caixas para o painel vêm do diagnóstico correspondente ao JPEG.

Validar o envelope completo antes de usar: sessão, frame e captura devem
corresponder ao pedido; referências de áudio devem corresponder à observação.
Limitar resposta a 16384 bytes e 20 objetos. Áudio é uma sugestão informativa,
não comando para motor; não converter corpo de erro em fala. O catálogo e
a arbitragem local possuem requisitos próprios na [interface de áudio](protocol/audio-local.md).

## Concorrência, erros e reconexão

Manter no máximo uma requisição de inferência ativa por dispositivo e nenhuma
fila de capturas antigas. Para ToF, envio best effort com uma requisição ativa
e sem acúmulo de medidas velhas. O firmware deve serializar/limitar o uplink
sem bloquear aquisição, geometria, motores ou arbitragem urgente. Não prometer
8 FPS até medir a câmera real e a rede da apresentação.

Usar timeout total de 2000 ms para imagem (conexão, envio e leitura), conforme
contrato; limitar também espera de telemetria. Em erro, descartar o pacote
antigo e trabalhar com aquisição nova. Não seguir redirecionamento levando o
token a outro host. TLS exige certificado e hostname/IP válidos; não usar
`setInsecure()`, `-k` ou HTTP como fallback.

| HTTP | Ação de diagnóstico |
|---|---|
| `200` na imagem / `204` no ToF | Envio aceito; `204` não contém JSON para decodificar |
| `400 invalid_request` | Conferir campos, tipos, números e ordem. Frame repetido na inferência também recebe 400 |
| `401 unauthorized` | POST: conferir token ESP. Painel: conferir usuário/senha de visualização |
| `403 forbidden` | ToF: credencial não é da origem selecionada; em ensaios legados pode indicar allowlist |
| `404` na rota ToF | Conferir URL e se o painel foi habilitado no serviço |
| `409 demo_conflict` no ToF | Conferir boot selecionado, sequência, timestamp ou sessão encerrada |
| `413 payload_too_large` | Diminuir carga; conferir bytes, pixels e overhead multipart |
| `415 unsupported_media_type` | Conferir Content-Type global e das partes |
| `429 busy` | Reduzir envio; descartar aquisição antiga, sem fila/reenvio imediato |
| `500 internal_error` / `503 unavailable` | Registrar código e avisar cloud; seguir operando localmente |
| Sem resposta / falha TLS | Conferir Wi-Fi, internet, relógio/CA, hostname e disponibilidade da VM |

O servidor pode continuar ocupado após timeout de inferência; não inundar com
retries. Reconexão usa novas aquisições e contadores crescentes no mesmo boot.
Reboot usa nova sessão combinada com cloud. Nunca imprimir Bearer, imagens ou
dados pessoais nos logs de diagnóstico compartilhados.

## Como demonstrar e verificar os dois canais

1. Cloud confirma endpoint, CA, token, boot e IPs permitidos; hardware confirma
   que a rede não interfere no laço local. Abrir `GET /healthz` validando TLS.
2. ESP envia ToF real e o navegador abre `URL-BASE/demo`. Aproximar/afastar um
   alvo em bancada e conferir mm, sequência e idade. Sem câmera, imagem fica
   aguardando e a distância pode funcionar normalmente.
3. ESP envia dois JPEGs visualmente distintos, com frames crescentes. Conferir
   no painel a imagem efetivamente recebida, frame/hash e origem. Os testes
   em computador devem continuar identificados como simulados.
4. Usar ambos juntos; imagem e ToF possuem timestamps/estados independentes.
   A distância não está automaticamente associada a uma pessoa ou caixa YOLO.
5. Enviar leitura inválida e interromper cada canal separadamente. Com idade
   desde recebimento ≥5 s fica atrasado; aos 30 s o payload ao vivo expira.
   Repetir sequência deve falhar, sem substituir a última medição aceita.
6. Interromper rede/API em bancada e comprovar que sensores e alerta tátil
   continuam locais. Registrar fonte, versões, valores e resultados reais.

Aceitar upload não significa salvá-lo permanentemente. Ao vivo mantém somente
o último JPEG/ToF por tempo limitado. Para revisão posterior, cloud deve ativar
[coleta autorizada por rodada](collection.md), conferir os limites e exportar
antes da remoção da VM. Não há treino automático com os uploads.

## Ordem até a apresentação

Proposta de execução: primeiro ToF real até a nuvem/painel; depois câmera real;
em seguida ensaio conjunto com falha de rede, evidência exportada e horário de
apresentação coberto pelo deploy. Não manter uma VM de teste ligada por uma
semana: planejar janelas com prazo automático dentro do saldo autorizado.

A montagem concluída ainda precisa de build, drivers, aquisição, envio,
calibração e teste integrado. Conseguir demonstrar os dois canais recebidos é
um marco verificável. Detector geral, especialista R21 e tracking já executaram
em ensaios, mas há perdas de escadas, falsos alertas e limitações de IDs; não é
necessário aguardar outro treino para demonstrar transporte/telemetria. Separar
esses problemas das falhas de rede e da conclusão do protótipo físico.

Referências: [API](api.md), [ToF](protocol/demo-tof.md), [painel](demo-panel.md),
[matriz da bancada](bench-integration.md), [operação AWS](aws-operation.md).
