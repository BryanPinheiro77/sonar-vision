import unittest
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "aws_preserved_boot",
    Path(__file__).resolve().parents[1] / "scripts/aws_preserved_boot.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
choose_window = module.choose_window

INSTANCE = "i-0a387712b1c657a3c"


def identity(second):
    return {"instanceId": INSTANCE, "pendingTime": f"1970-01-01T00:00:{second:02d}Z"}


class WindowTests(unittest.TestCase):
    def state(self):
        return {
            "version": 1,
            "instance_id": INSTANCE,
            "launch_id": identity(1)["pendingTime"],
            "deadline": 10,
            "remaining_seconds": 764,
        }

    def test_current_reboot_does_not_extend_or_charge(self):
        s = self.state()
        self.assertEqual(choose_window(s, identity(1), 5), s)

    def test_early_stop_start_keeps_deadline(self):
        s = self.state()
        r = choose_window(s, identity(4), 5)
        self.assertEqual(r["deadline"], 10)
        self.assertEqual(r["remaining_seconds"], 764)

    def test_expired_reboot_is_denied(self):
        with self.assertRaises(ValueError):
            choose_window(self.state(), identity(1), 12)

    def test_expired_new_start_uses_only_remaining_budget(self):
        r = choose_window(self.state(), identity(12), 13)
        self.assertEqual(r["deadline"], 776)
        self.assertEqual(r["remaining_seconds"], 0)

    def test_normal_new_start_is_capped_at_twenty_minutes(self):
        s = self.state()
        s["remaining_seconds"] = 2000
        r = choose_window(s, identity(12), 13)
        self.assertEqual(r["deadline"], 1212)
        self.assertEqual(r["remaining_seconds"], 800)

    def test_quota_empty_denied(self):
        s = self.state()
        s["remaining_seconds"] = 0
        with self.assertRaises(ValueError):
            choose_window(s, identity(12), 13)

    def test_retry_is_idempotent(self):
        r = choose_window(self.state(), identity(12), 13)
        self.assertEqual(choose_window(r, identity(12), 14), r)

    def test_instance_clock_and_invalid_state_denied(self):
        for s, i in [
            (self.state(), {**identity(12), "instanceId": "other"}),
            ({**self.state(), "remaining_seconds": -1}, identity(12)),
            ({**self.state(), "remaining_seconds": True}, identity(12)),
            ({**self.state(), "version": 2}, identity(12)),
        ]:
            with self.assertRaises(ValueError):
                choose_window(s, i, 13)


if __name__ == "__main__":
    unittest.main()
