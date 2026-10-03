# Issue #27 — evidência de integração e ponta a ponta

Data: 2026-10-03. Responsável: Julio. Procedimento: [integration.md](../integration.md).

## Testes determinísticos

Windows 11 (10.0.26200), Python 3.13.12, extras `.[api,api-dev]`, commit base
`d38bacb` com as mudanças da #27 aplicadas:

- `python -m unittest discover -s tests -p "test_e2e*.py"`: 15 testes OK e 1
  skipped (o opcional com detector real), repetido 3 vezes sem falha.
- Suíte completa: 114 testes OK, 5 skipped (4 do ByteTrack sem `[vision]` e 1
  opcional). Sem extras: OK, 34 skipped, com a simulação tátil executada.

## Medição dependente do ambiente (não é meta nem validação)

`python -m sonar_vision_integration.bench --frames 50`, com backend
**simulado**, um dispositivo, requisições sequenciais e HTTPS em loopback, na
mesma máquina:

| Métrica | Valor observado |
|---|---|
| Desfechos | 50 admitidos, 0 descartados |
| Ida e volta no cliente | média 2,01 ms; P50 1,55 ms; P95 2,01 ms; P99/máx 23,81 ms |
| P95 no servidor | read 0,61 ms; inference 0,026 ms; encode 0,021 ms; work 0,074 ms; total 0,89 ms |

O P99 de 23,8 ms vem da primeira requisição (aperto de mão TLS e aquecimento).
Esses números medem só o custo do transporte e da API com detecção
roteirizada. **Não** representam o YOLO, o Wi-Fi do ESP32 nem a VM final. O
relatório JSON completo fica em `results/` (ignorado pelo Git) e pode ser
gerado de novo com o mesmo comando.

## Pendências

- Medição com o detector real (`--weights`) e com o cliente da #30 na rede do laboratório (#22/#6).
- Medição tátil e de áudio em hardware (#9/#18).
