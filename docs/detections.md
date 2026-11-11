# O que o Sonar Vision reconhece

Lista conferida no vocabulário de `src/sonar_vision/core.py`, na política de
`src/sonar_vision/audio.py` e nos modelos usados na [#52](integrated-service.md).
São capacidades de software experimental, não garantia de reconhecimento em
qualquer situação nem validação de segurança.

## Classes identificadas na resposta dos óculos

| Categoria | Campo da API | Sugestão de áudio atual |
|---|---|---|
| Pessoa | `person` | Pessoa |
| Carro | `car` | Carro |
| Motocicleta | `motorcycle` | Moto |
| Ônibus | `bus` | Ônibus |
| Bicicleta | `bicycle` | Bicicleta |
| Cadeira | `chair` | Cadeira |
| Mesa de jantar | `dining_table` | Mesa |
| Cachorro | `dog` | Cachorro |
| Semáforo | `traffic_light` | Não gera fala nesta política |
| Escada | `stairs` | Escada, Escada de subida ou Escada de descida |

Escadas têm `stair_direction=up`, `down` ou `unknown`. Semântica de subida/
descida vem do especialista; não significa geometria local, degrau seguro ou
orientação validada do usuário. Semáforo identifica o objeto, **não** sua cor,
estado ou autorização para atravessar. Pessoas não são classificadas por idade.

`unknown` é a categoria de saída para classes fora desse vocabulário; não é um
detector genérico de todo obstáculo. Por exemplo, o YOLO pode reconhecer um
monitor como `tv`, mas o adaptador atual o envia como `unknown`. `cat`, `truck`,
`bench` e outras classes também não recebem nomes próprios no contrato atual.
O nome original dessas classes ainda não é preservado no diagnóstico da #52.
Não é necessário retreinar só para alterar esse mapeamento; ampliar o contrato
ou o vocabulário exige tarefa/decisão própria.

## O detector geral e o especialista

- **YOLOv8n COCO:** modelo geral com 80 classes originais. O adaptador normaliza
  essas classes para o vocabulário acima, preservando as detecções; a resposta
  tem no máximo 20 objetos por captura, ordenados pela confiança.
- **R20:** especialista experimental com `stairs_up` e `stairs_down`, usado
  junto ao modelo geral. Não substitui suas 80 classes. Adições de escadas pelo
  especialista podem ter ID nulo; não possuem tracking próprio neste adaptador.
- **ByteTrack:** associa IDs às detecções do caminho geral por sessão. ID
  consistente não comprova acurácia de tracking, distância ou aproximação física.
- **Política de áudio:** optativa, com confiança/cooldowns explícitos. Não fala
  todos os objetos em cada frame; pode se abster por confiança, repetição,
  expiração, orientação ou urgência local simulada.

## O que ainda não está implementado/validado

Não há reconhecimento semântico geral de buracos, meio-fio, portas, fios,
obstáculos na altura da cabeça ou qualquer desnível arbitrário neste conjunto.
Alguns objetos podem aparecer como `unknown`, o que não equivale à classe
específica ou ao perigo físico. Movimento de câmera vestível permanece
`unknown`, sem compensação/IMU validada.

Proximidade, geometria, TTC e alerta tátil são previstos para os sensores e
firmware local. Sua implementação/validação de hardware permanece nas issues
correspondentes; não são resultados do YOLO ou da integração da #52.
