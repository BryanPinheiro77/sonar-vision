# Correção da cadência proposta — #22/#11

Data: 2026-10-06. A oferta de 2 frames/s da proposta inicial não atende a
trajetória atual. A configuração exige cinco observações por track em uma
janela de um segundo, com pelo menos 0,4 s de histórico e mais 0,4 s de
confirmação. Não basta detectar a classe em uma imagem ou manter um ID.

Controle determinístico: caixas perfeitas de pessoa em aproximação aparente,
ID constante, câmera fixa declarada, três segundos de observações. Código e
parâmetros iguais aos da #11; nenhuma inferência de distância/TTC.

| Cadência | Máximo de amostras na janela | Primeiro approaching confirmado |
|---|---:|---:|
| 2/s | 3 | Nunca; insufficient_history |
| 5/s | 6 | 1200 ms |
| 8/s | 9 | 1000 ms |
| 10/s | 11 | 800 ms |

O novo teste da #11 cobre a incompatibilidade de 2/s e o controle de 10/s.
Isso prova uma condição de software; caixas/IDs perfeitos não são acurácia
real. Em câmera móvel, o contexto padrão continua desconhecido e o estimador
se abstém, independentemente do FPS.

## Ensaio curto com oferta de 10/s

JPEG preto original 640×480, um dispositivo, cinco segundos, HTTPS loopback,
YOLOv8n/ByteTrack reais, escadas v3 opcionais. Código `cd3e093`, checkout limpo
na medição. O [relatório agregado](issue-22-cadence.json) preserva hashes dos
pesos, configuração, versões, recursos e desfechos.

| Perfil | Oportunidades | Tentadas/admitidas | Drops antes da captura | Taxa admitida na janela | P95 HTTPS até admissão |
|---|---:|---:|---:|---:|---:|
| Geral | 50 | 21/21 | 29 | 4,2/s | 300,17 ms |
| Geral + escadas | 50 | 13/13 | 37 | 2,6/s | 430,38 ms |

O cliente descartou oportunidades enquanto a chamada anterior estava ativa;
não criou fila e não reenviou capturas antigas. A nova meta de ≥8/s não foi
demonstrada nessas execuções. Variação de desempenho em ensaios adicionais
reforça a necessidade de repetições controladas, dados representativos e
medição na VM antes de dimensionar.

Um ensaio de configuração chamou torch.set_num_threads antes de carregar o
modelo, mas o Ultralytics voltou a definir oito threads ao selecionar CPU.
Essas execuções não constituem comparação controlada de uma/duas threads e
não sustentam alegação de otimização. O executor agora registra um snapshot
das configurações de threads do PyTorch, distinguindo configuração observada
de intenção. A [documentação PyTorch](https://docs.pytorch.org/docs/2.14/generated/torch.set_num_threads.html)
define o escopo desse ajuste. Nenhuma configuração do serviço foi alterada.

A [proposta revisada](issue-22-proposta.md) usa 10 ofertas/s, ≥8 admissões/s e
orçamentos de latência compatíveis com uma chamada ativa. Bryan autorizou
prosseguir localmente com a meta de cadência; os demais limites e o orçamento
continuam propostos. Cadência efetiva por alvo, perdas/trocas de ID e movimento com
referências humanas precisam ser avaliados na #7/#11; FPS agregado não os prova.
Os relatórios preservam acceptance_evaluated=false; não há resultado de
acurácia, hardware ou AWS nesta entrega.
