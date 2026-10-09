# ADR 0019 — núcleo geométrico local simulado

- Data: 2026-10-09.
- Status: desenho de simulação e correção documental aprovados por Bryan,
  com resposta “aprovo”; implementação candidata sujeita a revisão por PR.
- Responsável: Bryan, com apoio de IA; revisão de firmware/bancada a designar.
- Issue: [#9](https://github.com/BryanPinheiro77/sonar-vision/issues/9).

## Contexto

O AGENTS.md, o escopo e o [ADR 0003](0003-eventos-semanticos.md) exigem alerta
geométrico local independente da VM. O diagrama histórico de percepção sugeria
“refinamento semântico do risco”, criando conflito. A #9 pede estruturas e testes
simulados antes de integrar sensores, atuação ou aprovar parâmetros operacionais.

## Decisão aprovada para simulação

Adotar a [especificação da #9](../local-geometry.md): núcleo C++17 puro, matriz
radial de 64 zonas, raios/extrínsecos explícitos, orientação com qualidade,
referência e timestamps monotônicos. Referencial artificial x à frente, y à
esquerda, z para cima; não presumir eixos/status/convenção reais dos sensores.

Separar cobertura, evidência de proximidade e derivada. Sem dados/perfil válido,
não declarar caminho livre. TTC radial candidato exige associação explícita de
ponto da fixture; mesma zona/mínimo/objeto não comprovam identidade. Tempo até
proteção é campo distinto, sem afirmar colisão física ou direção da caminhada.

Todo perfil de risco aceito nesta entrega tem estágio `fixture`, valores
explícitos e nenhum padrão operacional. Memória fixa e histórico limitado;
sem alocações/I/O na atualização, drivers, Arduino, FreeRTOS ou atuação.
Testes nativos mapeiam os 16 critérios; CI compila/executa com sanitizers.

Corrigir o diagrama para observações visuais, sugestões de áudio e telemetria.
Classes/track_id/trajectórias da VM não alteram risco/TTC/vibração local. A API
e o contrato remoto 0.1 permanecem preservados.

## Alternativas consideradas

- Derivar movimento do mínimo por setor ou da mesma zona: rejeitado porque
  superfícies podem mudar sem indicar movimento do mesmo ponto.
- Usar track_id visual para risco imediato: rejeitado pela independência local
  e ausência de comprovação de geometria/associação física.
- Implementar drivers/PlatformIO primeiro: fora do escopo da #9; impediria
  verificar lógica e falhas antes do hardware chegar.
- Usar valores operacionais padrão: rejeitado; fixtures não aprovam segurança.

## Consequências e limitações

O primeiro artefato do módulo [firmware](../../firmware/README.md) é somente o
núcleo e seus testes nativos. Ele produz evidência para a futura política local
(#4/#18); não aciona vibradores nem voz. RAM/stack/WCET no ESP, float, calibração,
status/ordenação/FoV dos sensores, associação real e limiares operacionais exigem
validação própria. Nenhuma infraestrutura AWS ou placa Edge é necessária.

A aprovação foi obtida antes do código. Resultados da implementação candidata
não encerram a issue antes de revisão/publicação autorizada e não validam
segurança física ou o protótipo vestível.
