"""#23 credential lifecycle: old processes, failed writes and concurrent operators."""
import contextlib
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision_api.auth import TokenStore
from sonar_vision_api.errors import ApiError
from sonar_vision_api.token_ops import main, maintain


class CredentialLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(TemporaryDirectory())
        self.root = Path(self.temp)
        self.store = self.root / 'tokens'

    def provision(self, device='glasses-01'):
        output = self.root / (device + '.token')
        maintain(self.store, device, 'provision', output)
        return output.read_text().strip()

    def test_rotation_requires_reload_and_revokes_only_target_device(self):
        old = self.provision()
        other = self.provision('test-operator')
        running = TokenStore.from_file(self.store)
        output = self.root / 'rotated.token'
        maintain(self.store, 'glasses-01', 'rotate', output)
        new = output.read_text().strip()
        self.assertNotEqual(new, old)
        self.assertEqual(running.authenticate('Bearer ' + old), 'glasses-01')
        with self.assertRaises(ApiError):
            running.authenticate('Bearer ' + new)
        reloaded = TokenStore.from_file(self.store)
        with self.assertRaises(ApiError):
            reloaded.authenticate('Bearer ' + old)
        self.assertEqual(reloaded.authenticate('Bearer ' + new), 'glasses-01')
        self.assertEqual(reloaded.authenticate('Bearer ' + other), 'test-operator')
        maintain(self.store, 'glasses-01', 'revoke')
        reloaded = TokenStore.from_file(self.store)
        with self.assertRaises(ApiError):
            reloaded.authenticate('Bearer ' + new)
        self.assertEqual(reloaded.authenticate('Bearer ' + other), 'test-operator')

    def test_revoking_last_device_prevents_startup(self):
        self.provision()
        maintain(self.store, 'glasses-01', 'revoke')
        with self.assertRaisesRegex(ValueError, 'no devices'):
            TokenStore.from_file(self.store)

    def test_failed_commit_keeps_old_credential_and_removes_unused_plaintext(self):
        old = self.provision()
        before = self.store.read_bytes()
        output = self.root / 'new.token'
        with patch('sonar_vision_api.token_ops.os.replace', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                maintain(self.store, 'glasses-01', 'rotate', output)
        self.assertEqual(self.store.read_bytes(), before)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.root.glob('.credentials-*')))
        self.assertFalse(self.store.with_name('tokens.lock').exists())
        self.assertEqual(TokenStore.from_file(self.store).authenticate('Bearer ' + old), 'glasses-01')

    def test_existing_output_and_operator_lock_prevent_change(self):
        self.provision()
        before = self.store.read_bytes()
        existing = self.root / 'existing.token'
        existing.write_text('keep')
        with self.assertRaises(FileExistsError):
            maintain(self.store, 'glasses-01', 'rotate', existing)
        lock = self.root / 'tokens.lock'
        lock.write_text('another operator')
        with self.assertRaises(FileExistsError):
            maintain(self.store, 'glasses-01', 'revoke')
        self.assertEqual(lock.read_text(), 'another operator')
        self.assertEqual(self.store.read_bytes(), before)
        self.assertEqual(existing.read_text(), 'keep')

    def test_plaintext_output_cannot_replace_hash_snapshot(self):
        with self.assertRaises(ValueError):
            maintain(self.store, "glasses-01", "provision", self.store)
        self.assertFalse(self.store.exists())

    def test_corrupt_store_or_symlink_is_never_replaced(self):
        self.store.write_text('glasses-01 invalid\n')
        with self.assertRaises(ValueError):
            maintain(self.store, 'glasses-01', 'rotate', self.root / 'new.token')
        self.assertEqual(self.store.read_text(), 'glasses-01 invalid\n')
        link = self.root / 'linked'
        link.symlink_to(self.store)
        with self.assertRaises(ValueError):
            maintain(link, 'glasses-01', 'revoke')
        self.assertTrue(link.is_symlink())

    @unittest.skipIf(os.name == 'nt', 'POSIX file permissions')
    def test_private_permissions_and_no_plaintext_on_stdout(self):
        out = self.root / 'new.token'
        with contextlib.redirect_stdout(io.StringIO()) as log:
            main(['provision', 'glasses-01', str(self.store), '--token-file', str(out)])
        token = out.read_text().strip()
        self.assertNotIn(token, log.getvalue())
        self.assertNotIn(token, self.store.read_text())
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
