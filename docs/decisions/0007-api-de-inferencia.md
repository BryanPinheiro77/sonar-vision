# 0007 — API de inferência HTTPS separada do módulo visual (proposta)

- Status: proposta para revisão do grupo no PR da #24.
- Data: 2026-10-03.
- Responsável: Julio. Revisão: Bryan (visão) e Matheus (política de anúncios).
- Relacionadas: #24, #12, #6, #21, #22, #5/#31; ADR 0003 e ADR 0004.

> Numeração: 0005 e 0006 já aparecem em PRs ainda abertos (#11, #16 e
> anúncios por áudio). Esta ADR usa 0007 para não colidir; renumerar no merge,
> se o grupo preferir.

## Contexto

O contrato 0.1 define `POST /v1/inference` com multipart, Bearer por
dispositivo, HTTPS validado, limites de resposta e códigos de erro. O módulo da
#21 já oferece `VisionService` sem HTTP. Faltava o adaptador de rede, sem
misturar HTTP no módulo visual e sem decidir banco, broker, deploy ou firmware.

## Decisão

1. Pacote próprio `src/sonar_vision_api/`; `sonar_vision` continua sem HTTP.
2. FastAPI + uvicorn (baseline do AGENTS.md) e python-multipart, num extra
   opcional `api`, com versões fixadas. Testes usam o extra `api-dev`
   (httpx2, trustme). Licenças MIT/BSD-3-Clause/Apache-2.0, compatíveis com
   AGPL-3.0-only.
3. Somente HTTPS: o processo não sobe sem certificado e chave. Para uso local,
   uma CA de desenvolvimento gerada na máquina é confiada explicitamente pelo
   cliente; nenhum passo recomenda desabilitar verificação.
4. Credencial individual por dispositivo: o servidor guarda só SHA-256 do
   token num arquivo fora do Git. `device_id` vem da credencial, nunca do corpo.
5. Uma inferência por vez no processo, espelhando o lock não bloqueante do
   `VisionService`; requisição que não começa na hora recebe 429 `busy`.
   Não há fila de imagens.
6. Timeout do servidor menor que o do cliente (padrão 1500 ms < 2000 ms).
   Ao expirar, só a espera termina; a thread de inferência não pode ser
   interrompida, segue ocupando o slot (novas requisições recebem `busy`) e o
   resultado tardio é descartado e registrado como `abandoned`.
7. A política de anúncios entra por interface (`select(observation,
   capture_age_lower_bound_ms=...)`, por sessão). Padrão: `audio = null`.
8. Um único processo uvicorn: sessões ficam em memória.

## Alternativas consideradas

- **HTTP dentro de `sonar_vision`**: rejeitada pela própria issue.
- **`request.form()` do Starlette**: partes sem `filename` viram texto e o tipo
  da parte se perde; o parser de baixo nível permite exigir exatamente
  `metadata` (application/json) e `image` (image/jpeg).
- **Pillow para ler dimensões**: dependência extra; o cabeçalho JPEG (SOF) é
  lido com a biblioteca padrão antes de decodificar qualquer pixel.
- **Fila por dispositivo ou global**: contraria o contrato (sem imagens antigas).
- **Vários workers**: exigiria roteamento de sessão ou estado compartilhado;
  fica para a #22.
- **Banco para credenciais**: fora do escopo da issue; arquivo de hashes basta
  para o protótipo e permite revogação.

## Consequências

- Um dispositivo ocupa toda a capacidade enquanto infere; com vários óculos,
  respostas `busy` aumentam. Medir na #22 antes de mudar o modelo.
- Mudança de resolução gera `reset` explícito (novo `tracker_epoch`) em vez
  de erro; falha do backend devolve 500 e a próxima captura reabre a sessão
  com epoch novo, preservando a marca d'água de frames contra replay.
- Provisionar ou revogar credenciais exige reiniciar o processo.
- O backend simulado é declarado por `SONAR_API_BACKEND=simulated`, no log de
  inicialização e em `/healthz`; ele não comprova a integração real.
- Valores iniciais de upload (512 KiB) e pixels (1600×1200, máximo da OV2640)
  são propostas configuráveis, não limites validados; precisam de aprovação.
