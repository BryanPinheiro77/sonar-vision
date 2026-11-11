# #19 — preparação de software para a primeira bancada

16/10/2026. Bryan. Preparação documental a partir da main
`051900fbe8219262b0db6c047e101e59fa7384a8`; sem alteração de implementação,
contrato, dependências, configuração operacional ou infraestrutura.

## Entrega

- [Guia ESP/API](../bench-integration.md): divisão de frentes, modelos, TLS,
  captura/metadata, admissão, áudio opcional, falhas e rollback.
- [CSV vazio](issue-19-bench-template.csv): registro por tentativa para execução
  física futura. Nenhuma linha de resultado físico foi preenchida.
- [Integridade dos três pesos](issue-19-model-integrity.json): arquivos lidos
  diretamente do pacote privado e comparados ao manifesto e perfil R21 versionado.
- [Verificações locais](issue-19-local-checks.json): seleção dos testes existentes
  que cobre os mecanismos necessários ao roteiro. Não é execução física da matriz.

## Verificação realizada

Python 3.11.16, macOS. Reproduzir com os extras de API instalados, na raiz:

```sh
PYTHONPATH=src:tests python -m unittest test_e2e test_simulator_https test_local_audio test_token_ops test_runtime_options test_aws_release -v
python scripts/check_docs.py
git diff --check
```

Resultado: **63 testes passaram, zero falhas, erros ou skips**. Testes existentes
exercitam HTTPS real em loopback, CA/hostname, autenticação, limites, sessões,
duplicatas, expiração, timeout/busy, arbitragem e isolamento tátil simulados,
rotação de token, hashes/configuração e preflight com entradas controladas.
Backend simulado e doubles nos testes: não afirmar inferência dos pesos reais,
rede Wi-Fi/AWS, reprodução física ou latência do ESP nesta execução.

Integridade: os três hashes do pacote coincidiram com o manifesto privado e
`issue-22-r21-profile.json`; licença, avisos e código correspondente estão
presentes no arquivo. O manifesto registra autorização privada ao grupo em
09/10/2026. Não foram carregados checkpoints, publicados pesos, extraídos seus
metadados de treino para o Git ou enviadas mensagens a colegas. Presença de
documentos não é auditoria independente das licenças/datasets declarados.

## Escolhas e limites

Reutilizar procedimentos e testes existentes evita cliente, provisionador,
framework de teste ou serviço duplicado. O CSV tem só cabeçalho e referências
opacas, mantendo resultados físicos pendentes. O guia não aprova número de
tentativas, critérios de qualidade da #7 ou novos limites de segurança.

O perfil medido CPU4 usa runner paralelo optativo; a CLI normal permanece serial.
JPEG95 do computador não define escala do sensor OV2640. O certificado local
de loopback não autentica automaticamente um IP de LAN. Esses pontos devem ser
resolvidos/registrados no provisionamento e no firmware antes da comparação.

Hardware/firmware e bancada: Mathias, Tarcísio e Weslley, conforme divisão
confirmada por Bryan em 16/10/2026. O trio de Bryan fica com modelo/IA e cloud;
a preparação da interface não o torna responsável pela montagem.

Pendentes: #1 física; captura/cliente #17; arbitragem/WM8960/voz #18/#32;
perfis e avaliação de anúncios; execução instrumentada da matriz; dados reais
independentes #7/#11/#16; demonstração da #19. A implementação existente da
geometria local continua sem drivers/atuação física. O caminho tátil não passa
a depender do servidor por este preparo.

Nenhuma VM criada ou despesa gerada. A #19 permanece aberta. Esta entrega
publica somente a preparação; não constitui aceite ou execução da bancada.
