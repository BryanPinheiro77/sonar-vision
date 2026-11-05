# ADR 0028 — pinagem definida para a bancada

- Data: 2026-11-05.
- Status: decisão confirmada por Bryan; ensaio físico separado.
- Issues: #1, #17 e #18.
- Responsáveis pela montagem e firmware: Mathias, Tarcísio e Weslley.

## Contexto e decisão

Bryan forneceu o mapa de fios após soldar os fios dos componentes e confirmou:
“nao esta como proposta ja esta definido o mapa de fios é aquele mesmo”.
Adotar a tabela e a imagem em [Mapa de fios](../hardware-wiring.md) como
referência da bancada. Preservar os GPIOs, I2C comum e ramais 0/esquerdo e
1/direito do TCA9548A. Mudanças exigem registro e alinhamento com o grupo.

Não escolher outra pinagem genérica da ESP32-CAM nem manter o mapa como mera
proposta. A confirmação resolve o estado anteriormente indefinido de GPIOs e
ramais, sem comprovar funcionamento elétrico, aquisição, áudio ou atuação.

## Consequências

Os agentes devem ler a referência antes de implementar drivers ou tarefas.
Terminal exato do transdutor e pinagem interna da câmera não estão definidos
pela imagem; não completá-los por suposição. Ensaios de continuidade, tensões,
conflitos de periféricos e motores permanecem com hardware/firmware.
O cliente cloud segue o guia existente, sem alterar contratos ou bloquear o
caminho tátil local. Nenhum código de firmware é acrescentado por este ADR.

O rodapé da imagem menciona ADR 0027 como proposta. Preservamos a imagem
recebida, mas corrigimos sua referência textual aqui: ADR 0027 no repositório
é o deploy preservado; ADR 0028 registra esta pinagem confirmada.
