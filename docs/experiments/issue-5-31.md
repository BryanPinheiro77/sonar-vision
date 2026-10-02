# Issues #5/#31 — verificação sintética

- Data: 2026-10-01.
- Pessoa responsável pela contribuição: Matheus; revisão do grupo pendente.
- Política/configuração: [anúncios por áudio](../audio.md).
- Artefatos: src/sonar_vision/audio.py e tests/test_audio.py.
- Dados: observações sintéticas geradas em memória; sem câmera, pesos ou pessoas.

## Procedimento

Na raiz, PowerShell:

```powershell
$env:PYTHONPATH = 'src'
python -B -m unittest discover -s tests -p test_audio.py -v
python -B -m unittest discover -s tests -v
git diff --check
```

Registrar abaixo resultado efetivamente obtido. Testes usam relógio controlado
para fronteiras de cooldown/expiração, conteúdo equivalente entre tracks e
epochs, saturação, sessões isoladas e mensagens malformadas. A tabela completa
de classe/direção/movimento/escada verifica textos e directional.
Não mede desempenho acústico, latência física, compreensão ou segurança.

## Resultados

Execução em Windows, Python 3.13.5, branch anuncios-por-audio:

- Testes de áudio: 16 passaram, incluindo conexão com Result.observation() do núcleo visual.
- Suíte completa: 42 testes encontrados; 38 passaram e 4 testes do ByteTrack
  real foram ignorados pela ausência das dependências opcionais.
- Vocabulário: 220 combinações de classe/direção/movimento/sentido de escada
  verificadas; maior frase com 59 pontos de código (limite contratual: 120).
- git diff --check: sem erros nos arquivos rastreados; arquivos novos também
  verificados separadamente quanto a espaços finais e links documentais locais.

Esses resultados não validam ByteTrack real, reprodução, compreensão, latência
sensor–vibração ou integração com rede/API. Nenhuma dependência foi instalada.

## Pendências para revisão

Parâmetros são hipótese de laboratório. Sem integração com API #24,
catálogo #25, reprodução/arbitragem #18 ou risco local #9.
Nenhum resultado com participantes ou hardware. Testes opcionais de ByteTrack
ignorados não contam como validação real do tracker.
