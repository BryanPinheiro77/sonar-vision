# ADR0023 — perfil experimental do seletor determinístico de anúncios

- Data: 2026-10-16.
- Status: aprovado por Bryan para experimentos de software, resposta "aprovo".
- Responsável pelas #5/#31: Matheus. Registro da decisão: Bryan.
- [Aprovação e hash](../experiments/issue-31-profile-approval.json).
- [Consolidação e limitações](../experiments/issue-5-policy-consolidation.md).

## Contexto

AudioPolicy e sua conexão optativa com a API já estão implementados. O perfil
de laboratório era explícito, mas ainda proposto; a #31 exige critérios
aprovados de relevância, prioridade e repetição. Bryan aprovou preservar o
perfil apresentado para a etapa experimental de software.

## Decisão

Congelar [audio-experimental-31.json](../experiments/audio-experimental-31.json),
cópia idêntica do perfil histórico da #52: corte0,50, cooldown por track2000ms,
supressão equivalente10000ms, retenção30000ms,32tracks/32descrições por instância.
Desempate de classes: person,car,motorcycle,bus,bicycle,chair,dining_table,dog,stairs.
Mudança de estado elegível precede entrada nova; demais desempates por classe,
score e ordem original permanecem como implementados/testados.

Aprovação permite usar essa configuração como baseline explícita em experimentos
de software. API mantém NullPolicy/audio=null sem configuração; não habilitar
anúncios automaticamente. Risco/TTC/vibração e validade do contrato0.1 não mudam.

## Alternativas e consequências

- Reajustar valores antes de medir falhas: rejeitado nesta rodada, por não haver
  evidência justificando mudança. Perfil congelado permite comparações reproduzíveis.
- Ordenar classes como risco físico: rejeitado. Desempate atual pode favorecer
  pessoa sobre escada, sem afirmar urgência local ou caminho livre.
- Repetir a cada frame ou ID novo: mantém-se supressão; pode silenciar objetos
  distintos com descrição equivalente. Seletor registra sugestões, não fala executada.

O registro não aprova adicionalmente todos os textos do catálogo, voz/provedor,
direitos, formato PCM/WM8960, instalação ou reprodução física. Correspondência
de texto/envelope com a proposta da #25 é verificável em software; validação
física e revisão da frente de firmware permanecem nas #18/#32.

## Verificação e pendências

65 testes existentes de política, HTTPS, arbitragem simulada e catálogo passaram
sem falhas/erros/skips antes da aprovação, com o mesmo perfil. Manter evidências
e revisão da consolidação na #31. A #5 continua aberta para compreensão,
interrupções e carga cognitiva; a #32 para voz e revisão auditiva.
Sem contratação, infraestrutura, treino, parâmetros novos ou dependências.
