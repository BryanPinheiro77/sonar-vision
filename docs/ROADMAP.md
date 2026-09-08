# Roadmap inicial

O roadmap apresenta dependências técnicas, não uma obrigação de executar todas
as frentes sequencialmente. Visão computacional e simulações podem avançar em
paralelo ao bring-up do hardware.

## Fundação do projeto

- [x] Documentar arquitetura e princípio de segurança.
- [x] Criar issues e GitHub Project.
- [x] Definir licença open source inicial.
- [ ] Definir responsáveis por cada frente.
- [ ] Confirmar componentes e interfaces do primeiro protótipo.

## Visão computacional

- [x] Medir baseline multiclasse do detector no laboratório.
- [ ] Preparar vídeos controlados e respectivos metadados.
- [ ] Integrar ByteTrack e manter IDs entre frames.
- [ ] Medir perdas e trocas de ID.
- [ ] Criar histórico por `track_id`.
- [ ] Estimar direção e trajetória.
- [ ] Diferenciar alvos convergentes de alvos passantes.
- [ ] Definir uma interface de resultados para futura integração.

## Firmware e hardware

- [ ] Configurar PlatformIO após confirmar a placa.
- [ ] Validar ESP32-S3 e PSRAM.
- [ ] Testar separadamente ToF, IMU, câmera, LRA e áudio.
- [ ] Implementar projeção e setores da matriz ToF.
- [ ] Integrar ToF e IMU.
- [ ] Implementar proximidade, aproximação e TTC local.
- [ ] Implementar feedback háptico independente da rede.

## Comunicação e nuvem

- [ ] Definir e versionar o contrato ESP32 ↔ VM.
- [ ] Implementar transporte de frames e estado de risco.
- [ ] Implementar heartbeat, timeout e fallback.
- [ ] Instrumentar latência e descarte de frames.
- [ ] Integrar resultados de visão sem bloquear o caminho local.

## Áudio e experiência

- [ ] Definir vocabulário e prioridades de mensagens.
- [ ] Implementar cooldown e controle de repetição.
- [ ] Integrar saída de áudio sem atrasar a vibração.
- [ ] Planejar avaliação de compreensão e carga cognitiva.

## Validação integrada

- [ ] Medir latência do sensor ao alerta tátil.
- [ ] Medir latência fim a fim com a VM.
- [ ] Testar perda de rede e indisponibilidade da VM.
- [ ] Validar alvos convergentes e passantes.
- [ ] Registrar limitações e condições de cada experimento.
- [ ] Avaliar requisitos éticos antes de testes formais com participantes.

O estado operacional das tarefas deve ser consultado no
[Kanban](https://github.com/users/BryanPinheiro77/projects/3). Este documento
registra apenas os marcos técnicos de alto nível.
