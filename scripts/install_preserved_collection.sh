#!/bin/sh
# #73: apply explicit private policy on the retained #23 deployment.
set -eu
cd "$HOME/sonar23"
sudo /usr/local/sbin/sonar23-expiry-check
sudo install -m 0755 source/scripts/prepare_preserved_collection.py /usr/local/sbin/sonar23-prepare-collection.py
sudo python3 - <<'PY'
import importlib.util,json,os
from pathlib import Path
import subprocess
base=Path("/home/ubuntu/sonar23")
spec=importlib.util.spec_from_file_location("collection_setup","/usr/local/sbin/sonar23-prepare-collection.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
approved=module.validate_policy(json.loads((base/"private/collection-policy-approved.json").read_text()))
policy=base/"private/collection-policy.json"
if not policy.exists():
    policy.write_text(json.dumps(approved)+"\n")
policy.chmod(0o600)
args=["docker","compose","--env-file",".env","-p","sonar23-bancada20261104"]
for name in module.FILES[:-1]:
    args+=["-f",name]
cfg=json.loads(subprocess.check_output([*args,"config","--format","json"],cwd=base/"source"))
uid,gid=map(int,cfg["services"]["api"]["user"].split(":"))
for name in ("collection-config","collection-rounds"):
    path=base/"private"/name
    path.mkdir(exist_ok=True);os.chown(path,uid,gid);path.chmod(0o700)
env=base/"source/.env"
backup=base/"private/collection-env-before"
if not backup.exists():
    backup.write_bytes(env.read_bytes());backup.chmod(0o600)
text=module.set_environment(env.read_text(),"SONAR_HOST_COLLECTION_DIR","../private/collection-rounds")
text=module.set_environment(text,"SONAR_HOST_COLLECTION_CONFIG_DIR","../private/collection-config")
env.write_text(text);env.chmod(0o600)
PY
sudo mkdir -p /etc/systemd/system/sonar23-application.service.d
sudo tee /etc/systemd/system/sonar23-application.service.d/collection.conf >/dev/null <<'UNIT'
[Service]
ExecStartPre=/usr/bin/python3 /usr/local/sbin/sonar23-prepare-collection.py
ExecStart=
ExecStart=/usr/bin/docker compose --env-file .env -p sonar23-bancada20261104 -f compose.aws.yaml -f compose.aws.parallel.yaml -f compose.aws.audio.yaml -f compose.evaluation.yaml -f compose.demo.yaml -f compose.domain.yaml -f compose.collection.yaml up -d --wait --wait-timeout 90
UNIT
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/sonar23-application.service
sudo python3 /usr/local/sbin/sonar23-prepare-collection.py
sudo systemctl restart sonar23-application.service
sudo /usr/local/sbin/sonar23-expiry-check
