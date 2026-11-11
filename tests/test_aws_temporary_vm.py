"""#23 lifecycle limits, expiry across reboot and ownership before destruction."""

import base64
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class TemporaryVmTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "temporary_vm",
            Path(__file__).resolve().parents[1] / "scripts/aws_temporary_vm.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.config = {
            "account_id": "123456789012",
            "iam_user": "operator",
            "profile": "project",
            "region": "sa-east-1",
            "instance_type": "c7i-flex.xlarge",
            "ami_id": "ami-123abc",
            "vpc_id": "vpc-123abc",
            "subnet_id": "subnet-123abc",
            "operator_cidr": "8.8.8.8/32",
            "maximum_minutes": 100,
            "previous_instance_hours": 3.75,
            "previous_consumption_estimate_usd": 1.32,
            "compute_usd_per_hour": 0.26135,
            "gp3_usd_per_gb_month": 0.152,
        }

    def test_broad_ingress_wrong_capacity_and_exhausted_budget_rejected(self):
        for update in [
            {"operator_cidr": "0.0.0.0/0"},
            {"operator_cidr": "8.8.8.0/24"},
            {"operator_cidr": "127.0.0.1/32"},
            {"region": "us-east-1"},
            {"instance_type": "c7i-flex.large"},
            {"maximum_minutes": True},
            {"maximum_minutes": 101},
            {"previous_instance_hours": 6.1},
            {"previous_consumption_estimate_usd": 15},
            {"compute_usd_per_hour": float("nan")},
            {"compute_usd_per_hour": 0},
            {"gp3_usd_per_gb_month": 0},
        ]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.module.validate({**self.config, **update})

    def test_launch_one_instance_with_encrypted_deleted_root_and_absolute_expiry(self):
        deadline = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)
        r = self.module.instance_request(
            self.config, "run-test", "sg-123", "key-test", deadline
        )
        self.assertEqual((r["MinCount"], r["MaxCount"]), (1, 1))
        self.assertEqual(r["ClientToken"], "run-test")
        self.assertEqual(r["MetadataOptions"]["HttpTokens"], "required")
        self.assertEqual(r["InstanceInitiatedShutdownBehavior"], "terminate")
        root = r["BlockDeviceMappings"][0]["Ebs"]
        self.assertTrue(root["Encrypted"] and root["DeleteOnTermination"])
        self.assertEqual(root["VolumeSize"], 20)
        script = base64.b64decode(r["UserData"]).decode()
        self.assertIn("OnCalendar=2026-10-08 16:00:00 UTC", script)
        self.assertIn("Persistent=true", script)
        self.assertIn("ExecStartPre=/usr/local/sbin/sonar23-expiry-check", script)
        self.assertNotIn("OnActiveSec", script)
        for kind in r["TagSpecifications"]:
            self.assertEqual(
                {x["Key"]: x["Value"] for x in kind["Tags"]}["Experiment"], "issue-23"
            )

    def test_ingress_reconciliation_rejects_ipv6_or_extra_ports(self):
        group = {
            "IpPermissions": [
                {
                    "IpProtocol": "tcp",
                    "FromPort": p,
                    "ToPort": p,
                    "IpRanges": [{"CidrIp": "8.8.8.8/32"}],
                }
                for p in [22, 8443]
            ]
        }
        self.module.check_ingress(group, "8.8.8.8/32")
        group["IpPermissions"][0]["Ipv6Ranges"] = [{"CidrIpv6": "::/0"}]
        with self.assertRaises(ValueError):
            self.module.check_ingress(group, "8.8.8.8/32")

    def test_root_or_different_account_cannot_operate(self):
        aws = self.module.Aws(self.config)
        for arn, account in [
            ("arn:aws:iam::123456789012:root", "123456789012"),
            ("arn:aws:iam::999999999999:user/operator", "999999999999"),
        ]:
            aws.call = lambda *args, **kwargs: {"Arn": arn, "Account": account}
            with self.assertRaises(ValueError):
                aws.identity()

    def test_ownership_requires_all_tags_and_exact_experiment_spelling(self):
        resource = {"Tags": self.module.tags("run-test")}
        self.assertTrue(self.module.owned(resource, "run-test"))
        resource["Tags"][1]["Value"] = "issue23"
        self.assertFalse(self.module.owned(resource, "run-test"))
        resource["Tags"] = self.module.tags("another-run")
        self.assertFalse(self.module.owned(resource, "run-test"))

    def test_destroy_rejects_unowned_resource_without_delete(self):
        calls = []

        class Fake:
            def identity(inner):
                pass

            def call(inner, action, params):
                calls.append(action)
                if action == "describe-instances":
                    return {"Reservations": []}
                if action == "describe-volumes":
                    return {
                        "Volumes": [
                            {"Tags": [], "State": "available", "VolumeId": "vol-other"}
                        ]
                    }
                raise AssertionError("unexpected mutation " + action)

        with TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "resources.json").write_text(
                json.dumps({"run_id": "run-test", "configuration": self.config})
            )
            life = self.module.Lifecycle(self.config, p, Fake())
            with self.assertRaisesRegex(ValueError, "ownership"):
                life.destroy()
        self.assertNotIn("delete-volume", calls)

    def test_completed_run_never_launches_again(self):
        class Fake:
            def identity(inner):
                pass

            def call(inner, *args, **kwargs):
                raise AssertionError("no AWS request expected")

        with TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "resources.json").write_text(
                json.dumps(
                    {
                        "run_id": "run-test",
                        "configuration": self.config,
                        "cleanup": {"completed_at_utc": "done"},
                        "instance_id": "i-old",
                    }
                )
            )
            life = self.module.Lifecycle(self.config, p, Fake())
            # plan is intentionally checked first; patch only this read-only stage.
            life.plan = lambda: {}
            with self.assertRaisesRegex(ValueError, "completed"):
                life.launch()

    def test_boot_guard_blocks_missing_corrupt_or_expired_deadline(self):
        import os
        import subprocess

        deadline = datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc)
        text = self.module.bootstrap(deadline)
        guard = text.split("<<'GUARD'\n", 1)[1].split("\nGUARD", 1)[0]
        subprocess.run(["bash", "-n"], input=text, text=True, check=True)
        with TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "deadline"
            marker = root / "poweroff"
            date = root / "date"
            date.write_text("#!/bin/sh\nprintf 200\n")
            date.chmod(0o755)
            power = root / "systemctl"
            power.write_text("#!/bin/sh\ntouch " + str(marker) + "\n")
            power.chmod(0o755)
            guard = guard.replace("/var/lib/sonar23/deadline", str(file))
            env = {**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"]}
            for value in [None, "", "not-a-timestamp", "100", "300"]:
                marker.unlink(missing_ok=True)
                if value is None:
                    file.unlink(missing_ok=True)
                else:
                    file.write_text(value)
                result = subprocess.run(
                    ["bash"], input=guard, text=True, env=env, capture_output=True
                )
                self.assertEqual(result.returncode == 0, value == "300")
                self.assertEqual(marker.exists(), value == "100")

    def test_launch_failure_removes_owned_key_and_group(self):
        module = self.module
        config = self.config
        calls = []

        class Fake:
            group = None
            key = None

            def identity(inner):
                pass

            def call(inner, action, params):
                calls.append(action)
                if action == "describe-instances":
                    return {"Reservations": []}
                if action == "describe-security-groups":
                    return {"SecurityGroups": [inner.group] if inner.group else []}
                if action == "create-security-group":
                    inner.group = {
                        "GroupId": "sg-created",
                        "Tags": params["TagSpecifications"][0]["Tags"],
                        "IpPermissions": [],
                    }
                    return {"GroupId": "sg-created"}
                if action == "authorize-security-group-ingress":
                    inner.group["IpPermissions"] = params["IpPermissions"]
                    return {}
                if action == "describe-key-pairs":
                    return {"KeyPairs": [inner.key] if inner.key else []}
                if action == "import-key-pair":
                    inner.key = {
                        "KeyPairId": "key-created",
                        "Tags": params["TagSpecifications"][0]["Tags"],
                    }
                    return inner.key
                if action == "run-instances":
                    raise module.AwsError("UnauthorizedOperation")
                if action == "describe-volumes":
                    return {"Volumes": []}
                if action == "delete-key-pair":
                    inner.key = None
                    return {}
                if action == "delete-security-group":
                    inner.group = None
                    return {}
                raise AssertionError(action)

        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "operator-key").write_text("synthetic-placeholder-not-a-key")
            (root / "operator-key.pub").write_text("synthetic-placeholder-public")
            fake = Fake()
            lifecycle = module.Lifecycle(config, root, fake)
            lifecycle.plan = lambda: {}
            with self.assertRaises(module.AwsError):
                lifecycle.launch()
            self.assertIsNone(fake.group)
            self.assertIsNone(fake.key)
            self.assertEqual(calls.count("run-instances"), 1)
            self.assertTrue(lifecycle.state["cleanup"])

    def test_console_and_network_host_keys_must_match_before_trust_file(self):
        from datetime import timedelta
        from unittest.mock import patch
        from types import SimpleNamespace

        now = datetime.now(timezone.utc)
        module = self.module

        class Fake:
            def identity(inner):
                pass

            def call(inner, action, params):
                if action == "describe-instances":
                    return {
                        "Reservations": [
                            {
                                "Instances": [
                                    {
                                        "InstanceId": "i-owned",
                                        "Tags": module.tags("run-test"),
                                        "State": {"Name": "running"},
                                        "PublicIpAddress": "8.8.8.8",
                                    }
                                ]
                            }
                        ]
                    }
                if action == "get-console-output":
                    return {
                        "Output": "SONAR23_HOSTKEY_BEGIN\nssh-ed25519 QUJD comment\nSONAR23_HOSTKEY_END\n"
                    }
                raise AssertionError(action)

        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "resources.json").write_text(
                json.dumps(
                    {
                        "run_id": "run-test",
                        "configuration": self.config,
                        "instance_id": "i-owned",
                        "created_at_utc": now.isoformat(),
                        "deadline_utc": (now + timedelta(minutes=10)).isoformat(),
                    }
                )
            )
            lifecycle = module.Lifecycle(self.config, root, Fake())
            with patch.object(
                module.subprocess,
                "run",
                return_value=SimpleNamespace(stdout="8.8.8.8 ssh-ed25519 REVG\n"),
            ):
                with self.assertRaisesRegex(ValueError, "differs"):
                    lifecycle.pin()
            self.assertFalse((root / "known_hosts").exists())

    def test_ledger_cannot_extend_expiry_beyond_approved_lifetime(self):
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        for minutes in [101, 1000000]:
            state = {
                "created_at_utc": now.isoformat(),
                "deadline_utc": (now + timedelta(minutes=minutes)).isoformat(),
            }
            with self.assertRaisesRegex(ValueError, "lifetime"):
                self.module.ledger_deadline(state, self.config)
