# 0010 — Empacotamento da API em imagem Docker com Compose (proposta)

- Status: proposta da #28, para revisão do grupo.
- Data: 2026-10-03.
- Responsável: Julio (empacotamento); Bryan (operação na AWS, #23).
- Relacionadas: #28, #24 (ADR 0007), #26 (ADR 0009), #27, #22, #23.

> Numeração: 0005 e 0006 não existem na `main`. Renumerar no merge, se necessário.

## Contexto

A API da #24 só rodava a partir de um ambiente Python montado à mão. A #23
(deploy) precisa de um artefato reproduzível, sem segredos, que qualquer
integrante construa a partir de um clone limpo. O `AGENTS.md` já prevê Docker
Compose como baseline e proíbe adicionar tecnologia sem necessidade registrada.

## Decisão proposta

1. Uma imagem (`Dockerfile`, dois estágios, `python:3.12-slim`) com a API,
   usuário sem privilégios e `HEALTHCHECK` por HTTPS com validação de
   certificado (`sonar_vision_api.healthcheck`).
2. Variante padrão com backend simulado e sem PyTorch (`EXTRAS=api`); variante
   com detector real por `--build-arg EXTRAS=api,vision`, somente CPU.
3. `compose.yaml` com **um** serviço: sem banco, broker ou rede extra. Porta
   publicada só em `127.0.0.1`; sistema de arquivos somente leitura; `cap_drop`
   total; volumes `:ro`.
4. Segredos, certificados, tokens, pesos e catálogo entram por volume e ficam
   fora da imagem e do Git; `.dockerignore` os exclui do contexto de build.
5. Smoke test (`scripts/smoke.py`) gera credenciais temporárias e verifica a
   imagem de ponta a ponta; testes estáticos e de probe rodam sem Docker.
6. O TLS continua terminado na própria API (ADR 0007). Não há proxy reverso.

## Alternativas consideradas

- **Executar só com venv documentado:** menos peças, mas depende do Python e
  das versões do computador de cada pessoa.
- **Imagem CUDA/GPU:** sem benchmark que mostre necessidade (#22), seria
  complexidade e tamanho sem evidência.
- **Pesos embutidos na imagem:** facilitaria o uso, mas misturaria artefato
  com licença própria (AGPL-3.0 do Ultralytics e dos pesos) e inflaria a imagem.
- **Proxy reverso (Traefik/Nginx) e rede dedicada:** é decisão de deploy (#23);
  hoje seria um serviço a mais sem necessidade registrada.
- **Kubernetes, banco, broker:** proibidos sem aprovação do grupo.

## Consequências

- O smoke test valida a imagem simulada; a variante `vision` foi verificada
  manualmente e não roda no CI.
- Quem rodar no Linux precisa de `SONAR_UID/SONAR_GID` para ler a chave TLS.
- Sem lockfile e sem escaneamento de vulnerabilidades da imagem; versões
  transitivas podem variar.
- A independência do caminho tátil local não muda: o serviço é opcional para o
  alerta imediato.
