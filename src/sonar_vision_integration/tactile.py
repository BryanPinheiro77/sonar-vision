"""Independent simulation: a hung network/API never blocks the simulated tactile path.

Mirrors the intended firmware split: the tactile loop only reads a local
distance source and drives a simulated actuator; the network task runs
separately and shares nothing the loop could wait on. This is NOT hardware
validation: a desktop OS scheduler is not FreeRTOS timing, and the distance
threshold here is a simulation value, not a risk threshold from #9.
"""

from contextlib import contextmanager
import socket
from threading import Event, Thread
from time import monotonic, sleep
from typing import Callable

SIMULATED_THRESHOLD_M = 1.0


class TactileLoop(Thread):
    def __init__(self, distance: Callable[[], float], period_s: float = 0.01):
        super().__init__(daemon=True)
        self.distance, self.period_s = distance, period_s
        self.ticks: list[tuple[float, bool]] = []  # (monotonic s, vibrating)
        self._stop = Event()

    def run(self):
        next_tick = monotonic()
        while not self._stop.is_set():
            self.ticks.append((monotonic(), self.distance() < SIMULATED_THRESHOLD_M))
            next_tick += self.period_s
            sleep(max(0.0, next_tick - monotonic()))

    def stop(self):
        self._stop.set()
        self.join(5)

    def first_vibration_after(self, start: float) -> float | None:
        return next((t for t, on in self.ticks if on and t >= start), None)

    def max_gap_s(self) -> float:
        times = [t for t, _ in self.ticks]
        return max((b - a for a, b in zip(times, times[1:])), default=0.0)


@contextmanager
def hung_endpoint():
    """TCP endpoint that accepts connections and never answers (network lockup)."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    held, stop = [], Event()

    def accept():
        server.settimeout(0.1)
        while not stop.is_set():
            try:
                held.append(server.accept()[0])
            except OSError:
                continue

    thread = Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield server.getsockname()
    finally:
        stop.set()
        thread.join(2)
        for connection in held:
            connection.close()
        server.close()


def blocking_socket_call(address, timeout_s: float) -> Callable[[], None]:
    """A network task that sends a request and blocks waiting for a reply."""
    def call():
        with socket.create_connection(address, timeout=timeout_s) as connection:
            connection.sendall(b"POST /v1/inference HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\n")
            try:
                connection.recv(1)
            except socket.timeout:
                pass
    return call


def run_independence(network_task: Callable[[], object], *, period_s: float = 0.01,
                     obstacle_after_s: float = 0.3, settle_s: float = 0.2) -> dict:
    """Run the tactile loop while `network_task` blocks; an obstacle appears mid-block."""
    obstacle = Event()
    loop = TactileLoop(lambda: 0.5 if obstacle.is_set() else 3.0, period_s)
    network_started, network_ended = [None], [None]

    def network():
        network_started[0] = monotonic()
        try:
            network_task()
        except Exception:
            pass  # a failed or timed-out request is expected here
        network_ended[0] = monotonic()

    loop.start()
    worker = Thread(target=network, daemon=True)
    worker.start()
    sleep(obstacle_after_s)
    obstacle_at = monotonic()
    obstacle.set()
    sleep(settle_s)
    vibration_at = loop.first_vibration_after(obstacle_at)
    blocked_at_vibration = network_ended[0] is None or (vibration_at or 0) < network_ended[0]
    worker.join(10)
    loop.stop()
    return {
        "kind": "independent_simulation_not_hardware",
        "period_ms": period_s * 1000,
        "obstacle_to_vibration_ms": None if vibration_at is None else (vibration_at - obstacle_at) * 1000,
        "network_still_blocked_at_vibration": blocked_at_vibration,
        "network_blocked_ms": (network_ended[0] - network_started[0]) * 1000,
        "max_loop_gap_ms": loop.max_gap_s() * 1000,
        "ticks": len(loop.ticks),
    }
