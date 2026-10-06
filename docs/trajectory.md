# Trajetória aparente e visualização local — #11

Responsável: Bryan. Implementação experimental sobre a #21. Não mede distância,
TTC ou risco de colisão. A vibração de risco deve funcionar localmente **com ou
sem rede**. Hardware e compensação de câmera com IMU não estão implementados.

## Executar

Na raiz do checkout com esta implementação, Python 3.11+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[vision]'
python -m unittest discover -s tests -v

# Vídeo autorizado: caixas, IDs, trilhas e estado/motivo.
python -m sonar_vision.preview --weights models/yolo26n.pt \
  --video videos/cenario-autorizado.mp4

# Webcam: selecionar explicitamente o índice correto (Mac/Camo podem variar).
python -m sonar_vision.preview --weights models/yolo26n.pt --camera 0
```

Os pesos precisam existir e ser confiáveis, conforme [origem/licenças](vision.md).
Permita acesso à câmera ao terminal se solicitado. Não há download, envio de
imagens, áudio ou gravação de vídeo automática. `q`/`Ctrl+C` encerram. O resize
afeta só a janela; inferência usa o frame original. IDs podem mudar após oclusão.

Por padrão o movimento é **INCONCLUSIVO**, porque não sabemos se a câmera está
fixa. Caixas/IDs continuam visíveis. Para experimento com câmera realmente fixa,
sem zoom (notebook parado/tripé), habilite explicitamente:

```sh
python -m sonar_vision.preview --weights models/yolo26n.pt \
  --camera 0 --assume-fixed-camera --output results/webcam-fixa-01.json
```

Também funciona para vídeo de câmera fixa. Não usar essa opção num vídeo andando
ou girando a cabeça para “fazer aparecer” estados. É hipótese declarada pelo
operador, não detecção automática nem IMU validada. Setas mostram movimento na
imagem, não o lado do risco. `stable` não significa ausência de perigo.

### Amostragem e frames perdidos

```sh
python -m sonar_vision.preview --weights models/yolo26n.pt \
  --video videos/camera-fixa.mp4 --assume-fixed-camera \
  --stride 2 --drop-every 7 --max-frames 100 --output results/perdas-01.json
```

Stride processa um a cada N frames; drop-every descarta cada N-ésimo frame da
origem (contagem começa em 1). Max-frames limita frames processados, não capturados.
Frame_id e timestamp mantêm a posição original: descarte não acelera o movimento.
Isso simula amostragem, não rede real. `--headless` desliga a janela e ainda
exercita desenho em memória. Saída JSON opcional contém parâmetros, versões e
contagens agregadas, sem imagens, IDs, trajetórias individuais ou caminho da mídia.
Contagens são por objeto/frame, não pessoas/eventos/acurácia. Arquivos existentes
não são sobrescritos: escolha outro nome.

Vídeo usa índice/FPS declarado, hipótese de taxa constante. Vídeo de FPS variável
exige timestamps de apresentação antes de avaliação quantitativa. Webcam usa
relógio monotônico ao fim da leitura: não mede exposição nem elimina buffering.

## Análise e parâmetros

Cada dispositivo/sessão/epoch/ID possui estimador separado. Ajusta retas ao centro
normalizado e logaritmo da área em função do **timestamp da captura**, não do
recebimento na nuvem. Movimentos dinâmicos exigem confirmação temporal contínua.

| Evidência visual predominante | Estado experimental |
|---|---|
| Área crescendo/diminuindo | approaching/receding |
| Centro deslocando lateralmente | crossing |
| Variações pequenas | stable |
| Histórico insuficiente, irregular, misto ou câmera não fixa | unknown |

Crescimento também pode vir de pose, zoom ou movimento de câmera. Cruzar a imagem
não comprova cruzar o caminho do usuário. Movimento vertical relevante, ou lateral
e escala simultâneos, são inconclusivos. Câmera fixa não garante acerto.

`TrajectoryConfig` herda do lab os parâmetros abaixo, **sem reajuste nesta entrega**.
São experimentais, não limiares de risco. Overrides por Python ou
`--trajectory-config arquivo.json`; positivos/finitos e contagens inteiras.

| Parâmetro | Valor | Unidade |
|---|---:|---|
| window_seconds | 1.0 | s de histórico |
| min_span_seconds | 0.4 | s de extensão mínima |
| min_samples / max_samples | 5 / 120 | amostras do estimador |
| max_gap_seconds | 0.5 | s; intervalo maior reinicia segmento |
| lateral_threshold | 0.08 | largura/altura da imagem por s |
| log_area_threshold | 0.15 | variação de ln(área) por s |
| max_center_residual | 0.025 | RMS de centro normalizado |
| max_log_area_residual | 0.12 | RMS de ln(área) |
| confirmation_seconds | 0.4 | s do candidato dinâmico contínuo |

O estimador usa até 120 amostras; a trilha desenhada usa o histórico da #21
(padrão 60). Perda, gap, mudança de classe/câmera, reset ou troca de sessão não
herdam confirmação anterior. Não interpolar por oclusões. Poucos frames podem
impedir cinco amostras na janela: unknown em vez de ampliar limites automaticamente.

## Integração para Julio

`Frame` tem contexto **interno** opcional `camera_motion`: unknown padrão, moving
ou fixed. `Frame(..., camera_motion="fixed")` é para teste controlado, não default
de óculos nem afirmação física a aceitar cegamente do cliente.

- `Result.motions[track_id]`: estado, candidato bruto, motivo, direção lateral na
  imagem, velocidades aparentes, span, amostras e tempo de confirmação.
- `Result.observation()` preenche o campo movement **já existente**. Sem ID,
  permanece unknown. Direção de posição (`left/center/right`) continua unknown:
  não confundir direção do objeto com sentido do movimento.
- Diagnósticos/caixas/camera_motion não são novos campos do JSON 0.1. Nenhum
  contrato de rede foi ampliado; autenticação e HTTP continuam na #24.

13 FPS de captura não garantem 13 envios/s. Com uma requisição por vez, ciclo de
envio+inferência+resposta precisa caber em aproximadamente 77 ms para essa taxa,
além de captura/encodificação acompanharem. Ciclo de 200 ms limita esse esquema a
aproximadamente 5 respostas/s. São contas, não medições de ESP/nuvem. Não acumular
fotos antigas; escolher captura recente. ByteTrack ainda usa buffer em frames;
a trajetória usa segundos de captura. Avaliar associação sob amostragem baixa.

O benchmark local da [#21](experiments/issue-21.md) mediu aproximadamente 20 ms
por processamento, mas não incluiu rede/API/ESP/áudio nem rodou numa instância
AWS. É evidência inicial de viabilidade computacional, **não garantia de 13 FPS
ponta a ponta**. Dimensionamento e carga pertencem à #22; integração e latência
completas à #6/#27. Medir percentis, idade das capturas, descartes e múltiplos
dispositivos antes de prometer uma taxa. Treze análises/s não significam treze
falas/s: seleção/prioridade/repetição de anúncios ficam na #31 e reprodução local
na #18. Processamento rápido também não comprova identificação correta de risco.

### BNO085 e câmera móvel: pendente

Definir com firmware/cloud orientação e qualidade correspondentes à exposição,
época de referência, sincronização/calibração câmera-IMU, formato/versionamento
do envio e falhas. Invalidar uma fala direcional antiga é diferente de compensar
imagem/tracking. Rotação não elimina automaticamente translação/paralaxe ao
caminhar. Não inferir câmera fixa só por yaw estável. Não há compensação IMU aqui.

### Planejamento da compensação (a confirmar)

Na consulta às issues em 2026-09-22 não havia tarefa específica cobrindo toda a
compensação visual. #9 aborda geometria/orientação local, #17 captura/envio e #24
API, mas não equivalem à implementação completa dessa compensação.
Proposta de divisão, **não atribuição formal de novas tarefas**:

- Bryan: análise/compensação visual e validação dos limites com câmera móvel.
- Julio: contrato versionado e integração dos dados sincronizados na API.
- Trio de firmware: BNO085, referência/qualidade, captura e associação temporal.
- Matheus: apoio com cenários do simulador/avaliação; cada autor testa seu código.

Criar tarefas específicas após confirmar essa divisão e os critérios. Pode-se
começar a especificação e testes sintéticos sem hardware; não marcar compensação
como validada antes de testar sincronização/calibração e dados reais.

## Verificação e conclusão da issue

Testes: múltiplos alvos/sessões, aproximação/afastamento/cruzamentos, 8/13/30 FPS,
tempos irregulares, oclusões, gaps, câmera desconhecida e confirmação temporal.
Avaliação sintética separada das fixtures unitárias:

```sh
python -m sonar_vision.evaluate_trajectory --output results/avaliacao-01.json
```

Ver [evidências e falha conhecida de câmera](experiments/issue-11.md) e
[ADR 0012 proposto](decisions/0012-trajetoria-aparente.md).
Não encerrar a #11 só pelos testes sintéticos. Falta revisão interativa da janela
e avaliação real independente/anotada conforme #7, registrando erros, inconclusivos,
iluminação, amostragem e movimento de câmera.
