# 0009 — Distribuição do catálogo pela API, com arquivos e manifesto (proposta)

- Status: proposta da #26, para revisão do grupo e da frente de firmware (#18).
- Data: 2026-10-03.
- Responsável: Julio.
- Relacionadas: #26, #24 (ADR 0007), #25 (ADR 0008), #32, #18.

> Numeração: 0005 a 0008 aparecem em PRs abertos. Renumerar no merge, se necessário.

## Contexto

Os óculos precisam receber o catálogo de vozes (#32) com versão e integridade
verificáveis, sem expor credenciais, sem URLs permanentes e sem baixar nada
durante uma urgência. A #24 já oferece HTTPS validado e credencial por
dispositivo, e a #25 define o que o aparelho aceita instalar.

## Decisão proposta

1. Servir o catálogo pela própria API da #24, com o mesmo token Bearer:
   `GET /v1/catalog/manifest` (com ETag) e `GET /v1/catalog/files/<path>`.
2. Pacote em diretório (`manifest.json` + `audio/*.wav`), validado na
   inicialização com as regras do dispositivo (#25) e regras de publicação:
   caminhos estritos, nenhum arquivo extra, WAV conforme o perfil, aprovações,
   origem, licença e revisão declaradas. O pacote é servido da memória.
3. Integridade de ponta a ponta pelo SHA-256 declarado no manifesto, conferido
   pelo aparelho antes de instalar. A troca é atômica (#25).
4. O aparelho só atualiza fora de urgência local e mantém o catálogo anterior
   em qualquer falha.
5. Sem banco: atualizar é publicar uma pasta nova e reiniciar a API.

## Alternativas consideradas

- **Bucket ou CDN com URLs públicas ou assinadas:** exigiria outro provedor e
  outra credencial, e as URLs poderiam vazar ou ficar em cache.
- **Download do ZIP inteiro:** é mais simples de transferir, mas obriga o
  ESP32 a descompactar e ter espaço para o pacote inteiro, e não permite
  repetir só o arquivo que falhou. Arquivos individuais com hash são
  verificáveis um a um.
- **Assinatura do pacote (Ed25519 etc.):** autenticaria a origem mesmo fora
  do TLS, mas exige gerenciar chaves e verificar no firmware. Fica como
  evolução, se o grupo exigir.
- **Banco de dados para versões:** sem necessidade demonstrada.
- **Recarregar o pacote sem reiniciar:** acrescenta estado concorrente; o
  reinício é simples e auditável.

## Consequências

- Um catálogo publicado por vez. Rollback é voltar à pasta anterior.
- O SHA-256 detecta corrupção, e a confiança na origem depende do TLS e do
  acesso ao servidor.
- Origem e licença continuam dependendo de declarações revisadas por pessoas;
  a API apenas recusa publicar sem elas.
