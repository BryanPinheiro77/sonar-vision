"""#27 review regressions for the integration client (requires .[api,api-dev]).

Total deadline over slow/hung TLS servers, streamed response limit and
malformed fields that must become a discard without changing admission state.
"""

from importlib.util import find_spec
import json
from pathlib import Path
import socket
import ssl
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest

from api_helpers import jpeg

AVAILABLE = all(find_spec(n) for n in ("httpx2", "trustme", "fastapi"))


class SlowTlsServer:
    """Answers 200 after `head_delay`, then dribbles `body` in `chunks` pieces."""

    def __init__(self, tls, body: bytes, *, chunks=20, delay=0.15, head_delay=0.0,
                 respond=True):
        self.body, self.chunks, self.delay = body, chunks, delay
        self.head_delay, self.respond = head_delay, respond
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(str(tls["cert"]), str(tls["key"]))
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen()
        self.port = self.socket.getsockname()[1]
        self.stop = Event()
        self.finished = Event()
        self.thread = Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        try:
            raw, _ = self.socket.accept()
        except OSError:
            return
        try:
            if not self.respond:  # accept TCP, never complete TLS or answer
                self.stop.wait(10)
                return
            with self.context.wrap_socket(raw, server_side=True) as connection:
                connection.settimeout(5)
                request = b""
                while b"\r\n\r\n" not in request:
                    request += connection.recv(65536)
                head, _, rest = request.partition(b"\r\n\r\n")
                length = int([line.split(b":")[1] for line in head.split(b"\r\n")
                              if line.lower().startswith(b"content-length")][0])
                while len(rest) < length:
                    rest += connection.recv(65536)
                time.sleep(self.head_delay)
                connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                                   + f"Content-Length: {len(self.body)}\r\n\r\n".encode())
                size = -(-len(self.body) // self.chunks)
                for start in range(0, len(self.body), size):
                    if self.stop.is_set():
                        return
                    time.sleep(self.delay)
                    connection.sendall(self.body[start:start + size])
        except OSError:
            pass
        finally:
            raw.close()
            self.finished.set()

    def close(self):
        self.stop.set()
        self.socket.close()
        self.thread.join(5)


def valid_body(client, capture, **object_changes) -> bytes:
    item = {"track_id": "1", "class_name": "person", "confidence": 0.9, "direction": "unknown",
            "movement": "unknown", "stair_direction": None, **object_changes}
    observation = {"version": "0.1", "type": "visual_observation", "session_id": client.session_id,
                   "message_id": "obs-" + capture.frame_id, "frame_id": capture.frame_id,
                   "captured_at_ms": capture.captured_at_ms, "valid_for_ms": 1000,
                   "tracker_epoch": "epoch-1", "objects": [item]}
    return json.dumps({"observation": observation, "audio": None}).encode()


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] to exercise the integration client")
class ClientReviewTests(unittest.TestCase):
    def setUp(self):
        from sonar_vision_api.dev_tls import create

        self.tls = create(Path(self.enterContext(TemporaryDirectory())) / "tls")

    def client(self, url="https://127.0.0.1:1", **options):
        from sonar_vision_integration.client import DeviceClient

        options.setdefault("clock", lambda: 10_000)  # constant: isolate from expiry
        client = DeviceClient(url, "token", self.tls["ca"], **options)
        self.addCleanup(client.close)
        return client

    def server(self, body, **options):
        server = SlowTlsServer(self.tls, body, **options)
        self.addCleanup(server.close)
        return server

    def assertTimeoutWithinDeadline(self, client, capture):
        from sonar_vision_integration.client import ClientBusy, Discarded

        started = time.monotonic()
        with self.assertRaises(Discarded) as caught:
            client.send(capture)
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.reason, "timeout")
        self.assertGreaterEqual(elapsed, 1.95)
        self.assertLess(elapsed, 2.3)  # total deadline, not per operation
        return ClientBusy

    # ----- 2. total deadline ---------------------------------------------
    def test_slow_body_hits_total_deadline_and_keeps_lock_until_worker_ends(self):
        client = self.client()
        capture = client.capture(jpeg())
        server = self.server(valid_body(client, capture), chunks=20, delay=0.15)  # ~3 s total
        client.url = f"https://127.0.0.1:{server.port}"
        client_busy = self.assertTimeoutWithinDeadline(client, capture)
        # The transport worker may still be reading: no overlapping request is allowed.
        if client.busy:
            with self.assertRaises(client_busy):
                client.send(client.capture(jpeg()))
        deadline = time.monotonic() + 1
        while client.busy and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(client.busy)  # worker stopped at the next chunk after the deadline
        self.assertEqual(client.seen, set())  # the late response was never admitted

    def test_sum_of_stages_exceeds_deadline_even_if_each_stage_is_short(self):
        client = self.client()
        capture = client.capture(jpeg())
        # 1.2 s before headers + 1.2 s of body: each step < 2 s, the total is not.
        server = self.server(valid_body(client, capture), chunks=8, delay=0.15, head_delay=1.2)
        client.url = f"https://127.0.0.1:{server.port}"
        self.assertTimeoutWithinDeadline(client, capture)

    def test_server_that_never_answers(self):
        client = self.client()
        server = self.server(b"", respond=False)
        client.url = f"https://127.0.0.1:{server.port}"
        self.assertTimeoutWithinDeadline(client, client.capture(jpeg()))

    def test_fast_valid_response_is_admitted(self):
        client = self.client()
        capture = client.capture(jpeg())
        server = self.server(valid_body(client, capture), chunks=2, delay=0.0)
        client.url = f"https://127.0.0.1:{server.port}"
        self.assertEqual(client.send(capture)["observation"]["frame_id"], capture.frame_id)
        self.assertFalse(client.busy)

    # ----- 3. streamed response limit ------------------------------------
    def counting_transport(self, status=200, headers=None):
        import httpx2

        consumed = []

        class Stream(httpx2.SyncByteStream):
            def __iter__(self):
                for _ in range(100):
                    consumed.append(8192)
                    yield b"x" * 8192

        def handler(request):
            return httpx2.Response(status, headers=headers or {}, stream=Stream())

        return httpx2.MockTransport(handler), consumed

    def test_oversized_body_is_cut_while_streaming(self):
        from sonar_vision_integration.client import Discarded

        for status in (200, 500):  # error responses are limited too
            with self.subTest(status=status):
                transport, consumed = self.counting_transport(status)
                client = self.client(transport=transport)
                with self.assertRaises(Discarded) as caught:
                    client.send(client.capture(jpeg()))
                self.assertEqual(caught.exception.reason, "response_too_large")
                self.assertLessEqual(sum(consumed), 16384 + 8192)  # stopped right after the limit

    def test_declared_oversized_length_is_rejected_before_reading(self):
        from sonar_vision_integration.client import Discarded

        transport, consumed = self.counting_transport(headers={"Content-Length": "819200"})
        client = self.client(transport=transport)
        with self.assertRaises(Discarded) as caught:
            client.send(client.capture(jpeg()))
        self.assertEqual(caught.exception.reason, "response_too_large")
        self.assertEqual(consumed, [])

    # ----- 4. malformed fields -------------------------------------------
    def test_wrong_enum_types_are_discarded_without_state_change(self):
        from sonar_vision_integration.client import Discarded

        client = self.client()
        capture = client.capture(jpeg())
        for field in ("class_name", "direction", "movement"):
            for value in ([], {}, 1, None):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(Discarded) as caught:
                        client.admit(valid_body(client, capture, **{field: value}))
                    self.assertEqual(caught.exception.reason, "invalid_message")
                    self.assertEqual((client.seen, client.last_admitted_frame), (set(), -1))
        client.admit(valid_body(client, capture))  # the valid one is still admissible
        self.assertEqual(client.last_admitted_frame, int(capture.frame_id))


if __name__ == "__main__":
    unittest.main()
