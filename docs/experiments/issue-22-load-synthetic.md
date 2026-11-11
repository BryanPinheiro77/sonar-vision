# #22 — ensaio curto de carga oferecida, 2026-10-06

Código `261718f`, checkout limpo no início dos quatro perfis. Entrada original
sintética preta 640×480, pré-codificada; dois frames/s por cliente durante cinco
segundos. HTTPS com CA validada, credenciais temporárias e uma requisição ativa
por cliente; servidor com um slot global. Sem câmera, AWS ou participantes.

Python 3.11.16, macOS 27.0.1 arm64, dez CPUs lógicas. Pesos YOLOv8n e escadas v3
obtidos conforme [releases](../releases.md); hashes/configuração/versões e
recursos estão no [relatório agregado](issue-22-load-synthetic.json).

| Perfil | Oportunidades | Admitidas | Busy do servidor | Drop antes da captura | P95 inferência |
|---|---:|---:|---:|---:|---:|
| Um cliente / geral | 10 | 10 | 0 | 0 | 367,81 ms |
| Dois / geral / alinhados | 20 | 10 | 10 | 0 | 129,90 ms |
| Dois / geral / espaçados | 20 | 20 | 0 | 0 | 120,23 ms |
| Um / geral + escadas v3 | 10 | 10 | 0 | 0 | 370,90 ms |

O ensaio revela contenção mesmo com poucos envios por segundo: dois clientes
alinhados não conseguem compartilhar um slot sem rejeições. Espaçar as
oportunidades evitou essas rejeições nesta execução, mas não garante justiça
ou fase estável numa rede real. Não foi adicionada fila ou alterada a capacidade.

P95 de aquisição **sintética** até admissão foi 391,40 ms no perfil geral de
um cliente e 376,56 ms no dual. A inicialização do modelo ocorreu antes da
janela; a primeira chamada do executor e efeitos de baixa taxa de oferta
continuam nas amostras. Dez amostras por cliente produzem percentis grosseiros;
essas execuções não comprovam a meta proposta de P95 de processamento ≤200 ms.
O desempenho do benchmark contínuo anterior não pode ser extrapolado para
este modo de envio espaçado ou para a AWS.

CPU média normalizada pelas dez CPUs lógicas foi 3,47%, 3,56%, 5,71% e 5,96%,
respectivamente, incluindo o cliente e o servidor durante a oferta. Pico de
RSS de 398 MB é o máximo desde o início do **mesmo processo**, incluindo
inicialização e perfis anteriores; não é consumo independente de cada modelo.
Para comparar RAM isolada, repetir cada perfil em processo novo. Temperatura,
carga externa e consumo de toda a máquina não foram medidos.

As fontes são sintéticas e não medem precisão de detecção, trajetória ou
escadas. `acceptance_evaluated=false` permanece em todos os relatórios.
Não houve seleção de instância/região, aprovação de metas nem gastos.

Verificações: 320 testes completos passaram com extras e pesos reais, sem
skips; os cinco testes de carga/configuração também executaram, sendo três
HTTPS. Sem extras, os dois testes de configuração/recursos passaram e os três
HTTPS foram explicitamente skipped. Ruff 0.16.10, links/JSON e diff passaram.
