# Como contribuir

Ao enviar uma contribuição, você concorda que ela poderá ser distribuída sob a
licença [AGPL-3.0-only](LICENSE) do projeto. Não inclua material de terceiros sem
permissão e identificação clara de sua origem e licença.

## Fluxo de trabalho

1. Escolha ou crie uma issue com objetivo e criterio de aceitacao.
2. Crie uma branch curta a partir de `main`, como `feat/telemetria-mqtt`, `fix/leitura-tof` ou `docs/protocolo`.
3. Faca commits pequenos e descritivos. O grupo pode usar os prefixos `feat:`, `fix:`, `docs:`, `test:` e `chore:`.
4. Abra um pull request usando o template e solicite revisao de outra pessoa.
5. So faca merge quando o criterio da issue estiver demonstrado e as verificacoes aplicaveis passarem.

Evitem commits diretos em `main`. Ativem no GitHub a protecao da branch com pelo menos uma aprovacao e, quando existirem, verificacoes obrigatorias.

## Definicao de pronto

Uma tarefa esta pronta quando:

- atende aos criterios de aceitacao da issue;
- possui teste automatizado quando a logica puder rodar sem hardware;
- inclui evidencia de bancada quando depender de hardware;
- nao expoe credenciais nem dados de participantes;
- atualiza contratos e decisoes afetados;
- registra limitacoes conhecidas no pull request;
- pode ser explicada pela pessoa responsavel, mesmo quando houve apoio de IA.

## Arquivos grandes

Nao enviem datasets, videos, modelos treinados ou resultados volumosos diretamente ao Git. Registrem scripts, metadados e instrucoes reproduziveis. Se arquivos grandes se tornarem necessarios, o grupo deve decidir entre Git LFS, DVC ou armazenamento externo antes de adiciona-los.

## Conduta e segurança

- Siga o [Código de Conduta](CODE_OF_CONDUCT.md).
- Vulnerabilidades devem ser relatadas conforme a [política de segurança](SECURITY.md),
  sem detalhes sensíveis em issues públicas.
