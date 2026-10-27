---
name: "Sonar Vision — painel experimental #73"
description: "Referência visual aprovada para observação remota de imagem e ToF; não é identidade oficial."
colors:
  ink: "#073b59"
  muted: "#456373"
  green: "#087d79"
  line: "#ccd9df"
  background: "#f4f7f7"
  surface: "#ffffff"
  hover: "#e5f1f0"
  neutral-state: "#eaf0f3"
  receiving-text: "#09635f"
  receiving-bg: "#e1f3ed"
  attention-text: "#805400"
  attention-bg: "#fff3d6"
  error-text: "#a32932"
  error-bg: "#fff0ef"
  overlay: "#00f5c4"
typography:
  display:
    fontFamily: "system-ui, sans-serif"
    fontSize: "clamp(2rem, 3vw, 2.5rem)"
    fontWeight: 650
    letterSpacing: "-.025em"
  title:
    fontFamily: "system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 650
  body:
    fontFamily: "system-ui, sans-serif"
    fontSize: "16px"
    lineHeight: 1.55
  label:
    fontFamily: "system-ui, sans-serif"
    fontSize: ".8rem"
  measure:
    fontFamily: "system-ui, sans-serif"
    fontSize: "3.5rem"
    fontWeight: 600
    letterSpacing: "-.03em"
  hash:
    fontFamily: "ui-monospace, monospace"
    fontSize: ".75rem"
rounded:
  badge: "4px"
  button: "6px"
  workspace: "12px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  panel-mobile: "20px"
  panel: "24px"
  section: "32px"
components:
  button:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.button}"
    padding: "12px 16px"
  button-hover:
    backgroundColor: "{colors.hover}"
  button-paused:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
  badge:
    backgroundColor: "{colors.neutral-state}"
    textColor: "{colors.ink}"
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
  workspace:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.workspace}"
---

# Design System: Sonar Vision — painel experimental #73

## Overview

**Creative North Star: "Observação clara de imagem e profundidade"**

Referência visual experimental da #73, aprovada por Bryan em 27/10/2026 e implementada em HTML/CSS/JS no FastAPI existente. Fundo claro, azul e verde aproximam o logo existente, preservado sem transformação em `docs/assets/logo-sonar-vision.jpeg`. Não constitui uma nova identidade oficial ou institucional.

A interface de observação prioriza a imagem e a leitura ToF com estados independentes. Superfícies planas, tipografia do sistema e recibos compactos permitem conferir origem e atualização sem confundir demonstração remota com segurança física.

**Key Characteristics:**
- Fundo claro e superfícies brancas, com azul para informação e verde para interação.
- Imagem em destaque e distância em coluna própria, empilhadas no celular.
- Estados descritos por texto, recibos verificáveis e atualização pausável.

## Colors

### Primary

Azul profundo (`ink`) organiza títulos, texto e controles. Verde (`green`) marca
links, foco e seleção; a variante `hover` destaca o botão sob o ponteiro.

### Secondary

Estados de recebimento usam `receiving-text` e `receiving-bg`; atraso/expiração
usam `attention-text` e `attention-bg`; falha/inválida usam `error-text` e
`error-bg`. A sobreposição `overlay` delimita caixas no JPEG; o rótulo usa fundo
azul e texto branco para legibilidade.

### Neutral

`background` envolve a página; `surface` sustenta cabeçalho e área de dados.
`muted` diferencia metadados; `line` separa blocos; `neutral-state` identifica
estados iniciais e o espaço reservado à imagem.

## Typography

Uma única família do sistema atende títulos, corpo e controles, sem downloads
de fontes. A família monoespaçada aparece apenas no hash. Os tokens acima
registram os papéis principais; metadados também usam (.875rem), e a unidade
de distância usa (1.25rem). Números de distância e recibos usam algarismos
tabulares. Não se inferiu uma fonte institucional a partir do logo.

## Layout

Conteúdo centralizado com largura máxima de (1448px) e recuo de (32px 24px).
Área branca dividida em duas colunas (2fr / 1fr), com mínimo de (310px) para
ToF; cada seção tem recuo de (24px). A imagem ocupa janela (4:3) sem distorção.
Em largura até (800px), as colunas empilham, as seções usam (20px), o conteúdo
usa (24px 16px) e o logo passa de (190px) a (144px). Cabeçalho e recibos permitem
quebra de texto. Tempos independentes têm medida máxima de (75ch).

## Elevation & Depth

Não há sombras. Fundo, superfícies e bordas finas organizam a profundidade.
O foco usa contorno verde de (3px), afastado (4px). Só o botão tem transição
de fundo (120ms ease-out), quando não há preferência por movimento reduzido.

## Shapes

Contêiner principal suavemente arredondado; botão e badge usam cantos menores,
conforme os tokens. Bordas de (1px) separam os canais e as linhas dos recibos.

## Components

### Buttons

Controle branco com borda em texto secundário, altura mínima de (44px), fundo
suave no hover e foco visível. Pausa usa `aria-pressed`, fundo azul e texto branco.
A ação suspende consultas; dados existentes continuam envelhecendo.

### Chips

Badges compactos exibem o estado por texto e cor, separadamente para imagem e
ToF. O indicador de fonte explicita simulação sem confundir fonte e backend.

### Cards / Containers

Uma superfície principal agrupa canais independentes. Divisória vertical vira
horizontal no celular. Recibos usam listas de definições com texto quebrável;
o hash fica em fonte monoespaçada.

### Inputs / Fields

Checkbox nativo de (18px), verde de interação e rótulo clicável controla as
caixas. Não existe campo de texto nem navegação por abas nesta implementação.

### Imagem, previsões e distância

Só desenhar previsões após verificar o SHA-256 do JPEG correspondente; apagar
caixas antigas ao trocar a imagem. Rótulos no canvas compensam a escala de
exibição, mantendo fonte de (14px) na largura observada. Uma lista HTML com
nome acessível oferece classes e IDs fora do canvas. A distância usa medida
grande com unidade separada e explicita que não está associada às caixas.
Falha somente no JPEG preserva a leitura ToF disponível. Não anunciar cada
frame em região viva; o status de conexão comunica mudanças de estado.

## Do's and Don'ts

### Do:
- **Do** preservar o logo existente e o caráter experimental da referência.
- **Do** acompanhar cores de estado com texto e manter foco visível.
- **Do** manter imagem e ToF com estados próprios, inclusive em falha exclusiva do JPEG.
- **Do** manter classes e IDs também na lista HTML acessível, além do canvas.

### Don't:
- **Don't** apresentar ausência de leitura como zero ou caminho livre.
- **Don't** associar a distância ToF a uma caixa ou pessoa da imagem.
- **Don't** apresentar movimento aparente ou demonstração simulada como validação física.
- **Don't** transformar esta aproximação visual na identidade oficial do projeto.
