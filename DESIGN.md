---
name: "Sonar Vision — painel experimental #73"
description: "Referência visual implementada para Ao vivo e Histórico; não é identidade oficial."
colors:
  ink: "#123d54"
  muted: "#526877"
  green: "#087d79"
  line: "#e1e8ed"
  canvas: "#f5f7fa"
  surface: "#fff"
  soft: "#edf6f5"
  control-border: "#c9d6de"
  control-hover-border: "#9dbebc"
  primary-hover: "#086763"
  nav-selected-text: "#076864"
  nav-selected-bg: "#e7f3f1"
  neutral-state: "#edf1f5"
  neutral-state-text: "#385269"
  receiving-text: "#09635f"
  receiving-bg: "#e3f4ed"
  attention-text: "#805400"
  attention-bg: "#fff3d6"
  error-text: "#a32932"
  error-bg: "#fff0ef"
  round-bg: "#f6f8fa"
  round-selected-border: "#80b4b0"
  message-bg: "#f3f6f8"
  overlay: "#00f5c4"
  live-overlay-label: "#073b59"
typography:
  display:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "1.9rem"
    fontWeight: 680
    letterSpacing: "-.025em"
  display-mobile:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "1.6rem"
    fontWeight: 680
    letterSpacing: "-.025em"
  title:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "1rem"
    fontWeight: 650
    letterSpacing: "-.01em"
  body:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "16px"
    lineHeight: 1.55
  control:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: ".85rem"
    fontWeight: 600
  metadata:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: ".75rem"
  measure:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "3.3rem"
    fontWeight: 650
    letterSpacing: "-.035em"
    lineHeight: 1.1
  hash:
    fontFamily: "ui-monospace, monospace"
    fontSize: ".7rem"
rounded:
  surface: "18px"
  surface-mobile: "16px"
  control: "12px"
  navigation: "13px"
  compact: "10px"
  badge: "8px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  panel-small: "18px"
  panel: "22px"
  lg: "24px"
  page-vertical: "32px"
  page-horizontal: "36px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "11px 17px"
  button-hover:
    backgroundColor: "{colors.soft}"
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  surface:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.surface}"
  surface-mobile:
    rounded: "{rounded.surface-mobile}"
  nav-selected:
    backgroundColor: "{colors.nav-selected-bg}"
    textColor: "{colors.nav-selected-text}"
    rounded: "{rounded.navigation}"
    padding: "12px 16px"
  badge:
    backgroundColor: "{colors.neutral-state}"
    textColor: "{colors.neutral-state-text}"
    rounded: "{rounded.badge}"
    padding: "6px 10px"
  badge-receiving:
    backgroundColor: "{colors.receiving-bg}"
    textColor: "{colors.receiving-text}"
  badge-attention:
    backgroundColor: "{colors.attention-bg}"
    textColor: "{colors.attention-text}"
  badge-error:
    backgroundColor: "{colors.error-bg}"
    textColor: "{colors.error-text}"
  round-option:
    backgroundColor: "{colors.round-bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "13px"
  round-selected:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.ink}"
  speed-select:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 30px 8px 12px"
---

# Design System: Sonar Vision — painel experimental #73

## Overview

**Creative North Star: "Observação organizada, revisão por rodada"**

Referência visual experimental do painel #73, reformulada conforme a direção de Bryan em 27/10/2026: organização mais clara e formas arredondadas. Substitui a referência da primeira interface. Preserva o logo Sonar Vision, a família azul/verde e fontes do sistema; não estabelece identidade oficial ou institucional.

A estrutura separa navegação, observação ao vivo e revisão histórica. Superfícies brancas sobre fundo claro agrupam imagem, distância e ações; detalhes técnicos permanecem disponíveis em seções recolhidas. POC Fleury e KPMG Agente orientaram apenas estrutura e controles, sem incorporar suas marcas, conteúdo, assets ou dependências.

**Key Characteristics:**
- Navegação persistente entre Ao vivo e Histórico, compactada no celular.
- Superfícies arredondadas, bordas suaves e controles consistentes.
- Imagem em destaque, ToF independente e detalhes técnicos recolhidos.
- Histórico com seleção de rodada, reprodução e download identificados.

## Colors

### Primary

Azul profundo (`ink`) organiza títulos e texto. Verde (`green`) marca ações,
foco, links e controles nativos; `primary-hover` aprofunda a ação principal.

### Secondary

Seleção de navegação combina `nav-selected-text` e `nav-selected-bg`. Recebimento,
atraso/expiração e falha/inválida usam os pares de estado correspondentes.
Caixas usam `overlay`; rótulos têm texto branco sobre azul: `live-overlay-label`
no ao vivo e `ink` no histórico. Cor sempre acompanha descrição textual.

### Neutral

`canvas` envolve a aplicação; `surface` sustenta sidebar, cabeçalho e painéis.
`muted` distingue metadados, `line` separa regiões e `neutral-state` recebe
estados iniciais e a área de imagem. `soft` destaca hover e rodada selecionada;
`round-bg` e `message-bg` diferenciam opções e mensagens sem sombra.

## Typography

Família do sistema compartilhada por corpo, títulos e controles; hashes usam
monoespaçada. Sem fonte externa. Os tokens registram os principais papéis;
textos auxiliares variam entre (.7rem), (.75rem), (.8rem) e (.875rem). Badges
usam (.7rem), reduzidos a (.65rem) no celular. Distância, timecode, recibos e
tabela usam números tabulares. Não se deduziu uma fonte institucional do logo.

## Layout

Sidebar branca fixa por rolagem, com largura de (224px), navegação Ao vivo /
Histórico e nota ao pé. Topbar separada com breadcrumb e conexão. Conteúdo
centralizado com máximo de (1600px), recuos de (32px 36px) e intervalos de
(22–24px). Logo sem transformação, dimensionado a (166px) no desktop.

Ao vivo: imagem ocupa a coluna flexível; ToF e contexto ficam em coluna de
(320px), ampliada para (360px) a partir de (1600px). Histórico: coluna de
(250px) reúne lista de rodadas e ToF registrado ao lado do player flexível;
a tabela expansível ocupa a coluna do player abaixo dele. Imagens preservam
proporção (4:3), com alturas máximas de (520px) ao vivo e (480px) no player.

Até (1180px), sidebar passa a (190px), recuos principais a (26px 24px), coluna
ToF ao vivo a (285px) e coluna de rodadas a (210px). Até (960px), imagem e
sensores deixam o arranjo lateral; histórico empilha lista, player e ToF,
com opções de rodada em faixa horizontal rolável. Até (680px), sidebar vira
cabeçalho compacto com logo de (90px) e dois links; breadcrumb e nota lateral
somem. Painéis e sensores empilham, controles do player quebram em duas linhas,
conteúdo usa (22px 16px) e intervalos de (16px).

## Elevation & Depth

Sem sombras. Fundo claro, superfícies brancas e bordas de (1px) organizam
profundidade. Foco verde de (3px) com afastamento de (4px). Botões, links e
select têm transição de fundo e borda de (140ms ease-out), apenas quando não
há preferência por movimento reduzido. Não há animação de entrada ou fonte
de movimento importada das referências.

## Shapes

Painéis usam raio de superfície no desktop e sua variante móvel. Controles e
janela de imagem compartilham cantos menores; badges são mais compactos.
Navegação arredondada reduz seu raio a (10px) no celular, assim como a janela
de imagem. Ícones são SVGs de traço, com cantos e terminações arredondados.

## Components

### Buttons

Botão e link de download compartilham altura mínima de (44px), borda fina e
raio de controle. Padrão branco; hover suave com borda de interação. Ação de
reprodução e pausa ativa usam verde e texto branco. Desabilitados usam opacidade
(.45). Anterior/próximo são botões de ícone com nome acessível; atualizar lista
é compacto, com mínimo de (40px). Link de download só aparece com rodada válida.

### Chips

Badges arredondados indicam fonte e estado de cada canal/rodada por texto e cor.
Não implicam segurança física nem autenticidade da captura.

### Cards / Containers

Imagem, sensor e contexto usam superfícies independentes. Títulos e subtítulos
formam um cabeçalho compacto; metadados com bordas horizontais mantêm a leitura
vertical. Detalhes da captura, telemetria, rodada e tabela ToF usam `details`
nativo, fechado inicialmente, com `summary` acionável e foco visível.

### Inputs / Fields

Checkbox nativo de (17px) liga sobreposições. Slider nativo escolhe frame;
select de velocidade oferece (0,5×), (1×), (2×), (4×), (8×), com altura mínima
de (44px). Verde é o acento dos controles nativos; controles indisponíveis ficam
desabilitados. Não há campo de texto nesta implementação.

### Navigation

Links com ícone e texto usam `aria-current="page"` para seleção. Item padrão
usa texto secundário, hover usa fundo da aplicação, selecionado usa fundo verde
suave. Links permanecem visíveis no cabeçalho móvel.

### Rodadas, reprodução e dados independentes

Opções de rodada são botões com `aria-pressed`, data, origem, contagens e estado;
a seleção usa fundo suave e borda verde. Player mostra captura original,
barra de posição, timecode, transporte e velocidade. Mensagem explica limites
de reprodução e ausência de interpolação. Seleção vencida ou indisponível
remove identidade anterior e download; estado vazio mantém orientações úteis.

SHA-256 é verificado antes de desenhar o JPEG correspondente. Rótulos compensam
a escala para permanecer em (14px) na exibição, acompanhados de lista HTML
acessível. Falha exclusiva do JPEG ao vivo preserva ToF disponível. No histórico,
ToF anterior ao frame mantém indicação própria de qualidade e defasagem;
inválido ou ausente mostra travessão. Não anunciar cada frame em região viva.

## Do's and Don'ts

### Do:
- Do preservar o logo existente e o caráter experimental desta referência.
- Do usar o verde para interação/seleção e texto explícito para estados.
- Do manter detalhes técnicos acessíveis por expansão, com foco visível.
- Do preservar listas HTML de classes e IDs além das sobreposições no canvas.
- Do limpar identidade, controles e link de download quando a rodada selecionada ficar indisponível.

### Don't:
- Don't importar marca, fontes ou dependências dos projetos de referência.
- Don't apresentar ausência de leitura como zero ou caminho livre.
- Don't associar a distância ToF a uma caixa ou pessoa da imagem.
- Don't apresentar reprodução, fonte simulada ou revisão visual como validação física.

## Implementação da imagem de referência — 27/10/2026

Esta revisão substitui o layout, marca apresentada e movimento anteriores,
conforme a imagem solicitada por Bryan. O logo anterior permanece no arquivo;
a interface volta a usar `logo.jpeg`, conforme solicitado por Bryan, em desktop e mobile.

Branco, bordas `#dce8ef`, azul-petróleo `#123d54` e turquesa `#00afbc`.
Sidebar de 192 px (174 px até 1180 px); conteúdo com recuos de 32×28 px.
Cabeçalho reúne título, conexão e pausa; linha de fonte abaixo, sem breadcrumb
extra no ao vivo. Câmera com mídia em 8:5 e controles/detalhes na base.
ToF: número grande, régua de 0–4.000 mm, qualidade/idade/zona em três colunas
e curva recente preenchida. Faixa de independência abaixo dos dois painéis.

Entre 681–940 px os painéis empilham e o sensor usa duas colunas; até 680 px,
marca horizontal no topo, título com badge, navegação inferior e painéis
empilhados. Verificações incluem 320 e 390 px.

A cena WebP gerada é separada do JPEG da API. Abre automaticamente só
quando fonte e backend são simulados; o aviso identifica a ilustração.
Caixa e ID são exemplos. O controle em Detalhes da captura alterna para o
JPEG verificado. Fonte/backend real inicia no JPEG. O indicador de recebimento
sempre se refere ao canal original, mesmo durante a apresentação.

Gráfico: até 24 leituras/30 s em memória, sem persistência, com quebras em
inválidas/lacunas e reset na troca de sessão. Valor acima da régua permanece
por extenso com aviso; não é interpretado como seguro. Escala e gráfico são
recursos de observação, sem inferência de risco ou vínculo com a pessoa.

Entrada de 250 ms, controles de 150–160 ms e feedback numérico por opacidade
de 200 ms. Sem interpolação de valores/caixas ou animação contínua.
Preferência de movimento reduzido suprime essas animações.


## Refinamento visual — 27/10/2026

Modernização solicitada por Bryan, mantendo `logo.jpeg` e a paleta original.
Este refinamento substitui as medidas de layout da revisão anterior: sidebar
de 212 px (184 px até 1180 px), recuos de 34×32 px e intervalos de 22 px.
Superfícies brancas com raio de 20 px, bordas claras e sombra azul discreta
sobre fundo cinza-azulado. Títulos com tipografia de sistema, números tabulares,
ícones em áreas suaves e dados do sensor agrupados em uma faixa neutra.

Até 980 px os painéis empilham; o sensor se organiza em duas colunas.
Até 680 px, logo original no cabeçalho, cartões de 17 px, sensor vertical
e navegação inferior em uma superfície flutuante com área segura. Controles
mantêm alvos de toque e foco visível. A entrada usa 280 ms e as interações
160 ms, respeitando movimento reduzido. O gráfico ganha linhas de referência
discretas; escala, dados e regras de expiração não mudam.

O CSS foi consolidado em uma única definição dos componentes, removendo
as camadas acumuladas de estilos das revisões anteriores. Sem dependências
novas, alterações na API, gravação, inferência ou significado dos indicadores.
