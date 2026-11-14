# Orientações de firmware: componentes, direção e nuvem

Guia de implementação para Mathias, Tarcísio e Weslley, nas #1/#4/#9/#17/#18/#19.
Organiza as decisões existentes; não implementa drivers ou aprova limiares.
Antes de programar, ler o [mapa confirmado](hardware-wiring.md), o
[inventário](bench-components.md), a [geometria local](local-geometry.md) e o
[perfil háptico experimental](protocol/haptic-local.md).

## Papel de cada componente

| Componente | Responsabilidade no firmware | Separação necessária |
|---|---|---|
| ESP32-S3 N16R8 | Adquirir sensores, executar geometria/política local, controlar atuadores e enviar telemetria/JPEG em tarefas separadas | Rede e câmera não bloqueiam o tátil; preservar pinagem, limites de memória e PSRAM |
| VL53L5CX | Fornecer matriz 8×8 com alcance, qualidade/status por zona e tempo de aquisição | Manter evidência por setor para direção; uma distância global perde essa informação |
| BNO085 | Fornecer orientação com referência, qualidade e tempo compatíveis com a geometria | Orientação indisponível não vira quaternion válido ou direção compensada inventada |
| TCA9548A | Selecionar ramal 0/esquerdo ou 1/direito para acessar o DRV correspondente | Não controla força nem para o motor ao desmarcar o ramal |
| Dois DRV2605L | Configurar e comandar cada atuador separadamente; parar o lado que não deve continuar ativo | Seleção do ramal e acesso ao driver formam uma operação protegida contra concorrência |
| Motores 1027 | Produzir feedback nas hastes do lado solicitado pela política | Tipo e calibração precisam seguir a identificação física; não aplicar configuração LRA a candidato ERM |
| Áudio P2 (YX5300 candidato, [ADR 0029](decisions/0029-audio-p2-yx5300.md); antes WM8960 e transdutor) | Configurar codec/clock/I2S e reproduzir áudio local autorizado pela arbitragem | Reprodução não bloqueia tátil; ganho e terminais exatos dependem da placa/transdutor |
| OV2640 | Capturar JPEG e metadados da mesma aquisição para envio HTTPS | Não autoriza vibração; usar pinagem nativa da placa, sem conflito com o mapa |

As tensões e parâmetros elétricos não são escolhidos por essa tabela. Seguir
as referências do inventário e registrar o conjunto realmente montado.

## Do ToF ao lado que vibra

O ToF mede alcance; ele não reconhece “pessoa” ou “cadeira”. A geometria local
transforma observações utilizáveis em evidência à esquerda, ao centro ou à
direita dos óculos. A política local decide se essa evidência pede atenção ou
urgência; somente então o atuador recebe o padrão correspondente.

1. Adquirir as 64 zonas e preservar índice, distância, status/qualidade e tempo.
   Validar conforme driver e perfil físico, sem converter ausência de retorno
   em distância zero ou caminho livre.
2. Conferir a orientação física da matriz no módulo montado. A ST descreve
   inversão horizontal e vertical pela lente; índices crus não devem ser
   traduzidos diretamente em “haste esquerda” por suposição. Referência:
   [ST UM2884, seção 2.2](https://www.st.com/resource/en/user_manual/um2884-a-guide-to-using-the-vl53l5cx-multizone-timeofflight-ranging-sensor-with-wide-field-of-view-ultra-lite-driver-uld-stmicroelectronics.pdf).
3. Usar raios calibrados, transformação ToF→cabeça e referência de orientação
   declarada, conforme a #9. Registrar fronteiras dos setores, volume observado
   e unidades; não inventar uma divisão fixa de colunas ou ângulo operacional.
4. Preservar evidência, alcance e cobertura por setor. O menor alcance de toda
   a matriz pode servir à telemetria simples, mas não diz de qual lado veio.
5. Aplicar o perfil local aprovado para bancada e sua arbitragem; não usar
   classe YOLO, ID de tracking ou resposta da API para autorizar os motores.
   Limiares físicos, histerese e liberação continuam pendentes de especificação
   e ensaio; os valores de fixture do núcleo não autorizam atuação vestível.

### Canais no perfil experimental já aprovado

Tabela para evidência que a política selecionou no nível de prioridade ativo,
conforme [ADR 0020](decisions/0020-feedback-haptico-local.md):

| Setor selecionado pela política local | Haste esquerda | Haste direita |
|---|---|---|
| Somente esquerda | Padrão ativo | Sem padrão de obstáculo |
| Somente direita | Sem padrão de obstáculo | Padrão ativo |
| Centro | Padrão ativo | Padrão ativo |
| Esquerda e direita simultâneas | Padrão ativo | Padrão ativo |
| Direção/percepção indisponível, sem urgência válida | Padrão de degradação, conforme perfil | Padrão de degradação, conforme perfil |

As duas hastes não distinguem centro de evidência bilateral neste perfil.
Degradação é um ritmo diferente, não uma indicação de obstáculo frontal.
Urgência válida tem prioridade sobre degradação e atenção; a tabela não
substitui essas regras. Ausência de padrão de obstáculo não prova caminho livre.

Detectar alguma distância na matriz **não basta para comandar os dois motores**.
Ao mudar de esquerda para direita, por exemplo, o firmware deve atualizar ambos
os drivers: parar o padrão anterior à esquerda e comandar o direito, conforme
o modo de operação e a política de transição. Apenas selecionar outro ramal do
TCA deixa a reprodução anterior potencialmente ativa.

Amplitude é calibrada por atuador e permanece constante no perfil experimental
vigente; a cadência comunica urgência. Não acrescentar força proporcional à
distância nem valores elétricos presumidos. Os motores comprados aparecem como
candidatos ERM no [ADR 0022](decisions/0022-ensaio-erm-1027.md); conferir tipo e
decisão física antes de selecionar o modo do driver.

O ToF sozinho também não confirma que um alvo é a mesma pessoa caminhando à
frente. Não suprimir alerta supondo identidade ou velocidade compatível sem
evidência e política aprovadas; mesma zona não comprova identidade para TTC.

## Telemetria é observação, não controle tátil

Seguir o [guia da API](esp-api-guide.md). Distância e JPEG são envios separados:

- Distância: JSON em POST /v1/demo/tof. No modo agregado existente,
  aggregation=min_valid_8x8 exige sector=all e zone=null. Isso não significa
  “acionar ambas as hastes”; o servidor apenas recebe uma medição global.
- Para uma zona individual, o contrato existente permite aggregation=zone,
  índice zone e sector conforme o mapeamento físico documentado. Não inventar
  agregação “mínimo por setor” ou outros campos sem revisar o contrato.
- JPEG: multipart em POST /v1/inference, com metadata e image. Não colocar
  matriz ToF ou distância dentro da metadata de inferência.

O painel atual mantém a última leitura ToF, não três indicadores simultâneos
por setor. Publicar três zonas sucessivas não cria um painel de três distâncias.
O estado local dos três setores precisa existir independentemente do dado
selecionado para enviar à nuvem. O painel tampouco atribui alcance a caixa YOLO.

TLS/token, boot e sequência seguem os guias existentes. Não imprimir segredos
em diagnóstico nem acumular uma fila de medidas antigas em reconexão.

## Conferência de bancada antes da integração vestível

Executar primeiro com alvo inanimado e montagem fixa, sem participante.
Registrar versão do firmware, placas/atuadores, configuração, orientação da
matriz, setores, qualidade e comandos realmente enviados a cada ramal.

| Cenário controlado | Conferência necessária |
|---|---|
| Alvo somente à esquerda, em condição de alerta definida pela bancada | Evidência no setor esquerdo e motor esquerdo; direito sem padrão de obstáculo |
| Alvo somente à direita | Caso simétrico, sem inversão dos lados |
| Alvo ao centro | Ambos conforme o perfil; medir atraso entre inícios |
| Alvos nos dois lados | Preservar os dois setores no registro, mesmo com padrão conjunto |
| Alvo muda de esquerda para direita | Motor anterior para conforme política; mudar ramal sozinho não basta |
| Retorno inválido, dado vencido ou perda de orientação | Estado e padrão de degradação previstos, sem distância zero/caminho livre |
| Wi-Fi e VM indisponíveis ou envio lento | Sensores e tátil continuam; não esperam timeout HTTP |
| Driver/atuador de um lado falha | Registrar falha; não apresentar o outro lado como direção correta |

Status de scan I2C ou comando escrito com sucesso não prova vibração mecânica.
Medir latência e canais conforme o protocolo da #4; não declarar validação de
segurança a partir destes exemplos. Os testes nativos da #9 verificam geometria
simulada, não substituem este ensaio físico. Implementação e resultados ficam
com hardware/firmware; este guia não conclui essas issues.
