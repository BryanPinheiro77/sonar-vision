# Avaliação visual e latência — #33

Síntese agregada; não valida segurança, licença ou qualidade das anotações.

Evidência: synthetic / controlled / synthetic.
Clips registrados: 3; sem frames: 0.
Confiança do detector não é qualidade medida. Aceitação experimental não avaliada.

| Classe | TP | FP | FN | Precision | Recall | Fontes | Amostra insuficiente |
|---|---:|---:|---:|---:|---:|---:|---|
| bicycle | 0 | 0 | 0 | N/A | N/A | 0 | sim |
| bus | 0 | 0 | 0 | N/A | N/A | 0 | sim |
| car | 0 | 1 | 0 | 0.0000 | N/A | 1 | sim |
| chair | 0 | 0 | 0 | N/A | N/A | 0 | sim |
| dining_table | 0 | 0 | 0 | N/A | N/A | 0 | sim |
| dog | 0 | 0 | 0 | N/A | N/A | 0 | sim |
| motorcycle | 0 | 0 | 0 | N/A | N/A | 0 | sim |
| person | 3 | 1 | 1 | 0.7500 | 0.7500 | 1 | sim |
| stairs | 2 | 0 | 1 | 1.0000 | 0.6667 | 1 | sim |
| traffic_light | 0 | 0 | 0 | N/A | N/A | 0 | sim |
| unknown | 0 | 0 | 0 | N/A | N/A | 0 | sim |

| Classe | Iluminação | Cenário | TP | FP | FN | Fontes |
|---|---|---|---:|---:|---:|---:|
| car | public_night | negative | 0 | 1 | 0 | 1 |
| person | good | approach | 3 | 1 | 1 | 1 |
| stairs | low | stairs_down | 2 | 0 | 1 | 1 |

Escopo de latência: capture_to_response; intervalos monotônicos únicos.
| Iluminação | Cenário | N | Média ms | P50 ms | P95 ms |
|---|---|---:|---:|---:|---:|
| good | approach | 4 | 25.0000 | 20.0000 | 40.0000 |
| low | stairs_down | 3 | 710.0000 | 70.0000 | 2000.0000 |
| public_night | negative | 1 | 50.0000 | 50.0000 | 50.0000 |

Estados: {"decode_error": 1, "ok": 7, "timeout": 1}
Diagnósticos de tracking: {"detection_loss": 2, "epoch_reset": 1, "fragmentation": 1, "id_switch": 1}

| Escada: verdade | Resposta up | Resposta down | Abstenção | Não detectada |
|---|---:|---:|---:|---:|
| up | 0 | 0 | 0 | 0 |
| down | 1 | 0 | 1 | 1 |

Confusões de classe: []

Parâmetros de associação/continuidade e mínimos de amostra são propostas a revisar na #7.
Resultados brutos e eventos por frame permanecem em armazenamento local restrito.
Nenhuma conclusão de caminho livre, contagem real de pessoas ou segurança física.

## Procedência e reprodução

Fixture original sintética: [issue-33-fixture.json](issue-33-fixture.json).
Código, configuração, modelos simulados, fontes e condições estão registrados
no snapshot; formato/procedimento em [guia #33](../evaluation.md).
Textos/anotações/predições próprios: AGPL-3.0-only; sem vídeo, peso ou participante.

Perfil usado apenas para cálculo: IoU=0.50, cutoff de confiança=0.50,
gap máximo=1 frame, mínimo declarado=2 fontes por grupo. Aprovação pendente;
não representa parâmetros de segurança, amostra suficiente ou desempenho real.
Totais: TP=5, FP=2, FN=2; precision=recall=5/7. Latência sintética: N=8,
média=285 ms, P50=40 ms e P95=2000 ms. Uma troca de ID, uma fragmentação,
um reset de epoch; falhas de detecção foram preservadas.

## Verificações executadas — 2026-10-02

Windows/PowerShell, Python 3.12.7. Os 27 testes da ferramenta passaram.
Suíte completa: 124 encontrados, 120 aprovados e 4 skipped por ausência das
dependências opcionais do ByteTrack real; 11,767 s reportados.
Associação comparada a força bruta independente em matrizes pequenas.
CLI retornou 0 na avaliação e baseline idêntica; diferenças de TP/FP/FN
e média de latência iguais a zero. Outputs existentes não foram sobrescritos.
Relatório detalhado/eventos ficam somente em results/issue-33/ (ignorado).
Verificações de whitespace e links locais sem erros.

Não foram avaliados vídeo real, precisão de detector real, identidade real,
desempenho no hardware, áudio/vibração, rede ou segurança física.
Protocolo/amostragem da #7 e interpretação por Bryan/grupo continuam pendentes.
Síntese para revisão; não fecha tarefas de coleta ou integração.
