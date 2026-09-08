# ADR 0002: adotar AGPL-3.0-only para o software

- Status: aceita
- Data: 2026-09-07
- Responsável pela decisão: grupo Sonar Vision

## Contexto

O Sonar Vision será desenvolvido publicamente e pretende receber contribuições
depois do projeto acadêmico. A baseline de visão computacional prevê o uso do
Ultralytics YOLO, disponibilizado em modalidade open source sob AGPL-3.0 ou sob
licença comercial.

O repositório precisa declarar claramente os direitos de uso, modificação e
distribuição e manter compatibilidade com a dependência planejada.

## Decisão

O código e a documentação produzidos para este repositório serão licenciados
sob `AGPL-3.0-only`.

Contribuições aceitas serão distribuídas sob essa mesma licença. Dependências
de terceiros continuarão sujeitas às licenças de seus respectivos autores.

Datasets, vídeos, pesos de modelos e artefatos futuros de hardware não recebem
automaticamente esta licença; cada categoria deverá ter origem, consentimento e
licenciamento documentados antes de ser publicada.

## Alternativas consideradas

- **MIT:** simples e permissiva, mas sem o mesmo compromisso de disponibilizar
  publicamente melhorias e potencialmente incompatível com a forma planejada de
  integrar o Ultralytics YOLO.
- **Apache-2.0:** permissiva e com concessão explícita de patentes, mas apresenta
  a mesma preocupação de compatibilidade para uma obra derivada da baseline
  AGPL.
- **Licença comercial do Ultralytics:** permitiria outra estratégia de
  licenciamento, porém adicionaria custo e não atende à prioridade acadêmica e
  open source atual.

## Consequências

- Distribuições e serviços derivados devem observar as obrigações da AGPL-3.0.
- O texto integral da licença deve permanecer no repositório.
- Novas dependências devem passar por verificação de compatibilidade de licença.
- Uma mudança futura de licença exigirá concordância dos titulares dos direitos
  das contribuições afetadas.
- Projetos físicos poderão adotar posteriormente uma licença de hardware aberto
  por meio de uma nova decisão.
