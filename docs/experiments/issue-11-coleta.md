# Preparação da avaliação independente de tracking — #11

Data: 2026-10-13. Responsável pela análise: Bryan.
Status: roteiro proposto; nenhum vídeo novo coletado ou aceite de qualidade realizado.

Referências: [issue #11](https://github.com/BryanPinheiro77/sonar-vision/issues/11),
[trajetória](../trajectory.md), [protocolo #7](protocolo-visual.md),
[avaliação disponível](../evaluation.md) e [evidências anteriores](issue-11.md).

## Objetivo e separação das etapas

Avaliar detecção, continuidade de identidade e movimento aparente com versões
congeladas, antes de decidir sobre novo treino. Não exige ESP nem VM:
o primeiro ensaio é offline no computador. Não mede risco físico, distância,
TTC, captura do ESP ou latência da rede. A vibração local permanece independente.

Os dois vídeos de cadeira/mesa, gravados por Bryan em outros móveis/locais,
continuam destinados à avaliação de detecção. Não presumir câmera fixa,
identidades anotadas ou movimento de referência a partir deles. Uma cadeira
parada filmada enquanto o operador anda não é alvo em aproximação física.

## Roteiro de piloto proposto

Uma pessoa andando é um alvo possível para os cenários de movimento. Usar
integrantes adultos autorizados, após os procedimentos de consentimento,
supervisão e revisão ética previstos na #7. Evitar terceiros, nomes e rostos
quando possível. Não realizar ensaio de navegação ou trânsito com o protótipo.

Proposta exploratória: duas tomadas de 8–12 segundos por linha abaixo,
12 tomadas no total, em boa iluminação. Esses números organizam um piloto;
não são amostra mínima ou limiar aprovado para avaliação final. Repetições na
mesma sessão não comprovam independência. Baixa luz e outras classes ficam
para a matriz de aplicabilidade da #7.

| Cena | Gravação | Referência a revisar |
|---|---|---|
| Estática | Câmera apoiada, alvo parado | Estabilidade aparente após histórico suficiente |
| Aproximação/afastamento | Câmera apoiada; alvo anda em direção à câmera e volta, sem contato | Marcar início, inversão e fim; analisar os dois segmentos |
| Cruzamento | Câmera apoiada; alvo passa esquerda→direita e retorna | Sentido lateral na imagem, sem inferir caminhada do usuário |
| Oclusão | Alvo passa atrás de anteparo e reaparece | Identidade manual, visibilidade e perdas; não exigir ID preservado cegamente |
| Dois alvos | Câmera apoiada; dois alvos cruzam | Identidades separadas, possíveis trocas e ambiguidades |
| Câmera móvel | Alvo parado; câmera gira e depois se desloca | Controle de câmera: movement deve permanecer unknown no caminho atual |

Câmera fixa significa sem deslocamento, giro ou zoom durante o segmento.
Registrar orientação e espelhamento; não inverter esquerda/direita sem registro.
Separar cada movimento em intervalos anotados, inclusive transições ambíguas.
Não encenar movimento da câmera e rotulá-lo como aproximação física do alvo.

## Congelamento antes de abrir o teste

1. Registrar fonte, permissão, metadados e grupo de origem conforme a #7.
   Guardar originais e referências pessoais somente no armazenamento privado.
2. Separar exploration/tuning/test por tomada e fonte; recortes da mesma tomada
   ficam juntos. Se o piloto orientar ajustes, ele não será teste independente.
3. Registrar commit, hashes de pesos, confiança, tamanho de entrada, tracker,
   parâmetros completos de trajetória, versão da anotação e regra de amostragem.
4. Usar YOLO geral e r21 congelados, r20 apenas para rollback. Não trocar pesos
   ou reajustar limiares depois de observar resultados e manter o rótulo test.
5. Para comparar o caminho AWS já escolhido, preservar max-edge 640/JPEG95 e
   registrar a transformação. O replay offline não reproduz a rede nem prova
   que o ESP entrega a cadência. Avaliar também a origem, em execução separada.
6. Usar timestamps originais. Para FPS variável, extrair tempos de apresentação
   antes de avaliação quantitativa; não substituir por índice/FPS médio.

## Anotação e revisão

Anotar caixas na captura original, classe, identidade opaca local, visibilidade,
intervalos de movimento aparente e contexto de câmera. Outro integrante revisa
sem aceitar a saída do modelo como verdade. Registrar desacordos/ambiguidade.
Os rótulos de movimento são approaching/receding/stable/crossing/unknown;
esquerda→direita e direita→esquerda são atributos separados do crossing.

Relatar perdas de detecção, IDs não atribuídos, trocas, fragmentações, resets,
erros de movimento e abstenções com denominadores e regras explícitos. Separar
início sem histórico suficiente, oclusão, gaps e câmera móvel. Não excluir erros
ou unknown para aumentar a taxa de acerto. Não chamar contagem de IDs de pessoas.

A ferramenta da #33 já calcula detecção e diagnósticos de identidade, mas seu
snapshot v1 não contém referência/predição de movimento da #11. O preview produz
contagens agregadas, insuficientes para matriz de movimento por segmento.
Existe agora [adapter e avaliação pareada offline](../motion-evaluation.md),
com entrada local adicional e referências humanas. O [replay local](../motion-replay.md) conecta vídeo e produtor real a esses
adapters; ainda faltam anotações independentes e execução real. O journal não
é convertido automaticamente, e a API permanece igual.

## O que já pode executar

Na raiz do checkout, para verificar o estimador com dados sintéticos:

```sh
PYTHONPATH=src python3 -m unittest tests.test_trajectory -v
PYTHONPATH=src python3 -m sonar_vision.evaluate_trajectory --output results/issue-11/synthetic-01.json
```

Escolher nome novo a cada execução: o avaliador não sobrescreve. O controle
negativo de câmera incorretamente declarada fixed deve continuar revelando a
falha conhecida; não ajustar o estimador para esconder esse caso. Para preview
real autorizado, seguir os comandos existentes em [trajetória](../trajectory.md).
Não ativar assume-fixed-camera em vídeo andando.

## Pendências para concluir

- Aprovação da matriz, amostras e critérios finais da #7 antes do teste final.
- Vídeos e anotações independentes com origem/revisão documentadas.
- Usar o replay com vídeo/anotações independentes para comparar movimentos e
  segmentos; revisar os erros de ID. O produtor offline e o avaliador existem.
- Revisão visual humana e relatório agregado, sem mídias/pesos privados.
- Câmera móvel/IMU e captura ESP continuam capacidades não validadas.

Não encerrar #11 com o roteiro ou com os testes sintéticos. Não há nova
tecnologia, infraestrutura, treinamento, pinos ou alteração de API nesta entrega.

## Verificação da preparação — 2026-10-13

- 15 testes de trajetória passaram, sem skips nesta execução.
- Fixture sintética: oito concordâncias e uma divergência conhecida no controle
  de zoom com câmera incorretamente declarada fixed. Não é acurácia real.
- check_docs: 89 arquivos Markdown, zero problemas.
- Nenhuma mídia coletada/enviada, peso alterado ou VM criada.
