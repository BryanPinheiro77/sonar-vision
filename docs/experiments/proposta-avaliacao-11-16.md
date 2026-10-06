# Próxima avaliação de trajetória e escadas — #11/#16/#7

Data: 2026-10-06. Proposta de execução para revisão do grupo. Os PRs #36/#37
incorporaram as implementações experimentais, mas o merge não aprovou metas,
amostra, dados ou segurança física. Bryan mantém responsabilidade pela visão;
Matheus coordena o protocolo comum da [#7](protocolo-visual.md).

## Trajetória — #11

Proponho um primeiro lote exploratório de oito vídeos de 10–15 segundos:
alvo estático, aproximação, afastamento, cruzamento nos dois sentidos,
oclusão/reentrada, dois alvos e câmera móvel diante de um objeto parado.
Câmera fixa é declaração controlada, não leitura da IMU. O último vídeo deve
rodar com contexto desconhecido; `unknown` nesse controle evita afirmar
movimento do alvo devido ao movimento da câmera.

As referências precisam indicar identidade local, caixas e intervalos de
movimento, perdas/oclusões e visibilidade, revisados por outra pessoa.
Registrar tempo de confirmação, erros e inconclusivos; não contar `unknown`
como acerto de aproximação/cruzamento. Cruzamento na imagem não demonstra
cruzamento da caminhada. O [viewer](../trajectory.md) e a avaliação sintética
já existem, mas esta última não calcula acurácia de um lote real anotado.

O lote exploratório serve para conferir o funcionamento e registrar falhas.
Se usado para ajustar parâmetros, não serve como teste independente final.
O grupo ainda precisa congelar tamanho da amostra final, condições de luz,
regras de anotação e metas quantitativas. Não afirmar validação da #11 apenas
porque oito arquivos foram processados.

## Escadas — #16

Proponho reaproveitar o desenho de **12 vídeos de 15 segundos**: quatro up,
quatro down e quatro negativos. Subida/descida do mesmo local pertencem ao
mesmo grupo de origem. Distribuir boa luz, baixa luz e noite iluminada sem
inventar medidas de lux ou distância; anotar como desconhecidas as não medidas.
Incluir trechos de câmera parada e vista oblíqua/móvel, permanecendo em posição
protegida; testes com participantes dependem de consentimento, supervisão e
avaliação das exigências éticas institucionais.

Antes de ver previsões, anotar frames aos 2, 6 e 10 segundos: caixa da escada
e sentido up/down, ou ausência de escada no negativo. Segunda pessoa revisa
as referências e resolve ambiguidades sem usar a previsão como verdade.
Congelar pesos, hashes, confiança, tamanho de inferência e regra de associação.
IoU 0.5 e maioria de dois dos três frames são propostas de avaliação, não
alterações dos limiares locais de risco.

Metas propostas para o lote acadêmico: pelo menos três dos quatro clipes
corretos em cada sentido, nenhuma inversão confirmada e nenhum falso alerta
nos quatro negativos. Reportar também cada frame, perdas e abstenções; nenhuma
abstenção conta como acerto. Poucos clipes sem erros não estimam confiabilidade
operacional. O grupo deve aprovar essas metas antes de abrir o teste final.

## Artefatos necessários antes da avaliação final

- Manifesto com hashes, origem/permissão, grupos de locais, iluminação,
  movimento, distâncias medidas ou lacunas e revisão ética aplicável.
- Referências humanas revisadas e congeladas antes das previsões.
- Registro dos arquivos já vistos/usados para treino, ajuste ou seleção de
  modelo. Eles permanecem desenvolvimento/exploração, mesmo com hash novo
  após recorte ou transcodificação.
- Perfil e metas aprovados na parte aplicável da #7. Seu fechamento inteiro
  não é necessário para executar uma avaliação específica aprovada.
- Vídeos, anotações detalhadas e termos em armazenamento privado, fora do Git.
  O repositório recebe procedimento e síntese revisada, sem mídia ou identidades.

Há trabalho exploratório local anterior de Bryan. Esta proposta não o
reclassifica como independente nem inclui alterações privadas dos worktrees
originais. As lacunas de coleta, referências e aprovação permanecem explícitas.
