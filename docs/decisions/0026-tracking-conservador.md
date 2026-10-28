# ADR 0026 — perfil conservador de tracking experimental

- Data: 2026-10-28.
- Status: aprovado por Bryan para adoção experimental, resposta “vamos com o candidato”.
- Responsável: Bryan, com apoio de IA; implementação sujeita à revisão por PR.
- Escopo: [#11](https://github.com/BryanPinheiro77/sonar-vision/issues/11), sem encerramento da avaliação.

## Contexto

Vídeos privados gravados por Bryan com iPhone em movimento revelaram
fragmentação de IDs para pessoas distantes e perda após oclusão. O corte 0.35
antes do ByteTrack descartava caixas fracas que poderiam manter identidades.
Três variantes com associação fraca reduziram a fragmentação de um caso,
mas prejudicaram controles antes estáveis. Um ID perdido chegou a vencer
um ID ativo pela diferença de custo de aproximadamente 0.0014.

## Decisão

Adotar o candidato conservador como padrão de `VisionConfig`: confiança de
saída 0.35, associação interna 0.25, high/new 0.35, low 0.25, margem de
reativação 0.02. Resolução, pesos, buffer 60, match 0.8 e fuse_score=true
permanecem. Caixas abaixo do corte de saída não aparecem no resultado nem
criam novos alvos; servem à manutenção de identidades. Cortes efetivos e
configuração são registrados nos metadados privados.

Na primeira associação, recusar um par ID perdido/detecção quando outro ID
da mesma classe é viável e seu custo é no máximo o custo desse perdido mais
a margem. Avaliar todos os pares pela matriz original. A regra pode recusar
ambos os IDs perdidos em uma disputa; não força identidade. Preservar a
segunda associação e o isolamento de estado/contadores por sessão.

Bryan selecionou o candidato após a comparação e relatou pouca diferença
visual geral. A escolha é operacional para experimentos; não é declaração
de superioridade quantitativa ou aprovação de segurança pelo grupo.

## Alternativas e consequências

- Manter o perfil antigo: preserva referência conhecida, mas perde a melhoria
  pontual no alvo distante. Permanece disponível por configuração explícita.
- Apenas baixar o corte: rejeitado nesta rodada devido às regressões observadas.
- Forçar recuperação após oclusão ou aumentar buffer: não corrige ausência de
  sobreposição entre previsão e reaparecimento, podendo associar outra pessoa.
- Treinar outro modelo ou substituir tracker: sem necessidade demonstrada
  por esta comparação; nenhuma tecnologia, peso ou dependência adicionada.

O candidato pode gerar mais caixas temporariamente sem ID e fragmentações.
Não resolve compensação de câmera/IMU, aparência/reidentificação ou o caso
de oclusão revisto. O especialista de escadas preserva seu corte de confiança.
API 0.1, política de áudio, risco/TTC e alerta tátil local não mudam. Alterar
o padrão no código não implanta nem cria recursos AWS.

## Verificação e limites

[Evidência agregada e procedimento](../experiments/issue-11-candidato-conservador.md).
Continuam pendentes anotação independente, validação de câmera móvel e
comparação de desempenho ponta a ponta. Vídeos, previsões individuais,
caminhos pessoais e pesos não integram esta decisão pública.
