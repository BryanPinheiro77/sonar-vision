"""#24 validation logic that needs only the standard library."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from api_helpers import jpeg, metadata
from sonar_vision.benchmark import SyntheticBackend
from sonar_vision.core import Frame, VisionService
from sonar_vision_api import contract
from sonar_vision_api.auth import TokenStore, token_hash
from sonar_vision_api.config import Settings
from sonar_vision_api.errors import ApiError
from sonar_vision_api.validation import jpeg_dimensions, parse_metadata

PROTOCOL = Path(__file__).resolve().parents[1] / "docs" / "protocol" / "exemplos-eventos.json"


class MetadataTests(unittest.TestCase):
    def assertRejected(self, raw, status=400):
        with self.assertRaises(ApiError) as caught:
            parse_metadata(raw)
        self.assertEqual(caught.exception.status, status)

    def test_valid_metadata(self):
        meta = parse_metadata(metadata(frame_id="12", captured_at_ms=0))
        self.assertEqual((meta.session_id, meta.frame_id, meta.captured_at_ms), ("boot-1", "12", 0))

    def test_rejects_fields_types_and_versions(self):
        self.assertRejected(metadata(extra_field=1))
        self.assertRejected(b'{"version":"0.1","session_id":"a","frame_id":"1"}')
        self.assertRejected(metadata(version="0.2").replace(b'"0.1"', b'"0.2"', 1))
        for frame in ("01", "-1", "1.0", "", "a"):
            self.assertRejected(metadata(frame_id=frame))
        for captured in (-1, 1.0, True, 2**53, "1"):
            self.assertRejected(metadata(captured_at_ms=captured))
        self.assertRejected(metadata(session_id=""))
        self.assertRejected(metadata(session_id="x" * 129))

    def test_rejects_duplicate_keys_nan_and_bad_encoding(self):
        self.assertRejected(b'{"version":"0.1","version":"0.1","session_id":"a",'
                            b'"frame_id":"1","captured_at_ms":1}')
        self.assertRejected(b'{"version":"0.1","session_id":"a","frame_id":"1","captured_at_ms":NaN}')
        self.assertRejected(b"\xff\xfe")
        self.assertRejected(b"[]")
        self.assertRejected(b" " * 2000)


class JpegHeaderTests(unittest.TestCase):
    def test_reads_dimensions_without_decoding(self):
        self.assertEqual(jpeg_dimensions(jpeg(480, 640), 640 * 480), (480, 640))

    def test_limits_and_format(self):
        cases = [(jpeg(1201, 1600), 413), (b"\x89PNG\r\n", 415), (b"", 415),
                 (jpeg()[:12], 400), (jpeg(0, 640), 400),
                 (b"\xff\xd8\xff\xda\x00\x02\xff\xd9", 400)]
        for data, status in cases:
            with self.assertRaises(ApiError) as caught:
                jpeg_dimensions(data, 1600 * 1200)
            self.assertEqual(caught.exception.status, status)


def observation():
    vision = VisionService(SyntheticBackend)
    vision.open("device", "boot-1")
    return vision.process(Frame("device", "boot-1", "1", 1000, None)).observation()


def audio_for(obs, **changes):
    audio = {"version": "0.1", "type": "audio_suggestion", "session_id": obs["session_id"],
             "message_id": "audio-1", "frame_id": obs["frame_id"],
             "captured_at_ms": obs["captured_at_ms"], "valid_for_ms": obs["valid_for_ms"],
             "observation_id": obs["message_id"], "text": "Pessoa", "directional": False}
    audio.update(changes)
    return audio


class ContractTests(unittest.TestCase):
    def test_vision_output_and_protocol_examples_are_valid(self):
        obs = observation()
        body = json.loads(contract.encode(obs, None))
        self.assertEqual(set(body), {"observation", "audio"})
        self.assertIsNone(body["audio"])
        examples = json.loads(PROTOCOL.read_text(encoding="utf-8"))
        # The documented 200 example combines both fixtures.
        body = contract.encode(examples["valid_observation"], examples["valid_audio"])
        self.assertEqual(json.loads(body)["audio"]["observation_id"], "obs-42")

    def test_audio_references_and_limits(self):
        obs = observation()
        contract.encode(obs, audio_for(obs))
        contract.encode(obs, audio_for(obs, text="é" * 120))
        bad = [dict(observation_id="other"), dict(session_id="other"), dict(frame_id="2"),
               dict(captured_at_ms=1), dict(valid_for_ms=obs["valid_for_ms"] + 1),
               dict(text=""), dict(text="a" * 121), dict(directional=1),
               dict(message_id=obs["message_id"]), dict(type="visual_observation")]
        for change in bad:
            with self.subTest(change=change), self.assertRaises(contract.ContractViolation):
                contract.encode(obs, audio_for(obs, **change))
        with self.assertRaises(contract.ContractViolation):
            contract.encode(obs, {**audio_for(obs), "extra": True})

    def test_observation_bounds(self):
        obs = observation()
        item = obs["objects"][0]
        for change in (dict(objects=[item] * 21), dict(valid_for_ms=0), dict(version="0.2")):
            with self.assertRaises(contract.ContractViolation):
                contract.encode({**obs, **change}, None)
        for change in (dict(confidence=float("nan")), dict(direction="up"),
                       dict(stair_direction="up"), dict(class_name="cat")):
            with self.assertRaises(contract.ContractViolation):
                contract.encode({**obs, "objects": [{**item, **change}]}, None)

    def test_response_size_limit(self):
        # Worst case within the other 0.1 limits is ~7 KiB, so the 16 KiB guard is
        # exercised with a lowered bound; the real constant is asserted separately.
        self.assertEqual(contract.MAX_RESPONSE_BYTES, 16384)
        obs = observation()
        obs["objects"] = obs["objects"] * 20
        with patch.object(contract, "MAX_RESPONSE_BYTES", 1024):
            with self.assertRaises(contract.ContractViolation):
                contract.encode(obs, None)


class AuthTests(unittest.TestCase):
    def test_bearer_maps_to_device_and_rejects_unknown(self):
        store = TokenStore({"glasses-01": token_hash("secret-token")})
        self.assertEqual(store.authenticate("Bearer secret-token"), "glasses-01")
        self.assertEqual(store.authenticate("bearer secret-token"), "glasses-01")
        for header in (None, "", "Bearer ", "Basic secret-token", "Bearer other"):
            with self.assertRaises(ApiError) as caught:
                store.authenticate(header)
            self.assertEqual(caught.exception.status, 401)

    def test_token_file_rejects_duplicates(self):
        digest = token_hash("t")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "tokens"
            path.write_text(f"# comment\na {digest}\nb {digest}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                TokenStore.from_file(path)
            path.write_text(f"a {digest}\na {token_hash('u')}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                TokenStore.from_file(path)
            path.write_text("a not-a-hash\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                TokenStore.from_file(path)


class SettingsTests(unittest.TestCase):
    def test_requires_explicit_backend_and_bounded_timeout(self):
        with TemporaryDirectory() as directory:
            tokens = Path(directory) / "tokens"
            tokens.write_text("", encoding="utf-8")
            env = {"SONAR_API_BACKEND": "simulated", "SONAR_API_TOKENS_FILE": str(tokens)}
            self.assertEqual(Settings.from_env(env).backend, "simulated")
            for broken in ({"SONAR_API_BACKEND": ""}, {"SONAR_API_BACKEND": "fake"},
                           {"SONAR_API_TIMEOUT_MS": "2000"}, {"SONAR_API_MAX_PIXELS": "0"},
                           {"SONAR_API_MAX_BODY_BYTES": "x"},
                           {"SONAR_API_BACKEND": "ultralytics"},
                           {"SONAR_API_TOKENS_FILE": os.path.join(directory, "missing")}):
                with self.assertRaises(ValueError):
                    Settings.from_env({**env, **broken})


if __name__ == "__main__":
    unittest.main()
