# ADR 0005 — trajetória aparente e contexto da câmera

- Data: 2026-09-22.
- Status: proposta implementada na branch da #11, sujeita à revisão do grupo.
- Responsável: Bryan, com apoio de IA.

## Contexto e proposta

A #21 isolou tracking por sessão. Câmera girando/com zoom pode gerar movimento
igual ao de um alvo; BNO085 e captura sincronizada não estão integradas ao contrato.
Portar parâmetros experimentais do lab sem reajuste, usando tempo de captura,
estado por track e confirmação temporal. Invalidar segmentos após perdas/gaps,
mudança de classe/câmera e reset. Estados usam enums já existentes no protocolo.

Contexto desconhecido produz unknown por padrão. `camera_motion=fixed` é opção
interna de experimento, não campo do protocolo ou medição de hardware. Não ativar
automaticamente em óculos. Moving/unknown apagam histórico do estimador/confirmador,
sem suprimir caixas/IDs. Viewer separado não salva mídia nem participa da segurança.

## Alternativas e consequências

- Classificar sempre: confunde câmera/alvo. Controle negativo demonstra falso
  approaching com zoom se a câmera for declarada fixed incorretamente.
- Esperar todo hardware: impediria testes puros; desenvolver com câmera fixa e
  simulações permite avançar sem afirmar compensação pronta.
- Inferir câmera só pelos alvos detectados: movimento comum não basta para
  considerar rotação/translação medidas.

Entrega não é navegação pronta: no uso vestível padrão, movimento permanece
unknown até haver caminho validado para câmera móvel. Não representa TTC,
colisão ou direção da caminhada. Evolução exige contrato IMU/imagem revisado,
sincronização/calibração e avaliação independente (#7). Caminho tátil não muda.
