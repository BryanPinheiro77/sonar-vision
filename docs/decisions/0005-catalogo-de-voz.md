# ADR 0005 — catálogo de voz verificável e avisos locais

- Data: 2026-10-02.
- Status: proposta da #32; não aceita nem interface aprovada.
- Responsável previsto: Matheus (@Matheus-xz), com apoio de IA.
- Revisão necessária: Bryan e frente de firmware na #25/#18.
- Referências: ADR 0001/0003, #5, #25, #26 e #32.

## Contexto

A #32 exige rastreabilidade de textos/arquivos, permissões de distribuição e
avisos essenciais disponíveis nos óculos sem rede. O contrato 0.1 transmite
texto; IDs de aviso/versão de catálogo e formato físico ainda serão revisados
na #25 com firmware. Não presumir AGPL para voz gerada por terceiros.

## Proposta implementada como ferramenta

Manter textos e manifesto JSON versionados, separando essential_local de visual.
Identidade interna é (catalog_version,id); arquivo tem hash SHA-256, tamanho,
duração e origem/configuração/versão. Direitos e revisão auditiva são explícitos.
Validador de bancada na biblioteca padrão Python, sem provedor ou rede, aceita
WAV PCM quando um perfil é informado. Perfil operacional permanece indefinido.
Fixtures usam silêncio e são bloqueadas para release.

Pacote ZIP inclui textos, manifesto, todos os arquivos e checksums, incluindo
avisos essenciais para provisionamento offline pela #26/#18. Release exige
declarações de aprovação #5/#25, firmware/provedor, direitos e revisão auditiva,
sem interpretar essas referências como comprovação automática.

Nenhuma mensagem 0.1 muda nesta proposta. Integração, instalação, prioridade,
repetição/interrupção e falhas pertencem à #25/#18; vibração continua local,
independente de arquivo/áudio/TTS/rede. A #25 decide migração caso adicione
identificador de catálogo às mensagens.

## Alternativas consideradas

- Frases completas versus montagem por fragmentos: completas permitem comparar
  áudio/texto e revisar prosódia individualmente; custo de armazenamento deve
  ser medido antes de aprovar o vocabulário/perfil.
- TTS remoto no caminho urgente: acrescenta dependência de rede incompatível
  com avisos essenciais locais; geração autorizada offline prepara o pacote.
- Escolher formato/provedor automaticamente: antecipa decisões do firmware e
  direitos ainda pendentes. Registrar opções/revisão antes do lote.
- Banco/serviço de catálogo agora: sem necessidade demonstrada; arquivos e
  ferramenta local atendem à preparação e revisão.

## Consequências e limites

Nenhuma dependência nova nem provedor contratado. SHA-256 detecta divergência,
não autentica origem nem comprova conteúdo falado. Revisão humana continua
obrigatória; referências de permissões/revisão são apenas declarações.
O formato local v1 e IDs propostos devem ser revisados pela #25 antes do uso
físico. Até aprovação e lote real, somente propostas e fixtures podem ser
apresentadas; esta ADR não registra decisão do grupo.
