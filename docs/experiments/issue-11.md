# Evidências da implementação de trajetória — #11

Data: 2026-09-22. Responsável: Bryan, com apoio de IA.
Branch: feat/11-visual-trajectory, base no merge do PR #35.
**Implementação para teste; avaliação real independente pendente.**

## Engenharia

44 testes passaram com extras de visão: ByteTrack real, trajetória, integração
e desenho em memória. Novos testes escritos antes dos módulos (RED: módulos
ausentes); após implementação a suíte completa passou (GREEN). Sem dependências
opcionais, os testes de ByteTrack/OpenCV são explicitamente ignorados.

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m sonar_vision.evaluate_trajectory --output results/avaliacao-01.json
```

Não foi medida cobertura percentual ou acurácia real. Nenhuma webcam foi aberta
pelo agente. Desenho exercitado sem janela; revisão visual humana ainda pendente.

## Avaliação sintética separada

Gerador versionado `sonar_vision.evaluate_trajectory`, fixture `projected-boxes-1`,
seed 110022: projeção perspectiva e pequeno ruído de centro, diferente das
fixtures exponenciais dos testes unitários. Intervalos de 65 a 151 ms; 23 amostras
por cenário. Parâmetros do lab congelados, sem ajustar ao resultado desta fixture.
Uma posição lateral inicialmente fora da imagem foi corrigida no gerador antes
da execução válida; parâmetros do estimador não foram alterados.

| Cenário | Esperado | Última amostra |
|---|---|---|
| Estático | stable | stable |
| Crescimento frontal | approaching | approaching |
| Redução frontal | receding | receding |
| Esquerda → direita | crossing | crossing |
| Direita → esquerda | crossing | crossing |
| Lateral + escala | unknown | unknown |
| Pan, câmera unknown | unknown | unknown |
| Zoom, câmera moving | unknown | unknown |
| Zoom, câmera indevidamente fixed | unknown | **approaching (erro conhecido)** |

O último controle demonstra ambiguidade visual, não resultado a esconder ajustando
limiares. Script registra `mismatches=1`. As outras oito concordâncias não são
taxa de acerto real: caixas/contextos/rótulos sintéticos, sem YOLO. Dados reais
independentes/anotados continuam pendentes na #7.

## Smoke com vídeo local

Trecho autorizado já usado no lab, não holdout real e não publicado. YOLO26n,
CPU, entrada 640, confiança 0.35, ByteTrack buffer=60, Ultralytics 8.4.137,
Python 3.14.7/macOS 27 arm64. Comando reproduzível com outro vídeo autorizado:

```sh
python -m sonar_vision.preview --weights models/yolo26n.pt \
  --video videos/cenario-autorizado.mp4 --headless \
  --stride 2 --drop-every 7 --max-frames 100 --output results/preview-01.json
```

100 frames processados, 133 descartados pelo amostrador; origem 2160×3840,
FPS declarado 30.0036. Câmera unknown: 488 observações unknown (426 camera_not_fixed,
62 no_track). São objetos/frames, não pessoas únicas ou erros anotados. Verifica
decode, YOLO, tracking, desenho e descarte sem alterar linha do tempo; não comprova
precisão de movimento. Relatórios locais em results/ são ignorados no Git, sem
imagens, identidades ou trajetórias salvas. [Guia de execução](../trajectory.md).
