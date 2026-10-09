# Núcleo geométrico local — #9

Primeiro artefato C++17 do firmware: **simulação no computador**, sem drivers,
Arduino, FreeRTOS, PlatformIO, placa, sensores ou atuadores integrados.
Responsável humano: Bryan, com apoio de IA. Desenho aprovado em 2026-10-09;
revisão/publicação da implementação candidata permanece pendente.
Código próprio: `AGPL-3.0-only`; nenhuma dependência externa foi adicionada.

## Objetivo e limites

Implementar a [especificação aprovada](../docs/local-geometry.md) e o
[ADR 0019](../docs/decisions/0019-nucleo-geometrico-local.md): transformar retornos
radiais calibrados e orientação explícita em setores, cobertura e proximidade.
Aproximação/TTC candidato só existem com associação explícita do mesmo ponto
na fixture. **Não se trata de associação real de alvo ou prova de colisão.**

- Eixos artificiais: x à frente, y à esquerda, z para cima.
- Dados faltantes, vencidos, fora de cobertura ou inválidos nunca significam
  caminho livre. `known` qualifica retornos, não uma área física inteira.
- Perfil de risco ausente/inválido preserva geometria utilizável, sem banda/TTC
  padrão. Todos os perfis aceitos aqui têm estágio `fixture`.
- Campo radial/TTC não é distância ao corpo, heading da caminhada ou
  confirmação de alvo convergente. Tempo até proteção é saída separada.
- Não há entrada de imagem, classe, track_id remoto, rede ou VM, nem saída para
  vibração/voz. O caminho local permanece independente da nuvem.

## Executar os testes

Na raiz do repositório, com Python 3 e compilador C++17 já instalado:

```sh
python3 scripts/test_local_geometry.py
python3 scripts/test_local_geometry.py --sanitize
```

`CXX` seleciona um executável (por exemplo `CXX=clang++` ou `CXX=g++`);
sem compilador, a verificação falha explicitamente. Sanitizers requerem suporte
do compilador/runtime. O runner compila em diretório temporário e remove o
binário ao terminar; não acessa rede, AWS, sensores ou dependências de ML.
Esses são comandos nativos; **não há comando de build/upload para o ESP**.

Compilação equivalente, guardando o executável localmente:

```sh
mkdir -p .local
c++ -std=c++17 -O2 -g -Wall -Wextra -Werror -I firmware/src/core \
  firmware/tests/native/local_geometry_test.cpp \
  firmware/src/core/local_geometry.cpp -o .local/local-geometry-tests
.local/local-geometry-tests
```

## Interface e armazenamento

[local_geometry.hpp](src/core/local_geometry.hpp) define entradas, enums/motivos,
optionals, saídas e `State`; [local_geometry.cpp](src/core/local_geometry.cpp)
implementa `sonar::local::update(input, state) noexcept`.

O chamador fornece ponteiros para dados válidos durante a chamada e mantém o
estado. Inicialize `State{}` para começar uma sessão independente. Zero IDs/
perfis/raios não são configuração utilizável. Não compartilhe estado entre
sessões concorrentes. Esta interface C++ local não modifica IDs/API remotos.

Arrays de 64 zonas e três setores, máscara fixa de motivos, nenhuma string/fila
ou alocação dinâmica na função. Estado retém só a aquisição anterior (64
alcances), instantâneos da configuração e relógio. Mudança de conteúdo ou ID
reinicia continuidade; duplicata não substitui histórico; regressão/entrada
inválida o quebra. Índices reordenados são normalizados; empate usa menor índice.

Sem observação, `unavailable` tem precedência; com geometria e perfil de risco
inválido, `unconfigured`. Exclusão de volume ou quadro parcial limita cobertura.
Contagens de quadro recusado são conservadoras 0/64, não status bruto real.
Associação inválida afeta derivada, sem apagar proximidade atual válida.

## Mapa de testes e resultados locais

[Fixtures nativas](tests/native/local_geometry_test.cpp) contêm AC-1 a AC-16:

| Critérios | Cobertura |
| --- | --- |
| AC-1/2 | Setores/fronteiras, extrínsecos, inclinação, equivalência q/-q |
| AC-3/4/5 | Orientação inválida, ausência de frame, cobertura parcial positiva |
| AC-6/7/8 | Idade/skew, futuro, duplicata, regressão, limites de dt |
| AC-9/10/11 | Ponto associado, TTC/proteção, recuo/parado, identidade não inferida |
| AC-12/13 | Sessão/referência/calibração/perfis novos ou alterados; ausência de limiares |
| AC-14/15/16 | Independência offline, guarda de alocação, não finitos/extremos, limites de buffers e volume |

Em 2026-10-09, Apple Clang 21.0.0, arm64/macOS, double: **16/16 grupos passaram**,
com e sem AddressSanitizer/UBSan. Cada grupo contém várias verificações, não são
16 vídeos ou ensaios físicos. Guarda de `operator new/new[]` ativa em toda
chamada; inspeção do objeto otimizado encontrou somente matemática/memória e
proteção de stack, sem símbolos de rede/I/O/alocação. Estado nativo: **2856 bytes**,
64 registros; isso não mede RAM/stack no ESP nem garante WCET. Tolerância de
fixture `1e-9` não representa erro físico aprovado.

CI adiciona `Local geometry (C++17)` com GCC e sanitizers, incluído em `CI result`.
Execução Linux remota será verificada quando o PR for autorizado/publicado;
os testes locais foram executados com Clang, não alegam validação GCC/ESP.

## Pendências físicas e próximas interfaces

Sem validação de distância/status/ordenação/FoV/extrínsecos reais, precisão
float, orientação na placa, associação física, orçamento de execução no ESP,
limiares operacionais, política de degradação/háptica (#4/#18), drivers ou atuação.
A aquisição real e o alerta tátil exigem testes de bancada posteriores. Nenhum
participante, vídeo, dataset, peso ou credencial faz parte desta entrega.
