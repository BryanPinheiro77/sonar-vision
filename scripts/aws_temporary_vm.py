"""#23 owned temporary EC2 lifecycle via the existing AWS CLI; no new dependency.

plan is read-only. launch creates one approved CPU4 VM with a persistent absolute
expiry; destroy checks account and all ownership tags before any deletion.
State and keys must remain in a private directory outside Git. See aws-operation.md.
"""

import argparse
import hashlib
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from uuid import uuid4

PROJECT = "sonar-vision"
EXPERIMENT = "issue-23"
CANONICAL = "099720109477"


class AwsError(RuntimeError):
    pass


def validate(config):
    for key, pattern in [
        ("account_id", r"[0-9]{12}"),
        ("iam_user", r"[A-Za-z0-9+=,.@_-]+"),
        ("profile", r"[A-Za-z0-9_-]+"),
        ("ami_id", r"ami-[0-9a-f]+"),
        ("vpc_id", r"vpc-[0-9a-f]+"),
        ("subnet_id", r"subnet-[0-9a-f]+"),
    ]:
        if not isinstance(config.get(key), str) or not re.fullmatch(
            pattern, config[key]
        ):
            raise ValueError(f"invalid {key}")
    if (
        config.get("region") != "sa-east-1"
        or config.get("instance_type") != "c7i-flex.xlarge"
    ):
        raise ValueError("only the approved CPU4/Sao Paulo profile is supported")
    network = ipaddress.ip_network(config["operator_cidr"], strict=True)
    if (
        network.version != 4
        or network.prefixlen != 32
        or not network.network_address.is_global
    ):
        raise ValueError("operator ingress must be a public IPv4 /32")
    minutes = config.get("maximum_minutes", 100)
    if type(minutes) is not int or not 1 <= minutes <= 100:
        raise ValueError("absolute expiry must be 1..100 minutes")
    for key in [
        "previous_instance_hours",
        "previous_consumption_estimate_usd",
        "compute_usd_per_hour",
        "gp3_usd_per_gb_month",
    ]:
        if (
            type(config.get(key)) not in (int, float)
            or not math.isfinite(config[key])
            or config[key] < 0
        ):
            raise ValueError(f"nonnegative finite {key} required")
    if config["compute_usd_per_hour"] == 0 or config["gp3_usd_per_gb_month"] == 0:
        raise ValueError(
            "positive catalog prices required; credits do not zero consumption"
        )
    # Reserve two hours for any launch/cleanup delays; one GB egress charged without
    # assuming remaining shared allowance. This is an estimate, not a billing cap.
    reserve = (
        2
        * (
            config["compute_usd_per_hour"]
            + 0.005
            + 20 * config["gp3_usd_per_gb_month"] / 720
        )
        + 0.15
    )
    if (
        config["previous_instance_hours"] + 2 > 8
        or config["previous_consumption_estimate_usd"] + reserve > 15
    ):
        raise ValueError("approved aggregate hours/consumption would be exceeded")
    return {
        "reserved_instance_hours": 2,
        "reserved_catalog_consumption_before_tax_usd": reserve,
    }


def tags(run):
    return [
        {"Key": key, "Value": value}
        for key, value in [
            ("Project", PROJECT),
            ("Experiment", EXPERIMENT),
            ("RunId", run),
        ]
    ]


def owned(resource, run):
    actual = {item["Key"]: item["Value"] for item in resource.get("Tags", [])}
    return all(actual.get(item["Key"]) == item["Value"] for item in tags(run))


def filters(run):
    return [
        {"Name": "tag:" + item["Key"], "Values": [item["Value"]]} for item in tags(run)
    ]


def check_ingress(group, cidr):
    actual = set()
    for rule in group.get("IpPermissions", []):
        if (
            rule.get("Ipv6Ranges")
            or rule.get("UserIdGroupPairs")
            or rule.get("PrefixListIds")
        ):
            raise ValueError("unexpected ingress source")
        for source in rule.get("IpRanges", []):
            actual.add(
                (
                    rule.get("IpProtocol"),
                    rule.get("FromPort"),
                    rule.get("ToPort"),
                    source["CidrIp"],
                )
            )
    if actual != {("tcp", 22, 22, cidr), ("tcp", 8443, 8443, cidr)}:
        raise ValueError("ingress must match exactly operator /32 and ports22/8443")


def ledger_deadline(state, config):
    created = datetime.fromisoformat(state["created_at_utc"])
    deadline = datetime.fromisoformat(state["deadline_utc"])
    if created.tzinfo is None or deadline.tzinfo is None:
        raise ValueError("UTC-aware ledger dates required")
    lifetime = (deadline - created).total_seconds()
    if not 0 < lifetime <= config.get("maximum_minutes", 100) * 60:
        raise ValueError("ledger expiry exceeds approved lifetime")
    if created > datetime.now(timezone.utc) + timedelta(seconds=1):
        raise ValueError("ledger creation timestamp is in the future")
    return deadline


def bootstrap(deadline):
    """Absolute deadline survives boot; Docker refuses to start after expiration."""
    epoch = int(deadline.timestamp())
    calendar = deadline.strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""#!/bin/bash
set -eu
install -d -m 700 /var/lib/sonar23
printf '%s\\n' '{epoch}' > /var/lib/sonar23/deadline
cat > /usr/local/sbin/sonar23-expiry-check <<'GUARD'
#!/bin/sh
set -eu
deadline=$(cat /var/lib/sonar23/deadline) || exit 1
case "$deadline" in ''|*[!0-9]*) exit 1 ;; esac
now=$(date +%s) || exit 1
case "$now" in ''|*[!0-9]*) exit 1 ;; esac
if [ "$now" -lt "$deadline" ]; then
    exit 0
fi
systemctl --no-block poweroff
exit 1
GUARD
chmod 755 /usr/local/sbin/sonar23-expiry-check
cat > /etc/systemd/system/sonar23-expiry.service <<'SERVICE'
[Unit]
Description=Terminate owned temporary Sonar Vision VM
[Service]
Type=oneshot
ExecStart=/sbin/shutdown -h now
SERVICE
cat > /etc/systemd/system/sonar23-expiry.timer <<'TIMER'
[Unit]
Description=Absolute Sonar Vision expiry, survives reboot
[Timer]
OnCalendar={calendar}
Persistent=true
AccuracySec=1s
Unit=sonar23-expiry.service
[Install]
WantedBy=timers.target
TIMER
systemctl daemon-reload
systemctl enable --now sonar23-expiry.timer
/usr/local/sbin/sonar23-expiry-check
export DEBIAN_FRONTEND=noninteractive
apt-get update > /var/log/sonar23-bootstrap.log 2>&1
apt-get install -y docker.io docker-compose-v2 >> /var/log/sonar23-bootstrap.log 2>&1
install -d /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/sonar23-expiry.conf <<'DOCKER'
[Service]
ExecStartPre=/usr/local/sbin/sonar23-expiry-check
DOCKER
systemctl daemon-reload
systemctl restart docker
usermod -aG docker ubuntu
install -d -o ubuntu -g ubuntu -m 700 /home/ubuntu/sonar23
printf 'SONAR23_HOSTKEY_BEGIN\\n' > /dev/console
cat /etc/ssh/ssh_host_ed25519_key.pub > /dev/console
printf 'SONAR23_HOSTKEY_END\\n' > /dev/console
touch /var/lib/sonar23/ready
"""


def instance_request(config, run, group, key, deadline):
    validate(config)
    return {
        "ImageId": config["ami_id"],
        "InstanceType": config["instance_type"],
        "MinCount": 1,
        "MaxCount": 1,
        "KeyName": key,
        "ClientToken": run,
        "NetworkInterfaces": [
            {
                "DeviceIndex": 0,
                "SubnetId": config["subnet_id"],
                "Groups": [group],
                "AssociatePublicIpAddress": True,
                "DeleteOnTermination": True,
            }
        ],
        "MetadataOptions": {
            "HttpTokens": "required",
            "HttpEndpoint": "enabled",
            "HttpPutResponseHopLimit": 1,
        },
        "InstanceInitiatedShutdownBehavior": "terminate",
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "VolumeSize": 20,
                    "VolumeType": "gp3",
                    "Encrypted": True,
                    "DeleteOnTermination": True,
                },
            }
        ],
        "TagSpecifications": [
            {"ResourceType": kind, "Tags": tags(run)}
            for kind in ["instance", "volume", "network-interface"]
        ],
        "UserData": base64.b64encode(bootstrap(deadline).encode()).decode(),
    }


class Aws:
    def __init__(self, config):
        self.config = config

    def call(self, action, params=None, service="ec2"):
        # Parameters never contain private SSH/TLS keys or device credentials.
        with tempfile.TemporaryDirectory(prefix="sonar23-request-") as temp:
            path = Path(temp) / "request.json"
            path.write_text(json.dumps(params or {}))
            path.chmod(0o600)
            result = subprocess.run(
                [
                    "aws",
                    service,
                    action,
                    "--profile",
                    self.config["profile"],
                    "--region",
                    self.config["region"],
                    "--output",
                    "json",
                    "--no-cli-pager",
                    "--cli-binary-format",
                    "base64",
                    "--cli-connect-timeout",
                    "5",
                    "--cli-read-timeout",
                    "20",
                    "--cli-input-json",
                    "file://" + str(path),
                ],
                capture_output=True,
                text=True,
                timeout=35,
                env={**os.environ, "AWS_MAX_ATTEMPTS": "1", "AWS_PAGER": ""},
            )
        if result.returncode:
            codes = re.findall(r"\(([A-Za-z0-9.]+)\)", result.stderr)
            raise AwsError(codes[0] if codes else "aws_command_failed")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def identity(self):
        actual = self.call("get-caller-identity", service="sts")
        expected = (
            f"arn:aws:iam::{self.config['account_id']}:user/{self.config['iam_user']}"
        )
        if (
            actual.get("Account") != self.config["account_id"]
            or actual.get("Arn") != expected
        ):
            raise ValueError(
                "approved IAM account/user mismatch; root/other principals rejected"
            )


class Lifecycle:
    def __init__(self, config, directory, aws=None):
        self.config = config
        validate(config)
        self.directory = Path(directory)
        self.aws = aws or Aws(config)
        self.state_file = self.directory / "resources.json"
        self.state = (
            json.loads(self.state_file.read_text())
            if self.state_file.exists()
            else None
        )
        if self.state and self.state["configuration"] != config:
            raise ValueError("ledger configuration changed; use original configuration")

    def save(self):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.directory / "resources.new"
        with temporary.open("w") as stream:
            json.dump(self.state, stream, indent=2)
            stream.write("\n")
        temporary.chmod(0o600)
        os.replace(temporary, self.state_file)

    def plan(self):
        self.aws.identity()
        image = self.aws.call("describe-images", {"ImageIds": [self.config["ami_id"]]})[
            "Images"
        ]
        if (
            len(image) != 1
            or image[0]["OwnerId"] != CANONICAL
            or image[0]["Architecture"] != "x86_64"
            or not image[0]["Name"].startswith(
                "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-"
            )
        ):
            raise ValueError("trusted Ubuntu24.04/Canonical AMD64 AMI required")
        subnet = self.aws.call(
            "describe-subnets", {"SubnetIds": [self.config["subnet_id"]]}
        )["Subnets"]
        if len(subnet) != 1 or subnet[0]["VpcId"] != self.config["vpc_id"]:
            raise ValueError("approved subnet/VPC mismatch")
        active = self.aws.call(
            "describe-instances",
            {
                "Filters": [
                    {"Name": "tag:Project", "Values": [PROJECT]},
                    {"Name": "tag:Experiment", "Values": ["issue-22", "issue-23"]},
                    {
                        "Name": "instance-state-name",
                        "Values": [
                            "pending",
                            "running",
                            "stopping",
                            "stopped",
                            "shutting-down",
                        ],
                    },
                ]
            },
        )
        other = [
            i
            for r in active["Reservations"]
            for i in r["Instances"]
            if not (self.state and owned(i, self.state["run_id"]))
        ]
        if other:
            raise ValueError(
                "another project experiment VM exists; reconcile before launch"
            )
        return {
            **validate(self.config),
            "identity_verified": True,
            "ami_verified": True,
            "other_active_or_stopped_experiment_vms": len(other),
            "resources_created": False,
        }

    def launch(self):
        if self.state and self.state.get("cleanup"):
            raise ValueError(
                "run already completed; reconcile budget before creating another run"
            )
        self.plan()
        if self.state and self.state.get("instance_id"):
            if datetime.now(timezone.utc) >= ledger_deadline(self.state, self.config):
                self.destroy()
                raise ValueError("expired instance reconciled; cannot extend a run")
            return self.state  # never blindly create a second instance
        if self.state is None:
            self.state = {
                "run_id": "sonar23-" + uuid4().hex,
                "configuration": self.config,
                "deadline_utc": (
                    datetime.now(timezone.utc)
                    + timedelta(minutes=self.config.get("maximum_minutes", 100))
                ).isoformat(),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            self.save()
        run = self.state["run_id"]
        try:
            existing = self.aws.call(
                "describe-security-groups", {"Filters": filters(run)}
            )["SecurityGroups"]
            if len(existing) > 1:
                raise ValueError("ambiguous owned security groups")
            if not existing:
                group = self.aws.call(
                    "create-security-group",
                    {
                        "GroupName": run,
                        "Description": "Temporary Sonar Vision issue23",
                        "VpcId": self.config["vpc_id"],
                        "TagSpecifications": [
                            {"ResourceType": "security-group", "Tags": tags(run)}
                        ],
                    },
                )
                self.state["security_group_id"] = group["GroupId"]
            else:
                self.state["security_group_id"] = existing[0]["GroupId"]
            self.save()
            rules = self.aws.call(
                "describe-security-groups",
                {"GroupIds": [self.state["security_group_id"]]},
            )["SecurityGroups"][0]
            if not owned(rules, run):
                raise ValueError("security group ownership mismatch")
            if not rules["IpPermissions"]:
                self.aws.call(
                    "authorize-security-group-ingress",
                    {
                        "GroupId": self.state["security_group_id"],
                        "IpPermissions": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": port,
                                "ToPort": port,
                                "IpRanges": [{"CidrIp": self.config["operator_cidr"]}],
                            }
                            for port in [22, 8443]
                        ],
                    },
                )
            rules = self.aws.call(
                "describe-security-groups",
                {"GroupIds": [self.state["security_group_id"]]},
            )["SecurityGroups"][0]
            check_ingress(rules, self.config["operator_cidr"])
            key = self.directory / "operator-key"
            if not key.exists():
                subprocess.run(
                    ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
                    check=True,
                    capture_output=True,
                )
            pairs = self.aws.call("describe-key-pairs", {"Filters": filters(run)})[
                "KeyPairs"
            ]
            if len(pairs) > 1:
                raise ValueError("ambiguous owned key pairs")
            if not pairs:
                self.aws.call(
                    "import-key-pair",
                    {
                        "KeyName": run,
                        "PublicKeyMaterial": base64.b64encode(
                            key.with_name("operator-key.pub").read_bytes()
                        ).decode(),
                        "TagSpecifications": [
                            {"ResourceType": "key-pair", "Tags": tags(run)}
                        ],
                    },
                )
            if pairs and not owned(pairs[0], run):
                raise ValueError("SSH key ownership mismatch")
            deadline = ledger_deadline(self.state, self.config)
            if datetime.now(timezone.utc) >= deadline:
                raise ValueError("launch deadline expired")
            request = instance_request(
                self.config, run, self.state["security_group_id"], run, deadline
            )
            response = self.aws.call("run-instances", request)["Instances"]
            if len(response) != 1 or not owned(response[0], run):
                raise ValueError("one owned instance required")
            self.state["instance_id"] = response[0]["InstanceId"]
            self.state["launch_time_utc"] = response[0]["LaunchTime"]
            self.save()
            return self.state
        except BaseException:
            self.destroy()
            raise

    def pin(self):
        self.aws.identity()
        if self.state is None or not self.state.get("instance_id"):
            raise ValueError("instance ledger required")
        run = self.state["run_id"]
        instance = None
        public_key = None
        for _ in range(60):
            found = [
                i
                for r in self.aws.call("describe-instances", {"Filters": filters(run)})[
                    "Reservations"
                ]
                for i in r["Instances"]
            ]
            if (
                len(found) != 1
                or found[0]["InstanceId"] != self.state["instance_id"]
                or not owned(found[0], run)
            ):
                raise ValueError("one matching owned instance required")
            instance = found[0]
            if instance["State"]["Name"] not in ("pending", "running"):
                raise ValueError("instance not available")
            if datetime.now(timezone.utc) >= ledger_deadline(self.state, self.config):
                raise ValueError("connection deadline expired")
            if instance.get("PublicIpAddress"):
                output = self.aws.call(
                    "get-console-output",
                    {"InstanceId": instance["InstanceId"], "Latest": True},
                ).get("Output", "")
                match = re.search(
                    r"SONAR23_HOSTKEY_BEGIN\s+(ssh-ed25519 [A-Za-z0-9+/=]+)(?:[^\n]*)\s+SONAR23_HOSTKEY_END",
                    output,
                )
                if match:
                    public_key = match.group(1)
                    break
            time.sleep(5)
        if not public_key:
            raise ValueError(
                "authenticated SSH host key not available; no TOFU fallback"
            )
        ip = instance["PublicIpAddress"]
        if not ipaddress.ip_address(ip).is_global:
            raise ValueError("public IPv4 address required")
        scanned = subprocess.run(
            ["ssh-keyscan", "-T", "5", "-t", "ed25519", ip],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        keys = {
            " ".join(line.split()[1:3])
            for line in scanned.stdout.splitlines()
            if not line.startswith("#")
        }
        if keys != {public_key}:
            raise ValueError("SSH host key differs from authenticated EC2 console")
        hosts = self.directory / "known_hosts"
        hosts.write_text(ip + " " + public_key + "\n")
        hosts.chmod(0o600)
        self.state["public_ip"] = ip
        self.state["volume_ids"] = [
            entry["Ebs"]["VolumeId"]
            for entry in instance.get("BlockDeviceMappings", [])
        ]
        self.state["ssh_host_key_verified_via_ec2_console"] = True
        raw = base64.b64decode(public_key.split()[1])
        self.state["ssh_host_key_fingerprint"] = "SHA256:" + base64.b64encode(
            hashlib.sha256(raw).digest()
        ).decode().rstrip("=")
        self.save()
        return {
            "host_key_verified": True,
            "private_known_hosts_written": True,
            "deadline_utc": self.state["deadline_utc"],
        }

    def destroy(self):
        self.aws.identity()
        if self.state is None:
            raise ValueError("owned ledger required for destruction")
        run = self.state["run_id"]
        instances = [
            i
            for r in self.aws.call("describe-instances", {"Filters": filters(run)})[
                "Reservations"
            ]
            for i in r["Instances"]
        ]
        for instance in instances:
            if not owned(instance, run):
                raise ValueError("instance ownership mismatch")
            if instance["State"]["Name"] != "terminated":
                self.aws.call(
                    "terminate-instances", {"InstanceIds": [instance["InstanceId"]]}
                )
        for _ in range(90):
            remaining = [
                i
                for r in self.aws.call("describe-instances", {"Filters": filters(run)})[
                    "Reservations"
                ]
                for i in r["Instances"]
                if i["State"]["Name"] != "terminated"
            ]
            if not remaining:
                break
            time.sleep(2)
        else:
            raise ValueError("termination pending; keep ledger and reconcile")
        for command, key in [
            ("describe-volumes", "Volumes"),
            ("describe-key-pairs", "KeyPairs"),
            ("describe-security-groups", "SecurityGroups"),
        ]:
            for resource in self.aws.call(command, {"Filters": filters(run)})[key]:
                if not owned(resource, run):
                    raise ValueError("resource ownership mismatch")
                if key == "Volumes":
                    if resource["State"] != "available":
                        raise ValueError("volume not available for deletion")
                    self.aws.call("delete-volume", {"VolumeId": resource["VolumeId"]})
                elif key == "KeyPairs":
                    self.aws.call(
                        "delete-key-pair", {"KeyPairId": resource["KeyPairId"]}
                    )
                else:
                    self.aws.call(
                        "delete-security-group", {"GroupId": resource["GroupId"]}
                    )
        residual = {
            key: len(self.aws.call(command, {"Filters": filters(run)})[key])
            for command, key in [
                ("describe-volumes", "Volumes"),
                ("describe-key-pairs", "KeyPairs"),
                ("describe-security-groups", "SecurityGroups"),
            ]
        }
        if any(residual.values()):
            raise ValueError("owned resources remain")
        self.state["cleanup"] = {
            "completed_at_utc": self.state.get("cleanup", {}).get(
                "completed_at_utc", datetime.now(timezone.utc).isoformat()
            ),
            "last_audit_at_utc": datetime.now(timezone.utc).isoformat(),
            "residual_resources": residual,
        }
        self.save()
        return self.state["cleanup"]


@contextmanager
def operator_lock(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = directory / "operator.lock"
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "launch", "pin", "destroy"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text())
        with operator_lock(args.run_dir):
            operation = Lifecycle(config, args.run_dir)
            result = getattr(operation, args.action)()
        print(
            json.dumps(
                result
                if args.action != "launch"
                else {
                    "instance_created_or_resumed": True,
                    "deadline_utc": result["deadline_utc"],
                    "private_ledger_written": True,
                },
                indent=2,
            )
        )
    except (ValueError, OSError, KeyError, AwsError, subprocess.SubprocessError):
        parser.exit(
            2,
            "AWS operation failed; inspect private configuration/ledger and reconcile owned resources.\n",
        )


if __name__ == "__main__":
    main()
