# Leitura de vídeo no simulador — correção da #70

Responsável: Bryan. Relacionadas: #19, #30, #7 e #11.
Esta correção trata do produtor de imagens no computador; não altera modelos,
contrato da API, firmware, política de áudio ou o caminho tátil local.

## Problema e solução

O leitor posicionava o vídeo com `VideoCapture.set(CAP_PROP_POS_FRAMES)` a cada
salto de frames. No perfil inicial privado de 19/10/2026, oito posições em um
vídeo 4K consumiram 2,449 s, dos quais 1,993 s foram buscas de posição. Reduzir a
resolução em uma cópia sem perda não eliminou esse custo. A inferência local
também teve custo relevante; esses números não isolam capacidade da API.

A seleção por tempo decorrido permanece igual. Quando houver até 30 frames
intermediários, o leitor usa `grab()` para descartá-los, recuperando e codificando
somente o frame selecionado. Saltos maiores usam busca direta. O máximo de
30 avanços limita o trabalho sequencial por chamada; não é limite de idade,
risco ou TTL. A escolha cobre intervalos curtos dos vídeos de 30 FPS avaliados,
sem percorrer sequencialmente uma pausa arbitrariamente longa.

Não há fila de JPEGs nem nova thread. A fonte webcam, transporte e limite de
uma requisição ativa não mudam. O timestamp continua após a aquisição e antes
da codificação JPEG; não passa a representar exposição do sensor ou timestamp
de apresentação do vídeo. Erros de avanço/leitura retornam
`source_ended_or_decode_failed`; busca não suportada mantém `video_seek_failed`.

Alternativas consideradas:

- Reduzir a resolução: facilitou parte da leitura, mas preservou o custo das buscas.
- Usar somente avanço sequencial: poderia percorrer um trecho enorme após atraso.
- Decodificar em outra thread com buffer: acrescentaria concorrência e estado sem
  necessidade demonstrada para esta correção.
- Alterar modelos/threads de inferência ou AWS: não resolve a busca do leitor e
  exigiria outra medição; não foi feito.

## Reprodução sem mídia privada

Com Python >=3.11 e o extra `.[vision]` instalado, execute na raiz:

```sh
mkdir -p .local
PYTHONPATH=src python scripts/benchmark_video_reader.py --output .local/reader-after.json
```

O script cria e remove um AVI MJPG sintético: 90 frames a 30 FPS, 640×360,
pixels procedurais próprios sob AGPL-3.0-only, sem pessoas, pesos ou rede.
O codec/dependências mantêm suas próprias licenças. Faz três passagens nas
posições 0–700 ms em intervalos de 100 ms, depois 2000 e 2100 ms. Registra índices,
hashes JPEG95 com max-edge 640, chamadas/tempos de read/grab/set, versões e hash
da mídia. Usa relógio controlado para escolher posições e perf_counter para
medir trabalho real. Não mede HTTP/inferência ou cadência em tempo real.
O JSON é criado com permissão 0600 e nunca sobrescreve arquivo existente.

Para comparar uma revisão anterior, execute o mesmo script com aquela versão
instalada de `src/` e outro nome de saída. Mantenha máquina, arquivo, versões,
posições, repetições e configuração iguais; compare todos os pares
`source_frame_index`/`jpeg_sha256` de todas as passagens. O script confere essa
consistência entre suas repetições; a comparação entre versões foi conferida
separadamente nesta execução.

É possível usar `--video CAMINHO-LOCAL` com vídeo autorizado de pelo menos
2,2 s. Não publicar mídia, imagens, caixas ou dados pessoais. O JSON não contém
caminho do arquivo; hash e informações de origem continuam sujeitos ao controle
de acesso do conjunto. O script exige OpenCV e o writer MJPG disponível.

## Resultados locais — 19/10/2026

Darwin arm64, Python 3.11.16, OpenCV 4.14.0. Mediana das médias de leitura das
três passagens de dez posições; não confundir com P50 de latência por frame.
Sem API/inferência concorrente durante as medições utilizadas abaixo.

| Entrada | Antes | Depois | Razão antes/depois |
| --- | --- | --- | --- |
| Vídeo privado H264 2160×3840, 30 FPS | 169,826 ms | 52,844 ms | 3,21× |
| Fixture MJPG sintética 640×360, 30 FPS | 28,064 ms | 10,044 ms | 2,79× |

Nas três passagens de cada entrada, todos os índices e hashes JPEG foram iguais
entre as versões. Por passagem, o original fez dez leituras e nove buscas antes;
depois fez dez leituras, 16 avanços descartados e uma busca. O ensaio inicial de
oito posições e este de dez posições têm protocolos diferentes; não comparar
suas médias diretamente. Há variabilidade de máquina, codec, cache e escalonamento;
essas razões não são garantia para outros arquivos ou hardware.

### Verificação com HTTPS e modelos reais

Um vídeo autorizado de 12,667 s foi enviado novamente à API HTTPS local,
com YOLOv8n + R21 congelados, CPU, confiança 0,35, imgsz 640, associação IoU
0,50, upload max-edge 640/JPEG95 e o perfil de áudio aprovado da #31.
O teto solicitado continuou 10 imagens/s. Comparação com a primeira execução
desse mesmo vídeo, sem reaplicar a mudança aos outros oito:

| Medida | Antes | Depois |
| --- | --- | --- |
| Frames admitidos | 24 | 106 |
| Tempo total do cliente, inclui inicialização/fim | 13,900 s | 13,043 s |
| Frames admitidos / tempo total | 1,73/s | 8,13/s |
| P95 até admissão, após leitura da imagem | 270 ms | 188 ms |
| Sugestões de texto admitidas | 4 | 4 |

O maior número de frames muda a amostragem temporal: não mede ganho de acurácia,
continuidade de IDs ou redução de falsos alertas. Há um evento terminal
`source_ended_or_decode_failed` em cada execução; não houve outros descartes.
Na nova execução, os 106 frames aceitos possuem diagnóstico correspondente,
JPEGs reconstruídos para revisão e hash de entrada inalterado. O servidor local
foi encerrado e as credenciais/TLS temporários removidos. Nenhuma VM, TTS ou
chamada paga foi criada. A execução usa relógio e orientação simulados no cliente;
não mede latência fim a fim do ESP nem substitui benchmark AWS da #22.

## Verificações e limites

Os testes do leitor verificam saltos curtos, pausa longa, fronteiras 0/1/30/31,
relógio repetido, ausência de codificação dos frames descartados, timestamp antes
do JPEG, falha no primeiro/intermediário avanço, fim no frame selecionado,
fim consecutivo e falha de busca. Um teste com OpenCV real compara bytes JPEG
contra decodificação sequencial independente, através de avanços e busca direta.
Sem OpenCV, esse teste aparece como skipped e não valida decodificação real.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_simulator.py -v
PYTHONPATH=src python scripts/run_tests.py --report-dir .local/test-report
python scripts/check_docs.py
git diff --check
```

Nesta execução, a suíte completa passou: **407 testes, zero falhas e zero
skips**, com extras de visão/API instalados e `SONAR_E2E_WEIGHTS` apontando para
o YOLOv8n geral confiável local. Inclui o teste do decodificador real e os
cenários HTTPS/tátil simulado existentes. Ruff 0.16.10 (perfil E4/E7/E9/F),
`check_docs.py` (107 arquivos, zero problemas) e `git diff --check` passaram.
Não houve validação em webcam, ESP, atuadores ou outros codecs/plataformas.
O feedback tátil local continua independente da nuvem; a atuação física não foi
exercitada. Esta correção não encerra #19/#7/#11/#16 e não aprova novo treino.
