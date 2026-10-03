"""#26 package publication, device update rules and authenticated HTTP routes."""

from importlib.util import find_spec
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from catalog_helpers import make_package, silence, write_manifest
from sonar_vision_api.catalog import PackageRejected, load_package
from sonar_vision_local_audio.catalog import CANDIDATE_PROFILE, ESSENTIAL_IDS
from sonar_vision_local_audio.updater import TransferError, update_catalog

HTTP = all(find_spec(name) for name in ("fastapi", "httpx2", "python_multipart"))


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory())
        self.root = Path(self.directory) / "pkg"
        self.manifest, self.files = make_package(self.root)

    def assertRejected(self, reason):
        with self.assertRaises(PackageRejected) as caught:
            load_package(self.root)
        self.assertEqual(caught.exception.reason, reason)

    def edit(self, function):
        function(self.manifest)
        write_manifest(self.root, self.manifest)

    def test_valid_package_is_published_from_memory(self):
        published = load_package(self.root)
        self.assertEqual(published.catalog_version, "1.0.0")
        self.assertEqual(set(published.files), set(self.files))
        (self.root / "audio" / "local.urgent.wav").write_bytes(b"changed after load")
        self.assertEqual(published.files["audio/local.urgent.wav"], self.files["audio/local.urgent.wav"])

    def test_missing_package_or_manifest(self):
        self.root = Path(self.directory) / "absent"
        self.assertRejected("package_missing")
        self.root = Path(self.directory) / "pkg"
        (self.root / "manifest.json").unlink()
        self.assertRejected("manifest_missing")

    def test_malformed_manifest(self):
        (self.root / "manifest.json").write_text('{"a": 1, "a": 2}', encoding="utf-8")
        self.assertRejected("manifest_not_json")

    def test_paths_outside_the_catalog_are_rejected(self):
        for path in ("../manifest.json", "audio/../manifest.json", "/etc/passwd", "C:/x.wav",
                     "audio/Local.wav", "audio/sub/x.wav", "audio/x.wav:stream", "audio/.hidden.wav"):
            with self.subTest(path=path):
                self.edit(lambda m: m["entries"][3]["audio"].__setitem__("path", path))
                self.assertRejected("audio_path_invalid")

    def test_removed_extra_and_corrupted_files(self):
        (self.root / "audio" / "visual.person.unknown.unknown.none.wav").unlink()
        self.assertRejected("audio_file_missing")
        flipped = bytearray(self.files["audio/visual.person.unknown.unknown.none.wav"])
        flipped[-1] ^= 0xFF  # same size and format, one sample changed
        (self.root / "audio" / "visual.person.unknown.unknown.none.wav").write_bytes(bytes(flipped))
        self.assertRejected("audio_hash_mismatch")
        (self.root / "audio" / "visual.person.unknown.unknown.none.wav").write_bytes(
            self.files["audio/visual.person.unknown.unknown.none.wav"])
        (self.root / "audio" / "stale.wav").write_bytes(silence())
        self.assertRejected("unreferenced_file")
        (self.root / "audio" / "stale.wav").unlink()
        (self.root / "notes.txt").write_text("x", encoding="utf-8")
        self.assertRejected("unexpected_file")

    def test_incompatible_audio_and_versions(self):
        (self.root / "audio" / "local.urgent.wav").write_bytes(silence(rate=22050))
        self.assertRejected("audio_format_mismatch")
        (self.root / "audio" / "local.urgent.wav").write_bytes(b"RIFF....not a wave")
        self.assertRejected("audio_not_pcm_wav")
        (self.root / "audio" / "local.urgent.wav").write_bytes(self.files["audio/local.urgent.wav"])
        self.edit(lambda m: m.__setitem__("schema_version", 2))
        self.assertRejected("schema_unsupported")
        self.edit(lambda m: m.update(schema_version=1, status="draft"))
        self.assertRejected("catalog_not_released")

    def test_origin_license_and_review_are_required(self):
        cases = [("rights", "license", None, "rights_missing"),
                 ("rights", "voice_permission_reference", "", "rights_missing"),
                 ("review", "status", "pending", "review_not_approved"),
                 ("origin", "kind", "synthetic_fixture", "origin_not_distributable")]
        for block, field, value, reason in cases:
            with self.subTest(field=field):
                original = self.manifest["entries"][0]["audio"][block][field]
                self.edit(lambda m: m["entries"][0]["audio"][block].__setitem__(field, value))
                self.assertRejected(reason)
                self.edit(lambda m: m["entries"][0]["audio"][block].__setitem__(field, original))
        self.edit(lambda m: m["approval"].__setitem__("firmware_reference", None))
        self.assertRejected("approval_missing")

    def test_essential_warnings_must_be_in_the_package(self):
        self.edit(lambda m: m["entries"].pop(0))
        (self.root / "audio" / "local.urgent.wav").unlink()
        self.assertRejected("essential_missing")


class FakeServer:
    """In-memory transport with injectable failures."""

    def __init__(self, manifest, files, etag='"v1"'):
        self.raw, self.files, self.etag = json.dumps(manifest).encode(), dict(files), etag
        self.fail_manifest = None
        self.corrupt = {}  # path -> remaining corrupted responses
        self.down = set()
        self.requests = []

    def manifest(self, etag):
        self.requests.append("manifest")
        if self.fail_manifest:
            raise TransferError(self.fail_manifest)
        return None if etag == self.etag else (self.etag, self.raw)

    def file(self, path):
        self.requests.append(path)
        if path in self.down:
            raise TransferError("transfer")
        if self.corrupt.get(path):
            self.corrupt[path] -= 1
            return self.files[path][:-1]
        return self.files[path]


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.manifest, self.files = make_package(Path(directory) / "pkg")
        self.server = FakeServer(self.manifest, self.files)
        self.urgent = False

    def update(self, current=None, etag=None):
        return update_catalog(current, etag, fetch_manifest=self.server.manifest,
                              fetch_file=self.server.file, device_profile=CANDIDATE_PROFILE,
                              urgent=lambda: self.urgent)

    def installed(self):
        catalog, etag, status = self.update()
        self.assertEqual(status, "installed")
        return catalog, etag

    def test_success_installs_essentials_before_use(self):
        catalog, etag = self.installed()
        self.assertEqual(etag, '"v1"')
        for phrase_id in ESSENTIAL_IDS:
            self.assertTrue(catalog.playable(phrase_id))

    def test_not_modified_downloads_nothing(self):
        catalog, etag = self.installed()
        self.server.requests.clear()
        self.assertEqual(self.update(catalog, etag), (catalog, etag, "up_to_date"))
        self.assertEqual(self.server.requests, ["manifest"])

    def test_never_downloads_during_urgency(self):
        self.urgent = True
        self.assertEqual(self.update(), (None, None, "deferred:urgent"))
        self.assertEqual(self.server.requests, [])

    def test_urgency_mid_transfer_keeps_current_catalog(self):
        catalog, etag = self.installed()
        self.server.etag = '"v2"'
        original = self.server.file

        def file_then_urgent(path):
            self.urgent = True
            return original(path)

        self.server.file = file_then_urgent
        self.assertEqual(self.update(catalog, etag), (catalog, etag, "deferred:urgent"))

    def test_missing_catalog_and_transfer_failures_keep_current(self):
        catalog, etag = self.installed()
        self.server.etag = '"v2"'
        self.server.fail_manifest = "catalog_unavailable"
        self.assertEqual(self.update(catalog, etag), (catalog, etag, "failed:catalog_unavailable"))
        self.server.fail_manifest = None
        self.server.down.add("audio/local.urgent.wav")
        self.assertEqual(self.update(catalog, etag), (catalog, etag, "failed:transfer"))

    def test_corruption_in_transit_is_retried_then_rejected(self):
        self.server.corrupt["audio/local.urgent.wav"] = 1
        self.assertEqual(self.update()[2], "installed")
        self.server.corrupt["audio/local.urgent.wav"] = 5
        self.assertEqual(self.update(), (None, None, "failed:integrity"))

    def test_incompatible_package_keeps_current(self):
        catalog, etag = self.installed()
        bad = json.loads(self.server.raw)
        bad["profile"] = {**CANDIDATE_PROFILE, "sample_rate_hz": 22050}
        self.server.raw, self.server.etag = json.dumps(bad).encode(), '"v2"'
        self.assertEqual(self.update(catalog, etag), (catalog, etag, "rejected:profile_incompatible"))
        self.server.raw = b"not json"
        self.assertEqual(self.update(catalog, etag), (catalog, etag, "rejected:manifest_invalid"))


@unittest.skipUnless(HTTP, "install .[api,api-dev] to exercise the catalog routes")
class CatalogHttpTests(unittest.TestCase):
    TOKEN = "catalog-test-token-not-a-secret"

    def client(self, published):
        from fastapi.testclient import TestClient
        from sonar_vision.benchmark import SyntheticBackend
        from sonar_vision.core import VisionService
        from sonar_vision_api.app import create_app
        from sonar_vision_api.auth import TokenStore, token_hash
        from sonar_vision_api.service import InferenceService, header_only_decoder

        service = InferenceService(VisionService(SyntheticBackend), header_only_decoder,
                                   timeout_ms=1500)
        self.addCleanup(service.close)
        app = create_app(service, TokenStore({"glasses-01": token_hash(self.TOKEN)}),
                         backend="simulated", max_body_bytes=4096, max_pixels=640 * 480,
                         catalog=published)
        return TestClient(app, raise_server_exceptions=False)

    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.manifest, self.files = make_package(Path(directory) / "pkg")
        self.published = load_package(Path(directory) / "pkg")
        self.http = self.client(self.published)
        self.auth = {"Authorization": f"Bearer {self.TOKEN}"}

    def test_manifest_with_etag_no_store_and_not_modified(self):
        response = self.http.get("/v1/catalog/manifest", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.published.manifest_bytes)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-catalog-version"], "1.0.0")
        again = self.http.get("/v1/catalog/manifest",
                              headers={**self.auth, "If-None-Match": response.headers["etag"]})
        self.assertEqual(again.status_code, 304)
        self.assertEqual(again.content, b"")

    def test_files_only_for_referenced_paths(self):
        response = self.http.get("/v1/catalog/files/audio/local.urgent.wav", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.files["audio/local.urgent.wav"])
        self.assertEqual(response.headers["x-content-sha256"],
                         self.published.hashes["audio/local.urgent.wav"])
        for path in ("audio/missing.wav", "manifest.json", "audio/../manifest.json",
                     "audio/%2e%2e/manifest.json"):
            with self.subTest(path=path):
                missing = self.http.get(f"/v1/catalog/files/{path}", headers=self.auth)
                self.assertEqual(missing.status_code, 404)
                self.assertIn(missing.json()["error"]["code"], ("not_found",))

    def test_credentials_are_required(self):
        for url in ("/v1/catalog/manifest", "/v1/catalog/files/audio/local.urgent.wav"):
            response = self.http.get(url)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"error": {"code": "unauthorized"}})

    def test_no_catalog_published(self):
        http = self.client(None)
        response = http.get("/v1/catalog/manifest", headers=self.auth)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"error": {"code": "catalog_unavailable"}})

    def test_device_update_through_the_api(self):
        def fetch_manifest(etag):
            headers = dict(self.auth, **({"If-None-Match": etag} if etag else {}))
            response = self.http.get("/v1/catalog/manifest", headers=headers)
            if response.status_code == 304:
                return None
            if response.status_code != 200:
                raise TransferError(response.json()["error"]["code"])
            return response.headers["etag"], response.content

        def fetch_file(path):
            response = self.http.get(f"/v1/catalog/files/{path}", headers=self.auth)
            if response.status_code != 200:
                raise TransferError(response.json()["error"]["code"])
            return response.content

        catalog, etag, status = update_catalog(None, None, fetch_manifest=fetch_manifest,
                                               fetch_file=fetch_file,
                                               device_profile=CANDIDATE_PROFILE,
                                               urgent=lambda: False)
        self.assertEqual(status, "installed")
        self.assertTrue(catalog.playable("local.urgent"))
        self.assertEqual(update_catalog(catalog, etag, fetch_manifest=fetch_manifest,
                                        fetch_file=fetch_file, device_profile=CANDIDATE_PROFILE,
                                        urgent=lambda: False)[2], "up_to_date")


if __name__ == "__main__":
    unittest.main()
