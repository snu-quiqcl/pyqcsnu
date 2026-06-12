"""
Qiskit workflow using PyQCSNU as the execution backend.

Start the local backend stack first:

    cd /home/quiqclserver
    ./run_server.sh --mock-proxy

Then run this example:

    cd /home/quiqclserver/pyqcsnu
    python examples/example.py

The mock proxy currently returns simulated PMT-count data, so this example is
best treated as an end-to-end integration workflow rather than a physics
validation of the circuit state.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

from qiskit import QuantumCircuit
from qiskit.result import Result

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pyqcsnu import SNUQ

LOCAL_BASE_URL = "http://localhost:8000"
LOCAL_USERNAME = "admin"
LOCAL_PASSWORD = "adminpassword"


def load_local_env() -> None:
    """Load non-secret variables written by run_server.sh, if present."""
    env_path = PROJECT_ROOT / ".env.local"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_circuit() -> QuantumCircuit:
    """Build a small circuit using normal Qiskit APIs."""
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    return circuit


def get_client() -> SNUQ:
    """Create an authenticated PyQCSNU client for the local controlserver."""
    base_url = os.getenv("PYQCSNU_BASE_URL", LOCAL_BASE_URL)
    client = SNUQ(base_url=base_url)
    client.login(LOCAL_USERNAME, LOCAL_PASSWORD)
    return client


def print_counts_summary(result: Result) -> None:
    """Print counts and a compact probability summary."""
    counts = result.get_counts()
    shots = sum(counts.values())
    ranked_counts = Counter(counts).most_common()

    print("\nCounts")
    for bitstring, count in ranked_counts:
        probability = count / shots if shots else 0.0
        print(f"  {bitstring:>8}: {count:5d} ({probability:.3f})")

    if ranked_counts:
        print(f"\nMost frequent outcome: {ranked_counts[0][0]}")


def print_hardware_status(client: SNUQ) -> None:
    """Print configured hardware backends and their live controlserver status."""
    backends = client.list_backends()

    print("\nHardware")
    print(f"  {'name':<16} {'active':<8} {'mode':<12} {'pending':<8} status")
    print(f"  {'-' * 16} {'-' * 8} {'-' * 12} {'-' * 8} {'-' * 16}")

    for backend in backends:
        try:
            status = client.get_backend_status(backend.name)
        except Exception as exc:
            print(f"  {backend.name:<16} {'?':<8} {'?':<12} {backend.pending_jobs:<8} error: {exc}")
            continue

        active = status.get("active", "?")
        mode = status.get("mode", status.get("system_mode", "?"))
        pending_jobs = status.get("pending_jobs", backend.pending_jobs)
        status_text = status.get("status", "ok")
        print(f"  {backend.name:<16} {str(active):<8} {str(mode):<12} {pending_jobs:<8} {status_text}")


def main() -> None:
    load_local_env()

    backend = "Trinity"

    client = get_client()
    print_hardware_status(client)

    circuit = build_circuit()

    print("Circuit")
    print(circuit.draw(output="text"))

    print(f"\nSubmitting to {backend}...")
    result = client.run(
        circuit,
        backend=backend,
    )

    print(f"\nQiskit Result success: {result.success}")
    print_counts_summary(result)


if __name__ == "__main__":
    main()
