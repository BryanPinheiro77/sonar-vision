# ADR 0001: iniciar com ESP32-S3 e VM

- Status: aceita
- Data: 2026-08-27

## Contexto

O projeto precisa de um caminho inicial executavel que preserve a seguranca local e permita comparar alternativas de processamento sem comprar hardware prematuramente.

## Decisao

A primeira versao tera duas camadas:

1. ESP32-S3 para sensores, geometria, risco, TTC e alerta tatil local.
2. VM para deteccao, tracking, trajetoria, telemetria e contexto semantico.

Uma placa Edge nao faz parte do MVP. Ela so podera ser adotada se benchmarks de latencia, confiabilidade, consumo, custo e mobilidade demonstrarem vantagem suficiente. Permanecer apenas com a VM e um resultado valido.

## Consequencias

- O modo tatil deve continuar funcional quando a VM ou a rede falhar.
- O protocolo devera permitir mudar o local da inferencia sem reescrever as politicas locais.
- Nenhuma pasta, dependencia ou compra relacionada a Edge sera necessaria antes dessa decisao experimental.
