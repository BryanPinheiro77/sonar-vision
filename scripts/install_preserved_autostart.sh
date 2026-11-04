#!/bin/sh
# #23 preserved deployment only; requires an approved private initial quota.
set -eu
cd "$HOME/sonar23"
sudo /usr/local/sbin/sonar23-expiry-check
sudo mkdir -p /var/lib/sonar23/auto-boot-backup
sudo cp /etc/systemd/system/sonar23-expiry.timer /var/lib/sonar23/auto-boot-backup/
sudo install -m 0755 source/scripts/aws_preserved_boot.py /usr/local/sbin/sonar23-auto-window.py
if ! sudo test -f /var/lib/sonar23/auto-start.json; then
  sudo install -m 0600 private/auto-start-approved.json /var/lib/sonar23/auto-start.json
fi
sudo tee /etc/systemd/system/sonar23-auto-window.service >/dev/null <<'UNIT'
[Unit]
Description=Prepare approved runtime window on EC2 start
Wants=network-online.target
After=network-online.target
Before=docker.service
OnFailure=sonar23-expiry.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/sbin/sonar23-auto-window.py
RemainAfterExit=yes
TimeoutStartSec=30
[Install]
WantedBy=multi-user.target
UNIT
sudo mkdir -p /etc/systemd/system/sonar23-expiry.timer.d /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/sonar23-expiry.timer.d/auto-window.conf >/dev/null <<'UNIT'
[Unit]
Requires=sonar23-auto-window.service
After=sonar23-auto-window.service
UNIT
sudo tee /etc/systemd/system/docker.service.d/sonar23-autostart.conf >/dev/null <<'UNIT'
[Unit]
Requires=sonar23-auto-window.service sonar23-expiry.timer
After=sonar23-auto-window.service sonar23-expiry.timer
UNIT
sudo tee /etc/systemd/system/sonar23-application.service >/dev/null <<'UNIT'
[Unit]
Description=Start the preserved Sonar Vision application
Requires=docker.service
After=docker.service
OnFailure=sonar23-expiry.service
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/sonar23/source
ExecStart=/usr/bin/docker compose --env-file .env -p sonar23-bancada20261104 -f compose.aws.yaml -f compose.aws.parallel.yaml -f compose.aws.audio.yaml -f compose.evaluation.yaml -f compose.demo.yaml -f compose.domain.yaml up -d --wait --wait-timeout 90
TimeoutStartSec=120
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/sonar23-auto-window.service /etc/systemd/system/sonar23-application.service /etc/systemd/system/sonar23-expiry.timer
sudo systemctl enable --now sonar23-auto-window.service
sudo systemctl enable --now sonar23-application.service
sudo /usr/local/sbin/sonar23-expiry-check
systemctl is-active sonar23-auto-window.service sonar23-application.service sonar23-expiry.timer
sudo cat /var/lib/sonar23/auto-start.json
