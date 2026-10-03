# Cliente simulador dos óculos — #30

- Responsável previsto: Matheus (@Matheus-xz), com apoio de IA.
- Status: implementação experimental para revisão; não comprova segurança física.
- Referências: [issue #30](https://github.com/BryanPinheiro77/sonar-vision/issues/30),
  [contrato 0.1](protocol/eventos-semanticos.md), [ADR 0003](decisions/0003-eventos-semanticos.md),
  [escopo](ESCOPO.md). API real depende da #24; catálogo/áudio da #25/#18.

## Solução e padrão

`src/sonar_vision/simulator.py` mantém núcleo puro, transporte HTTPS e fontes
substituíveis no pacote existente, com testes unittest em `tests/test_simulator.py`.
Biblioteca padrão Python >=3.11; captura real reutiliza OpenCV opcional já previsto
no extra vision. Sem API, firmware, TTS, dashboard ou infraestrutura novos.

O computador cria sessão UUID, contador decimal e timestamp monotônico em ms.
Uma captura imutável mantém JPEG, referências e orientação **sintética**. O envio
usa POST /v1/inference multipart: metadata application/json e image image/jpeg.
Timestamp é obtido na leitura, antes da codificação JPEG; mede idade desde a
aquisição pelo computador, não exposição do sensor nem relógio interno do vídeo.
Vídeo é posicionado por tempo decorrido, pulando frames após atrasos; FPS inválido
ou seek não suportado falham explicitamente. Webcam usa leitor contínuo e um único
slot que substitui o frame anterior, sem fila. Buffers internos da câmera/driver
podem adicionar atraso ainda não medido.

Simulador e transporte rejeitam concorrência com busy. Não há retransmissão nem
fila de capturas. Timeout cobre conexão/envio/leitura: 2000 ms. O chamador encerra
a espera no limite; se DNS ainda estiver bloqueado, o worker permanece protegido,
novas tentativas recebem busy antes da captura e ele confere cancelamento antes
de enviar após conexão. Não promete cancelar trabalho já recebido pela API.

O parser limita 16384 bytes, 20 objetos, 120 pontos de código, IDs de 128 bytes,
inteiros seguros JSON, enums e campos exatos. Rejeita chaves duplicadas, NaN,
referências divergentes e comandos extras. Envelope completo é validado antes de
qualquer efeito. Observação admitida não significa áudio executado ou caminho livre.
Áudio é apenas decisão exibida; não há reprodução atual/pendente nem TTS.

Validade: idade >= min(valid_for_ms,1000) descarta. Áudio não estende observação.
Sessão anterior, captura desconhecida/divergente, duplicata, conflito de ID,
regressão do relógio e saturação de IDs são descartados. Memória comporta 64 IDs
de mensagens ainda válidas (limite do simulador, não limiar de risco); expira
sem expulsar IDs vivos. Apenas uma captura de requisição é mantida.

Orientação usa menor separação angular de quaternions 3D, aceitando sinais
equivalentes e wrap. CLI fornece yaw sintético constante na captura e outro no
recebimento. >15 graus, referência divergente ou amostra explicitamente inválida
descartam áudio direcional. Não há validação de idade/qualidade de IMU real.
Urgência local sintética bloqueia áudio; liberação exige captura posterior.
`update_local` permite injetar transições entre envio e resposta em testes.
Essas entradas não vêm da visão nem representam medições. Não calcula risco/TTC
e não acessa vibração. O modo tátil local continua independente por arquitetura;
sua execução física e a arbitragem de fala permanecem nas issues de firmware.

## Fixtures reproduzíveis, antes da API

PowerShell, na raiz:

```powershell
$env:PYTHONPATH = 'src'
python -B -m sonar_vision.simulator --fixture success --frames 3
python -B -m sonar_vision.simulator --fixture expired
python -B -m sonar_vision.simulator --fixture timeout
python -B -m sonar_vision.simulator --fixture old_session
python -B -m sonar_vision.simulator --fixture success --current-yaw 16
python -B -m sonar_vision.simulator --fixture success --orientation-invalid
python -B -m sonar_vision.simulator --fixture success --urgent
```

Outras fixtures: wrong_capture, malformed, oversized, unauthorized, disconnect,
duplicate (use pelo menos dois frames). Cenários são determinísticos e em memória:
não validam rede, certificado ou inferência. VirtualClock avança 100 ms no sucesso,
1000 em expired e 2000 em timeout, sem espera real. duplicate reutiliza IDs em
captura nova, produzindo id_conflict. As interfaces podem ser usadas pela #27,
que continua responsável pelos demais testes de integração.

A primeira linha JSON identifica modo, entradas simuladas, origem e perfil.
As seguintes mostram decisão, classes/direção/movimento, motivo e latência em ms
da leitura da captura até admissão/descarte, incluindo codificação, envio e leitura.
No fixture success: outcome=accepted, observation=accepted, audio=accepted,
latency_ms=100. Em expired e timeout: outcome=discarded e motivo correspondente.
Sem média/FPS ou alegação de desempenho real. Descartes esperados não fazem o
CLI falhar: código 0 significa cenário executado; configuração inválida retorna 2.

## Vídeo/webcam e HTTPS

Utilizar um ambiente com OpenCV do extra vision já instalado conforme
[guia de visão](vision.md). Fixtures/testes do núcleo dispensam esse extra.
Não há download automático de mídia/modelos.

Configure SONAR_VISION_TOKEN fora do Git e dos logs usando credencial individual
provisionada pela API. Não coloque o token no comando, URL, arquivo versionado
ou histórico do terminal. Pode usar um prompt oculto nesta sessão:

```powershell
$simulatorCredential = Read-Host 'Credencial individual da API' -AsSecureString
$env:SONAR_VISION_TOKEN = [System.Net.NetworkCredential]::new('', $simulatorCredential).Password
python -B -m sonar_vision.simulator --video videos/cenario-autorizado.mp4 --source-id laboratorio-autorizado-01 --endpoint https://HOST-DA-API/v1/inference --frames 10
python -B -m sonar_vision.simulator --webcam 0 --source-id camera-bancada-01 --endpoint https://HOST-DA-API/v1/inference --capture-yaw 0 --current-yaw 0
Remove-Item Env:SONAR_VISION_TOKEN
```

HOST-DA-API é placeholder; não existe servidor incluído aqui. Exige endpoint HTTPS,
certificado válido e autenticação da #24. Para CA de laboratório provisionada
externamente, use `--ca-file C:\caminho-local\ca.pem`. SSLContext padrão valida
cadeia e hostname. HTTP e URL com credenciais/query são rejeitados; nenhum redirect
é seguido e não existe opção insecure ou fallback. Falhas TLS/autenticação/rede
geram códigos fixos, sem imprimir exceção, token, endpoint, path ou corpo remoto.

`--source-id` é obrigatório na captura real: escolha identificador sem dados
pessoais. Registre fora do Git origem, licença/permissão, responsável, condições,
consentimento quando aplicável e hash de vídeos autorizados. Não presumir licença
AGPL para vídeos de terceiros. Vídeos em videos/ e certificados PEM são ignorados.
A fixture JPEG é um quadrado preto original de 8x8 gerado em memória, incorporado
como base64, licença AGPL-3.0-only; respostas sintéticas também são próprias.
OpenCV segue as licenças já documentadas no guia de visão; nenhuma dependência nova.

## Testes, evidências e limites

```powershell
$env:PYTHONPATH = 'src'
python -B -m unittest discover -s tests -p test_simulator.py -v
python -B -m unittest discover -s tests -v
git diff --check
```

Testes verificam captura/metadados correspondentes, parsing completo, limites e
fronteiras de idade/ângulo, referências, sessão reiniciada durante requisição,
deduplicação, urgência, memória e concorrência sem capturar/enfileirar no busy.
Transporte é exercitado com conexões substitutas: certificado rejeitado, HTTP
302/401/503, Content-Type, leitura limitada e deadline com conexão bloqueada.
Esses testes verificam uso do SSLContext, não handshake com servidor real.

### Evidência local — 2026-10-02

Ambiente: Windows/PowerShell, Python 3.12.7. Suíte completa: 77 testes,
73 aprovados e 4 skipped (ByteTrack real sem extra vision). Os 21 testes
do simulador passaram. git diff --check sem erro de whitespace.
Execuções CLI confirmadas: success aceita observação/áudio com 100 ms virtuais;
expired descarta aos 1000 ms; timeout aos 2000 ms; old_session retorna
session_mismatch; current-yaw=16 conserva observação e descarta áudio com
orientation_changed. Tempos virtuais não representam desempenho real.

Para o PR, explicar a escolha da biblioteca padrão/fixtures e as alternativas
acima, vincular #30 e anexar estes comandos/resultados. A pessoa responsável
deve revisar e conseguir explicar funcionamento, riscos e testes. O PR ainda
não foi aberto; commit/push exigem solicitação explícita conforme AGENTS.md.

Não foram validados API real, handshake TLS real, vídeo/webcam físicos, latência
fim a fim real, qualidade de sensores, áudio, avisos de disponibilidade ou
segurança. Avisos 3000/3/10000 ms e arbitragem atual/pendente são da #18/#25;
este cliente não declara validar todos os critérios do contrato. Revisão humana
e execução com API/artefatos autorizados são necessárias antes de concluir
integração. Sem commit, push ou abertura de PR automática; evidências ficam
disponíveis no checkout para preparar o PR revisável.

Alternativas: copiar um loop de webcam/detector misturaria inferência e cliente;
adicionar biblioteca HTTP/dependências não é necessário; relaxar TLS viola contrato.
Não muda arquitetura, protocolo, pinos ou limiares locais: sem novo ADR aceito.
