# Roadmap inicial

O roadmap apresenta dependências técnicas, não uma obrigação de executar todas
as frentes sequencialmente. Visão computacional e simulações podem avançar em
paralelo ao bring-up do hardware.

O [escopo da entrega acadêmica](ESCOPO.md) foi aprovado pelo grupo, conforme
confirmação de Bryan na #10. Requisitos planejados não são capacidades já validadas.

## Fundação do projeto

- [x] Documentar arquitetura e princípio de segurança.
- [x] Criar issues e GitHub Project.
- [x] Definir licença open source inicial.
- [ ] Definir responsáveis por cada frente.
- [ ] Confirmar componentes e interfaces do primeiro protótipo.

## Visão computacional

- [x] Medir baseline multiclasse do detector no laboratório.
- [ ] Preparar vídeos controlados e respectivos metadados.
- [x] Integrar ByteTrack no laboratório, com limitações de continuidade (#8).
- [x] Registrar perdas e revisar casos de troca de ID no laboratório (#8).
- [x] Criar histórico por `track_id` no laboratório (#8).
- [ ] Integrar e validar tracking no protótipo real; revisão pontual não
  substitui avaliação completa de identidade.
- [ ] Estimar direção e trajetória.
- [ ] Diferenciar alvos convergentes de alvos passantes.
- [ ] Definir uma interface de resultados para futura integração.

## Firmware e hardware

- [ ] Configurar PlatformIO após confirmar a placa.
- [x] Validar ESP32-S3 e PSRAM em bancada (câmera com buffers/DMA em PSRAM;
  [registro](experiments/bancada-tof-drv-nuvem-2026-11-13.md)).
- [ ] Testar separadamente ToF, IMU, câmera, LRA e áudio. Em 13/11: ToF,
  câmera (bit 5 em aberto) e DRV2605L com motor ERM esquerdo testados em
  bancada; DRV direito, IMU e áudio pendentes.
- [ ] Implementar projeção e setores da matriz ToF.
- [ ] Integrar ToF e IMU.
- [ ] Implementar proximidade, aproximação e TTC local.
- [ ] Implementar feedback háptico independente da rede. Protótipo de bancada
  `firmware/bench/bench_tof_drv` (#86); firmware final e latência pendentes.

## Comunicação e nuvem

- [ ] Definir e versionar o contrato ESP32 ↔ VM.
- [ ] Implementar transporte de frames e estado de risco.
- [ ] Implementar heartbeat, timeout e fallback.
- [ ] Instrumentar latência e descarte de frames. Tempo de envio e aceitação
  medidos na bancada; latência sensor→alerta não medida.
- [ ] Integrar resultados de visão sem bloquear o caminho local. Na bancada, a
  nuvem roda em tarefa separada e o alerta não espera a rede (#86).

## Áudio e experiência

- [ ] Definir vocabulário e prioridades de mensagens.
- [ ] Implementar cooldown e controle de repetição.
- [ ] Integrar saída de áudio sem atrasar a vibração.
- [ ] Planejar avaliação de compreensão e carga cognitiva.

## Validação integrada

- [x] Aprovar escopo da entrega acadêmica (#10).
- [ ] Aprovar parâmetros de avaliação por classe e condição.
- [ ] Avaliar escadas de subida/descida e respostas inconclusivas.
- [ ] Avaliar baixa iluminação e noite com iluminação pública.
- [ ] Demonstrar captura, análise e feedback com os óculos em funcionamento.
- [ ] Medir latência do sensor ao alerta tátil.
- [ ] Medir latência fim a fim com a VM.
- [ ] Testar perda de rede e indisponibilidade da VM.
- [ ] Validar alvos convergentes e passantes.
- [ ] Registrar limitações e condições de cada experimento.
- [ ] Avaliar requisitos éticos antes de testes formais com participantes.

O estado operacional das tarefas deve ser consultado no
[Kanban](https://github.com/users/BryanPinheiro77/projects/3). Este documento
registra apenas os marcos técnicos de alto nível.
