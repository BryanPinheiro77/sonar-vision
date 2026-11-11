# Evidência da implementação local — #73

Data: 27/10/2026. Responsável: Bryan, frente modelo/cloud, com apoio de IA.
Base do primeiro ensaio: `aeae4ec` mais alterações da branch `feat/73-demo-panel`,
antes do commit local `4d2f24b`.
[Guia e pendências](../demo-panel.md), [ADR 0024](../decisions/0024-painel-demonstracao.md).

## Natureza da evidência

**Fonte e inferência simuladas, sem placa, câmera, sensor ou AWS.**
HTTPS nativo em loopback no macOS/ARM64, Python 3.11, extras existentes.
Não representa CPU4/R21 ou latência do ESP. A fonte gera dois padrões JPEG
visualmente distintos; as detecções são roteirizadas e não medem acurácia.

## Verificações de software

- Suíte final: **430 testes, 426 passaram e quatro skipped**, todos os skips
  relacionados a cenários optativos que exigem pesos reais. Os 23 testes da
  demonstração passaram. Relatórios privados em `.local/issue73/test-report/`.
  O teste de limite usa relógio controlado para não depender da fronteira entre
  segundos reais; a expiração automática também foi exercitada sem espectadores.
- Testes novos cobrem esquema/duplicatas/tipos, inválida sem zero, sequência e
  captura fora de ordem, boot, credencial/401/403, corpo declarado e chunked
  excessivo/413, excesso de consultas/429 sem bloquear inferência, hash exato,
  replay sem apagar previsões, timeout e corrida de conclusão/diagnóstico,
  falha do painel e expiração sem espectadores. Teste JS executa o código
  entregue com rede/relógio controlados, inclusive falha JPEG com ToF válido.
- Chromium local: duas imagens obtidas do servidor com hashes diferentes,
  conferência de hash no navegador, desktop 1440px e celular 390px sem overflow,
  pausa/retomada, atraso, desconexão e falha apenas do JPEG preservando ToF.
  Classes/IDs também possuem texto acessível. Zero erros de página observados.
- Para evitar alterar confiança do SO, o teste de renderização encaminhou as
  rotas do navegador ao servidor HTTPS real por adaptador Node com CA/hostname
  validados. Não desabilitou verificação TLS. Isso testa renderização com bytes
  do servidor local; **não** certifica configuração de confiança do navegador
  de apresentação, tráfego navegador→AWS ou acesso ESP real.
- Revisão independente de interface confirmou resolvidas as três correções:
  falha independente JPEG/ToF, rótulos móveis legíveis e equivalente textual.
  Detector executado uma vez: não resolveu CSS pelo caminho absoluto da rota;
  aviso de hierarquia foi confrontado com CSS/renderização. Dashes são
  placeholders de dados ausentes. Não é auditoria completa de acessibilidade.
- Ruff `E4,E7,E9,F`, sintaxe JS, links/JSON/índices documentais e diff verificados.
- Núcleo geométrico C++17: 16 grupos de aceite passaram na máquina; nenhum
  driver, pino, tarefa, limiar ou controle tátil alterado. Sem validação física.

## Compose e retenção

Imagem local construída com extra `api`, sem pesos/segredos; usuário não root,
assets HTML/CSS/JS/logo incluídos no pacote instalado. Compose base + overlay
`compose.demo.yaml` subiu saudável em loopback. Cliente externo validou CA,
mandou dois JPEGs e leitura ToF; ingestão sem credencial retornou401, válida204.
Consulta interna HTTPS confirmou painel, no-store, assets e JPEG/hash/previsões
correspondentes. Após a retenção, imagem e ToF estavam expirados/sem payload.
O teste de consulta interna não comprova peer/NAT autorizado de espectador externo.
Contêiner/rede próprios foram removidos ao final; nenhum recurso AWS criado.

## Carga local exploratória

[Agregado da comparação](issue-73-local-simulated.json). Uma condição por vez,
10 s, fonte sintética a no máximo 10 inícios/s, zero/um/três espectadores gerados
consultando a cada 2 s. Nenhuma outra fonte/aba durante a comparação válida.
O primeiro acionamento concorrente dos geradores foi invalidado e separado
nos arquivos privados; não entra na comparação.

A consulta inicial de configuração do próprio gerador consumia cota de leitura
junto das três consultas iniciais, produzindo um 429. O gerador agora deixa essa
janela terminar antes de começar a medição; a condição de três foi repetida.
Registrar essa limitação é necessário para não confundir o probe inicial com
um espectador adicional. As condições 0/1 não apresentaram esse 429.

409 no JPEG é conflito esperado quando chega outro frame entre snapshot e
consulta. O painel descarta a associação e tenta de novo no próximo ciclo,
sem sobrepor caixas antigas; foram registrados esses conflitos, não ocultados.
Não representam falha da inferência. CPU/RAM de servidor **não medidas** nesta
comparação nativa. Resultados de milissegundos do backend simulado não validam
capacidade de detecção. Três abas/2 s permanecem limite provisório.

## Critérios ainda pendentes

- Revisão do contrato com Mathias, Tarcísio e Weslley/#17, incluindo status
  nativos de validade/qualidade, zona/setor/agregação e relógio por boot.
- Roteiro AWS manual por Bryan: computadores autorizados, confiança TLS,
  verificação de origem AWS das imagens/leituras, restrições SG/allowlist,
  custos/recursos e limpeza no mesmo teto agregado US$15/8h.
- Comparação CPU4 com os modelos R21/runner/perfil congelados, recursos Docker,
  zero/um/três espectadores e três abas reais. Não há aceite de desempenho CPU4.
- ESP→AWS→navegador para ambos os canais; ensaio independente de falhas e prova
  física de que página/rede/nuvem não bloqueiam sensores/risco/motores locais.
- Push/PR e revisão do grupo, quando solicitados. Nada foi publicado.

Não encerrar a issue como totalmente validada a partir da simulação.

## Ampliação: coleta, histórico e visual reorganizado

Escopo da #73 ampliado explicitamente por Bryan em 27/10/2026: rodadas para
baixar/revisar e histórico com reprodução. Limites iniciais confirmados:
10 minutos, 3.000 imagens ou 100 MiB, primeiro atingido; exclusão em até 24h.
A retenção não garante que VM/disco temporários existam por 24h. O modo ao vivo
continua efêmero; armazenamento exige configuração/origem/permissão explícitas.

- Suíte da ampliação: **470 testes, 466 passaram e quatro skipped** por falta
  dos pesos reais optativos. Regressões incluem gravação fora da inferência,
  limites/fila/disco lento/falho, recuperação, dry-run sem remoção de fundo,
  ZIP/hash/retenção concorrente e cancelamento sem liberar slots de leitura cedo.
- Histórico no Chromium: busca por frame, reprodução 4×, play/pausa, próximo/
  anterior, caixas, tabela ToF independente e download. Teste de expiração limpa
  título/origem/posição e URL de download antigos; zero erros JavaScript.
- Download da rodada sintética do preview: **40 JPEGs, 39 leituras ToF** e todos
  os hashes conferidos. O último ToF pode não entrar quando a coleta atinge o
  limite de frames: canais são independentes e o encerramento não inventa par.
- Novo visual solicitado por Bryan após rejeitar a primeira organização:
  referência estrutural nos componentes Fleury/KPMG, mantendo marca Sonar.
  Sidebar Ao vivo/Histórico, superfícies/controles arredondados e detalhes
  técnicos recolhidos. Revisão de interface confirmou a direção e a correção
  de seleção expirada; não é avaliação formal com participantes.
- Capturas finais: desktop 1440px e celular 390px de ambas as páginas, sem
  overflow horizontal. O teste usa adaptador Node com CA/hostname HTTPS local
  verificados, sem desabilitar TLS; confiança real do navegador AWS não validada.
- Player usa captura original e o ToF anterior/igual à captura, nunca futuro;
  inválida/defasada fica indisponível. Lacunas não são interpoladas. Cache de
  dois JPEGs, uma requisição ativa e teto 10 imagens/s; velocidades altas podem
  saltar frames de exibição, preservando revisão manual e arquivos originais.

O primeiro núcleo do coletor e a API de histórico/download foram registrados em
commits separados, antes da interface. Correções de dry-run/recuperação também
ficaram separadas. Código/docs/segredos de outros projetos não foram copiados.
Não houve push, merge, deploy ou criação de infraestrutura AWS.

Compose final local (extra `api`, sem pesos): serviço saudável e não root,
dois JPEGs e duas leituras ToF válida/inválida persistidos; ZIP conferido com
dois hashes. Após recriar a API com coleta desligada, o histórico continuou
disponível no mesmo volume e o buffer ao vivo ficou vazio. Índice público não
exibiu a referência privada de permissão. Contêiner/rede e dados sintéticos
desse smoke foram limpos; o preview solicitado ficou separado e disponível.
Consultas internas ao contêiner não validam NAT/allowlist de navegador externo.

Continuam pendentes comparação CPU4/R21 com coleta/play/download e recursos,
implantação AWS manual, revisão física ToF/#17 e independência tátil real.
Os resultados sintéticos não encerram esses critérios.
