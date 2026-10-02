# Visão computacional

Módulo da issue #21: `core.py` (interface/sessões),
`ultralytics_backend.py` (YOLO/ByteTrack), `benchmark.py` (execução sem janela).

Instalação, exemplos, testes, parâmetros e limites:
[guia do módulo](../../docs/vision.md).

O seletor experimental de anúncios da #31 está em `audio.py`, independente de
HTTP, TTS e hardware. Consulte [política, configuração e limites](../../docs/audio.md);
parâmetros propostos ainda dependem de aprovação.


A ferramenta evaluation_manifest.py verifica metadados da coleta #7 sem acessar
vídeos ou executar modelos. Consulte o [protocolo e comandos](../../docs/experiments/protocolo-visual.md).
