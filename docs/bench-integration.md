# Preparação da integração ESP → API → áudio — #19

Data: 2026-10-16. Coordenação: Bryan.
**Status: preparação de software; montagem e execução física pendentes.**
Referências: [#19](https://github.com/BryanPinheiro77/sonar-vision/issues/19),
[contrato 0.1](protocol/eventos-semanticos.md), [API](api.md),
[integração testável](integration.md), [operação AWS](aws-operation.md),
[componentes](bench-components.md) e [áudio local](protocol/audio-local.md).

## Objetivo e responsabilidades

Preparar o primeiro cliente físico sem esperar novos vídeos de tracking.
Começar com uma imagem sintética ou cena de objetos autorizada. Essa verificação
mostra transporte e admissão, não acurácia visual ou navegação validada.

| Frente | Entrega para a bancada |
|---|---|
| Bryan / modelos e cloud | Versão do serviço, hashes/configurações, acesso privado aos modelos, endpoint/CA/credencial e análise dos registros |
| Mathias, Tarcísio e Weslley / hardware e firmware | Confirmar placas, alimentação e pinos na #1; captura/HTTPS na #17; arbitragem/reprodução na #18; instrumentação física |
| Matheus / anúncios e catálogo | Consolidar #5/#31, frases/voz #32 e revisão do formato com firmware |
| Ambos os trios | Executar e revisar evidências da #19, identificando responsável e revisor de cada rodada |

Divisão confirmada por Bryan em 16/10/2026: as issues de hardware ficam com
Mathias, Tarcísio e Weslley; Bryan e seu trio ficam com modelo/IA e cloud.
Este documento é apoio de interface entre frentes, sem exigir montagem ou
implementação de firmware por Bryan. Não altera assignees no GitHub.
O guia não fornece
pinagem, build PlatformIO, drivers ou perfil elétrico ainda inexistentes.
WM8960 substitui MAX98357A conforme ADR0021; uso dos motores ERM continua proposta
para hardware, sem converter o inventário parcial da #1 em aprovação física.

## Pacote e versões a registrar antes da conexão

Perfil experimental existente: [modelos R21](experiments/issue-22-r21-profile.json).
Os arquivos são privados, obtidos com o responsável; não estão anexados ao Git
nem devem ser baixados de origem desconhecida. O manifesto registra autorização de Bryan em 09/10/2026 para handoff privado
aos integrantes do grupo; combinar a entrega em canal autorizado, sem publicar
os pesos. Esta sessão não envia arquivos ou mensagens a colegas.

| Papel | Arquivo no pacote privado | SHA-256 esperado |
|---|---|---|
| Geral, preservar demais classes | `models/general.pt` | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| Escadas, candidato atual | `models/stairs-r21.pt` | `449aecd65557e18a982a4c3ab6a33c7a7e41020b7f368b4305db4a1823607813` |
| Escadas, rollback | `models/stairs-r20.pt` | `f30ab3ee162d51322667342c1d8f38e50473aa994a573205be5ae3ff08424f3b` |

Conferir manifesto/origem/licenças do pacote e calcular o hash antes de carregar.
Renomear arquivo não altera hash; registrar o caminho efetivo privado.
Não substituir o geral pelo especialista ou pelo candidato de móveis rejeitado.

Registrar em cada rodada: commit do serviço, estado modificado/limpo, ID imutável
da imagem quando usar Docker, hashes dos pesos e configuração, versões Python/
dependências, firmware/placa/câmera, resolução, compressão, cadência e relógios.
Não usar `latest` ou só um nome de checkpoint como identificação reproduzível.

Confiança 0,35, entrada do modelo 640, CPU e associação IoU 0,50 seguem o perfil
R21; não são medidas de precisão. CPU4 em São Paulo usa o runner paralelo optativo
e intraop=1 da #22, não o padrão serial da CLI. Preservar o runner verificado
para reproduzir aquele benchmark. Nenhuma troca de runner é feita neste guia.

Upload do ensaio anterior: maior lado 640, proporção preservada, JPEG95,
cadência periódica com teto de 10 inícios/s e uma requisição ativa. JPEG95 é
parâmetro do codificador do computador. A escala de compressão do driver OV2640
precisa ser documentada e avaliada; não configurar um número 95 por analogia.
Não afirmar equivalência de compressão sem verificar os JPEGs efetivos.

## Sequência para o primeiro teste

1. **Software local:** executar os testes abaixo. Eles criam CA, credenciais
   efêmeras e servidor de teste em loopback, sem VM ou câmera. O backend é
   simulado; isso não executa os pesos conferidos acima.
2. **Rede local controlada:** operador prepara serviço HTTPS para um host/IP
   alcançável pelo ESP, com certificado que inclua esse host/IP. Provisionar
   somente CA pública e credencial individual no dispositivo. Chave privada do
   servidor nunca vai para o ESP. Confirmar relógio de parede para validação TLS;
   não confundir esse relógio com o monotônico de captura. A ferramenta
   `dev_tls` da CLI gera certificado apenas para localhost/loopback: não basta
   mudar o URL para o IP da máquina. O operador deve fornecer certificado com
   identidade correspondente, seguindo o procedimento de endpoint da #23.
3. **Transporte no ESP:** hardware implementa #17, envia JPEG e metadata da
   mesma captura e verifica o envelope recebido, inicialmente sem reprodução.
   Registrar memória e tempos antes de aumentar resolução ou cadência.
4. **Modelo real:** repetir com geral+R21, hashes conferidos e aquecimento
   concluído; a imagem sintética verifica contrato, não reconhecimento.
5. **Áudio:** somente após perfil/frases/formato revisados. Ausência de
   `SONAR_API_AUDIO_CONFIG` mantém `audio: null`, resultado válido. Sugestão
   presente ainda exige admissão local; não comprova fala executada.
6. **AWS temporária:** quando o cliente estiver pronto, seguir #23 e verificar
   autorização, consumo acumulado e prazo. Este preparo não inicia recursos,
   renova orçamento ou autoriza hospedagem permanente. Instalar prazo automático
   antes de servir, preservar após reboot e remover recursos ao terminar.

## O que o firmware precisa implementar no caminho HTTPS

Enviar `POST /v1/inference` com `Authorization: Bearer` individual e
`multipart/form-data` com boundary correto. Exatamente duas partes:

| Parte | Content-Type | Conteúdo |
|---|---|---|
| metadata | application/json | Somente os quatro campos abaixo |
| image | image/jpeg | Um JPEG correspondente à captura; não MP4/stream de vídeo |

Exemplo fictício de metadata, não captura medida:

```json
{"version":"0.1","session_id":"bancada-boot-exemplo","frame_id":"1","captured_at_ms":1000}
```

Sessão nova por boot; contador decimal como string, sem zeros à esquerda
(exceto `"0"`). Timestamp inteiro monotônico local, não horário UTC da VM.
Guardar referência da mesma captura no ESP, incluindo orientação/qualidade
quando disponível. Documentar se o instante corresponde ao início/fim da
captura: conclusão da leitura do buffer não prova instante de exposição.
O metadata atual não aceita campos extras de IMU, caixas ou comandos táteis.

Uma requisição ativa, sem fila de imagens antigas. Após timeout/desconexão,
invalidar a tentativa; próxima tentativa usa captura nova. Transporte que ainda
possui buffer/worker não pode ser reutilizado antes de liberar ownership.
Não seguir redirect com credencial e não desabilitar TLS para contornar erro.

Validar resposta inteira e limitar durante leitura, mesmo sem Content-Length.
`200` traz os dois campos `observation` e `audio` (pode ser null). Conferir
versão, sessão, frame, timestamp contra registro local, epoch, IDs e referências,
enums, tipos, finitude e limites antes de efeitos. Não tratar HTTP 200 como
admissão automática. IDs/epoch não comprovam identidade física perfeita.

| Regra existente | Valor / ação |
|---|---|
| Timeout cliente | 2000 ms, total conexão+envio+leitura |
| Timeout servidor configurado | 1500 ms; slot pode permanecer ocupado até o trabalho terminar |
| Corpo multipart na API atual | 524288 bytes, incluindo todas as partes |
| Metadata / pixels na API atual | 1024 bytes / 1920000 pixels; não são orçamento de RAM do ESP |
| Corpo JSON da resposta / objetos / texto | 16384 bytes / 20 / 120 pontos de código Unicode |
| Validade local | Idade >= min(validade recebida, 1000 ms): descartar |
| Mudança de orientação | >15 graus ou orientação inválida: rejeitar/interromper fala direcional |
| Ausência / recuperação / cooldown | 3000 ms / 3 resultados novos válidos / 10000 ms |

Os limites de upload/pixels são configuração experimental da API, não validação
da capacidade física. Para orientação usar rotação relativa 3D e referências
comparáveis, conforme contrato; yaw simulado do cliente de computador não é BNO085.

Erros 400/401/413/415/429/500/503 não produzem fala visual. `busy` não pede
acumular frames. Resposta de sessão antiga, duplicada, vencida ou malformada
é descartada; silêncio e observação vazia não significam caminho livre.
Mensagens remotas nunca definem risco/TTC ou acionam vibração.

## Matriz da bancada e evidências

Preencher uma linha por tentativa no [modelo CSV](experiments/issue-19-bench-template.csv),
guardando o preenchido em armazenamento privado, por exemplo `.local/issue19/`.
Arquivo vazio não é resultado. Não registrar tokens, URLs privados, pessoas,
JPEGs ou textos de fala no relatório agregado do PR. Evidências brutas seguem
as regras de acesso e retenção da #7.

| ID | Procedimento controlado | Resultado a verificar |
|---|---|---|
| B01 | JPEG/credencial/CA válidos | Captura e observação correspondem; audio null aceito |
| B02 | Credencial ausente ou inválida | 401; nenhuma fala visual; caminho local continua |
| B03 | CA errada ou host divergente | TLS recusado sem HTTP inseguro; nenhum upload autenticado |
| B04 | JPEG/campos inválidos ou payload excessivo | 400/413/415; rejeição sem bloquear sensores |
| B05 | Rede lenta/travada além do prazo | Timeout; captura não reenviada; resultado tardio ignorado |
| B06 | Segundo envio enquanto ocupado | Sem fila/captura antiga; tratar busy/ownership corretamente |
| B07 | Resposta duplicada ou ordem antiga | Sem repetir áudio nem substituir sugestão nova |
| B08 | Idade no limite de 1000 ms | Descarte, validade não reinicia no recebimento |
| B09 | Reboot ESP com resposta antiga pendente | Sessão nova; rejeitar resposta anterior |
| B10 | Reinício API/expiração de sessão | Epoch novo; não concatenar tracks entre reinícios |
| B11 | Desligar Wi-Fi/serviço e restaurar | Aviso local estabilizado; recuperação só com 3 resultados novos válidos |
| B12 | Orientação >15 graus ou inválida durante fala direcional | Cancelar sem retomar frase antiga |
| B13 | Urgência local durante fala/rede travada | Vibração sem espera de rede; cancelar fala e pendente |
| B14 | Atualização com uma fala atual e uma pendente | Substituir só pendente; nunca ampliar fila |
| B15 | Falha de sensor ou saída de áudio | Aplicar modo degradado definido por hardware; ausência não vira caminho livre |
| B16 | Troca R21→R20 e retorno | Hash/configuração registrados, serviço recriado e nova sessão; preservar geral |

B12–B15 exigem entradas locais instrumentadas; não fabricar campos de risco ou
orientação na resposta da API para simulá-los. O teste físico de vibração segue
o [protocolo háptico](protocol/haptic-local.md); esta matriz não define pinos,
amplitude, estímulo mecânico ou limiar operacional novo. Preparar uma falha por
vez, em bancada supervisionada; registrar tentativa falha/inconclusiva também.

Medir captura/encode, JPEG pronto→admissão, trabalho do servidor e início físico
do áudio/tátil separadamente. Intervalos devem usar o mesmo relógio ou método
instrumental documentado, nunca subtrair timestamp ESP de relógio VM.
Metas da #22: ≥8 admissões/s, trabalho P95≤80 ms e JPEG pronto→admissão
P95≤150/P99≤250 ms, **para a entrada e perfil aprovados**, não captura completa
nem metas novas de bancada. Não exigir que o primeiro teste já atinja a carga.
Registrar FPS ofertado/admitido, duração, warmup, falhas, descartes e denominadores.

## Rollback e encerramento

Guardar ID da imagem/configuração anterior e hashes antes de mudar o serviço.
R21→R20 troca caminho e hash do especialista, preserva geral e recria serviço;
conferir health/HTTPS autenticado e captura nova. Rollback não restaura tokens
revogados, chaves comprometidas ou sessão antiga. Falha mantém serviço
indisponível; sensores/tátil locais não esperam o rollback.

No fim, exportar só os registros autorizados, encerrar serviço de bancada e
remover segredos efêmeros. Em AWS, executar limpeza/auditoria da #23, incluindo
volumes e demais recursos próprios; parar instância não é limpeza completa.

## Reproduzir a verificação local

Com extras `.[api,api-dev]` já instalados, na raiz do checkout:

```sh
PYTHONPATH=src:tests python -m unittest test_e2e test_simulator_https test_local_audio test_token_ops test_runtime_options test_aws_release -v
python scripts/check_docs.py
git diff --check
```

Em Windows usar o separador de PYTHONPATH da plataforma ou executar discovery
por arquivo, como no [guia de integração](integration.md). Sem extras, skips
não contam como validação HTTPS. Não há comando de firmware ou deploy novo.

[Registro desta preparação](experiments/issue-19-preparation.md).
Não encerrar #19: faltam cliente físico, arbitragem/voz, medidas de bancada,
avaliação real #7/#11/#16 e demonstração integrada com ambos os trios.
