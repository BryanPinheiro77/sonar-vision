# Sonar Vision — painel de demonstração

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Bryan e participantes da apresentação acadêmica, observando capturas e leituras
remotas. Escopo confirmado na #73 e na conversa de implementação de 27/10/2026.

## Product Purpose

Mostrar o último JPEG recebido pelo servidor e a última leitura ToF, com origem,
tempos, validade e indisponibilidade explícitos. Sucesso de software não confirma
segurança física nem integração ESP real.

## Capabilities and Constraints

FastAPI existente, HTML/CSS/JS sem framework novo, sem login de espectador e
acesso restrito pela rede. Upload autenticado; segredos fora do navegador.
Uma fonte/sessão selecionada pelo operador; ao vivo temporário e coleta
experimental optativa por rodada. Bryan ampliou a #73 em 27/10/2026 para
download/revisão e histórico com play/pausa, busca, avanço e velocidade.
Limites aprovados: 10 minutos, 3.000 imagens ou 100 MiB por rodada, o primeiro
atingido, com exclusão em até 24h. Arquivos não sobrevivem à destruição do volume.
Sem treino automático. Inferência 0.1 preservada. Tátil independente da nuvem.
Integração física e revisão do contrato com hardware permanecem pendentes.

## Brand Commitments

Logo existente em `docs/assets/logo-sonar-vision.jpeg`. Bryan aprovou em
27/10/2026 a proposta experimental de fundo claro, azul/verde do logo e fonte
do sistema, imagem em destaque e ToF ao lado, com estados independentes.
Não é uma identidade oficial nova.

Bryan rejeitou a primeira organização visual e solicitou em 27/10/2026 um
visual mais organizado/arredondado, como POC Fleury e KPMG Agente. A reformulação
preserva marca e cores do Sonar Vision, acrescenta navegação e recolhe detalhes
técnicos. As referências orientam estrutura/controles, sem copiar conteúdo,
marcas de terceiros, dados ou dependências desses projetos.
