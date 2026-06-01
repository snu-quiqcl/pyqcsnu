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
    """Load non-secret variables written by run_stack.sh, if present."""
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
    circuit = QuantumCircuit(2, 2, name="pyqcsnu_bell_workflow")
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


def main() -> None:
    load_local_env()

    backend = os.getenv("PYQCSNU_BACKEND", "Cassiopeia")
    shots = int(os.getenv("PYQCSNU_SHOTS", "1024"))

    client = get_client()
    circuit = build_circuit()

    print("Circuit")
    print(circuit.draw(output="text"))

    print(f"\nSubmitting to {backend} with {shots} shots...")
    result = client.run(
        circuit,
        backend=backend,
        shots=shots,
        name="pyqcsnu-qiskit-workflow-example",
        polling_interval=1,
        timeout=120,
    )

    print(f"\nQiskit Result success: {result.success}")
    print_counts_summary(result)


if __name__ == "__main__":
    main()
