# Publicação de versões e modelos

O projeto ainda não tem uma versão executável integrada. O CI da #38 testa
PRs e commits na `main`. Para uma versão do **software**, o grupo escolhe um
marco e cria uma tag `vX.Y.Z` ou `vX.Y.Z-sufixo` em um commit já integrado à
`main`; o GitHub Actions repete os testes e cria a Release com notas geradas
automaticamente. **Um merge de PR sozinho não cria release.**

Pesos treinados ficam fora do Git e são publicados manualmente como assets de
uma pré-release própria. Uma release de **modelo experimental** não aprova o
uso do modelo como alerta de segurança nem conclui a avaliação da #16/#7.

## Modelo de escadas v3

- Tag: `model-stairs-v3-preview` (pré-release).
- Arquivo: `stairs-up-down-v3.pt` (Ultralytics YOLOv8n, classes
  `stairs_up`/`stairs_down`, 5,9 MiB).
- SHA-256 do arquivo público:
  `8949d163cab5bfe429a5b4c5d68f683d24a8291a468591f6f719488144d8fec4`.
- Origem: ajuste local iniciado com peso YOLOv8n/Open Images V7 da
  [Ultralytics](https://docs.ultralytics.com/datasets/detect/open-images-v7/);
  etapas e limites do treino estão no [experimento da #16](experiments/issue-16.md).
- Licença do peso derivado: AGPL-3.0, preservando a licença e a atribuição da
  [Ultralytics](https://docs.ultralytics.com/help/contributing/). As fotos de
  treino não são publicadas nem recebem essa licença por consequência.

O arquivo publicado foi gerado do checkpoint v3 local com
`scripts/issue16_prepare_release_weight.py`. A preparação removeu dos
metadados caminhos absolutos do Mac; **não alterou os parâmetros aprendidos**.
As saídas foram idênticas nas quatro cenas locais conferidas (subida, descida e
negativa). O hash do checkpoint bruto e os resultados do piloto continuam no
[relatório da #16](experiments/issue-16.md). Os metadados restantes ainda
dependem do formato `.pt` da Ultralytics; carregue somente arquivos obtidos
da release oficial do projeto e verificados pelo hash.

O peso contém só as duas classes de sentido. Para manter as demais classes,
instale `.[vision]` e configure os dois pesos conforme o
[guia de visão](vision.md). O script
`python3 scripts/download_vision_models.py` baixa o peso experimental para
`models/stairs-up-down-v3.pt` e o detector geral oficial
`yolov8n.pt` da [Ultralytics](https://github.com/ultralytics/assets/releases/tag/v8.4.0)
para `models/yolov8n.pt`, verificando ambos os SHA-256. O peso geral tem hash
`f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.
É necessário acesso à internet apenas para baixar os arquivos; a inferência
local da VM não faz downloads. O alerta tátil do ESP32-S3 permanece independente
da VM, da câmera e desses modelos.

## Procedimento para as próximas releases

1. Definir o escopo, a pessoa responsável, a tag e se a entrega é experimental
   ou estável. Código só recebe release após revisão do PR e verificações
   aplicáveis; modelos podem ter uma pré-release própria, sem fechar a issue de
   avaliação. A automação de versão do software está na
   [workflow de release](../.github/workflows/release.yml).
2. Congelar o artefato e registrar origem, licença, classes, peso base, versão
   do Ultralytics, comando de treino, avaliação conhecida e limitações. Não
   anexar fotos, datasets brutos ou dados pessoais.
3. Calcular SHA-256 do arquivo final e conferir que o nome, a tag, o hash e as
   instruções de obtenção coincidem. Quem publica a release deve testar o
   download e o hash em uma pasta nova.
4. Para **software**, após o merge, criar e enviar uma tag `v...` no commit da
   `main`. O workflow verifica a origem da tag, instala `.[vision]`, executa os
   testes e cria a Release. Tags com sufixo, como `v0.1.0-alpha.1`, viram
   pré-releases. Se os testes falharem, não há publicação. Para **modelos**,
   criar uma pré-release `model-...` e anexar o `.pt` como asset, com notas que
   apontem o PR, a issue, a licença e as limitações. O workflow de software
   não age sobre tags `model-...`.
5. Atualizar os links no README/guia e o `CHANGELOG.md` quando houver nova
   versão de código. Manter as versões antigas identificáveis para reproduzir
   resultados anteriores.

Para publicar uma versão de software, depois de revisar o código na `main`:

```sh
git fetch origin main
git tag -a v0.1.0-alpha.1 origin/main -m "Sonar Vision v0.1.0-alpha.1"
git push origin v0.1.0-alpha.1
```

O exemplo mostra a forma da tag; cada release precisa de uma versão nova. As
releases do software seguem as tags `v...` previstas no
[`CHANGELOG.md`](../CHANGELOG.md). Os artefatos de modelo usam tags `model-...`;
uma tag de modelo não indica que todo o sistema vestível esteja pronto. Não há
pipeline de deploy neste estágio. O workflow gera notas a partir dos commits;
o responsável deve conferir e complementar manualmente as limitações antes de
divulgar o marco como pronto para uso.
