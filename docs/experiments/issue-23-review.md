# #23 — revisão local antes de publicação

08/10/2026. Revisão crítica local pela mesma sessão autora, com três perspectivas
sequenciais da skill adversarial-reviewer. **Não é revisão de PR por outra conta
nem substitui revisão humana.** Escopo: provisionador/cleanup, Compose, preflight,
credenciais offline, smoke/probe, testes e procedimento/evidência.

## Achados e tratamento

- Falhas operacionais: `on-failure` não é recuperação de parada manual; primeiros
  métodos de injeção não provaram crash. Método final usou processo do contêiner
  próprio e comprovou aumento de RestartCount. Documentado no resultado.
- Reprodução: runbook ainda dizia que#22 não tinha aceite e não explicava
  transferência/SAN/env. Corrigidos perfil aceito, comandos e handoff de pesos.
- Segurança/custos: preço zero permitiria estimativa inválida apesar do uso de
  créditos. Provisionador passou a exigir preços positivos; testes rejeitam0.
  Alerta de Budget não é cap; ledger manual precisa reconciliação em cada rodada.
- Probe: extração de classe usava chave errada do contrato; teste com resposta
  não vazia detectou `KeyError`. Corrigido para `class_name`; teste passou.
- Evidência: logs com prefixoCompose e ausência de timestamps não permitem
  agregação de recursos. Exportados logsDocker puros e timestampados da mesma
  execução; agregador validou identidade, limites e426requisições correspondentes.
- Credenciais: restauração temporária em recuperação não deve virar procedimento
  recomendado. Nova rotação invalidou as duas antigas; procedimento exige
  provisão de token novo após revogação total.

## Riscos que limitam o aceite

FPS da cadeira abaixo da meta; não declarar capacidade irrestrita. Dependências
transitivas sem lockfile não garantem rebuild idêntico. Lock do operador é local,
sem transação global entre computadores: uma pessoa serializa rodadas. Timer
real/reboot não executados; houve remoção manual/auditoria. Pesos requerem handoff
privado legítimo. Nenhum deploy permanente ou validação física autorizado.

Resultado: implementação revisável para operação experimental com essas
limitações explícitas. Publicação/PR/CI/revisão humana continuam pendentes.
