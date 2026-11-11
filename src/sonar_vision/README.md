# Visão computacional

Instalação consolidada e demonstração: [guia #34](../../docs/execution.md) e
[roteiro](../../docs/demo.md). `smoke.py` verifica offline os comandos existentes
com fixtures sintéticas; não valida modelo, rede ou hardware reais.

Módulo da issue #21: `core.py` (interface/sessões),
`ultralytics_backend.py` (YOLO/ByteTrack), `benchmark.py` (execução sem janela).

Issue #11: `trajectory.py` (análise temporal), `preview.py` (janela local),
`evaluate_trajectory.py` (avaliação sintética). Veja o [guia](../../docs/trajectory.md).

Instalação, exemplos, testes, parâmetros e limites:
[guia do módulo](../../docs/vision.md).

O seletor experimental de anúncios da #31 está em `audio.py`, independente de
HTTP, TTS e hardware. Consulte [política, configuração e limites](../../docs/audio.md);
parâmetros propostos ainda dependem de aprovação.


A ferramenta evaluation_manifest.py verifica metadados da coleta #7 sem acessar
vídeos ou executar modelos. Consulte o [protocolo e comandos](../../docs/experiments/protocolo-visual.md).

O cliente simulador da #30 está em `simulator.py`; veja [execução, fixtures,
testes e limites](../../docs/simulator.md). Entradas locais são sintéticas,
sem sensores, TTS ou vibração.

A ferramenta audio_catalog.py prepara/valida/empacota o catálogo da #32.
Veja [catálogo, comandos, testes e pendências](../../docs/audio-catalog.md).
Não sintetiza voz, acessa rede ou reproduz áudio.

A ferramenta evaluation.py calcula métricas contra referências anotadas e
latência da #33. Consulte [formato, comandos e limites](../../docs/evaluation.md).
Não executa modelo, acessa hardware ou altera o contrato 0.1.
