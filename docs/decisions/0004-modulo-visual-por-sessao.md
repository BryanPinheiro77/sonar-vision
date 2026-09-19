# ADR 0004 — módulo visual independente de HTTP e estado por sessão

- Data: 2026-09-19.
- Status: proposta implementada na #21, sujeita à revisão do PR por Bryan/grupo.
- Responsável pela implementação: Bryan, com apoio de IA.

## Contexto

O lab executava um vídeo por processo. Na API, misturar o estado de usuários
produziria associações de IDs incorretas. O contrato 0.1 exige epoch após reset;
não comporta caixas ou histórico no JSON enviado aos óculos.

## Decisão proposta

Núcleo Python sem dependências/HTTP, factory de backends substituível por fixtures,
detector YOLO compartilhado no processo e ByteTrack independente por par
dispositivo/sessão. Estado e histórico limitados, epoch novo após reset/erro,
rejeição não bloqueante de trabalho concorrente, sem fila de imagens antigas.

Na versão fixada de Ultralytics (8.4.137), BaseTrack possui contador global.
O adaptador usa uma classe de track específica por sessão com contador próprio
e não reseta esse contador global. Testes com ByteTrack real verificam sessões
intercaladas e IDs novos na primeira após abrir a segunda.

Caixas e histórico são internos. Serialização respeita o contrato existente;
movimento/direção desconhecidos até suas etapas. Não implementar distância,
TTC, política de áudio, firmware ou alteração de risco local.

## Alternativas

- Copiar integralmente o loop de webcam: mistura captura/UI e heurísticas de
  risco não validadas com o serviço; dificulta testes e integração.
- Compartilhar `model.track(persist=True)` entre usuários: pode compartilhar
  tracker; instâncias separadas ainda exigem tratar o contador global de IDs.
- Um processo/modelo por sessão: isolamento mais forte, mas memória e operação
  adicionais sem dimensionamento. Reavaliar na #22, não assumir capacidade AWS.
- Implementar API agora: responsabilidade #24 de Julio; não bloqueia o módulo.

## Consequências

API recebe interface testável agora. Modelo/configuração explícitos permitem
comparar YOLOv8n e YOLO26n sem eleger vencedor por data de lançamento. Histórico
é descartável e IDs não comprovam identidade real. Serialização global limita
throughput; roteamento por sessão, autenticação e cancelamento ficam para #24.
Upgrade da dependência exige novos testes do adaptador. #11 usa histórico sem
assumir continuidade após perda/expiração. Perfil do contrato não foi alterado.
