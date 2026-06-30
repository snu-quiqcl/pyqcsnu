"""
Expectation value workflow using PyQCSNU and Qiskit SparsePauliOp.

Start the local backend stack first:

    cd /home/quiqclserver
    ./run_server.sh

Then run:

    cd /home/quiqclserver/pyqcsnu
    python examples/expectation_value.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pyqcsnu import SNUQ, SNUQBackend

LOCAL_BASE_URL = "http://localhost:8000"
LOCAL_USERNAME = "admin"
LOCAL_PASSWORD = "adminpassword"


def load_local_env() -> None:
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


def get_client() -> SNUQ:
    base_url = os.getenv("PYQCSNU_BASE_URL", LOCAL_BASE_URL)
    client = SNUQ(base_url=base_url)
    client.login(LOCAL_USERNAME, LOCAL_PASSWORD)
    return client


def resolve_backend(client: SNUQ) -> SNUQBackend:
    backends = client.list_backends()
    if not backends:
        raise RuntimeError("No SNUQ backends are available.")
    backend_name = os.getenv("PYQCSNU_BACKEND")
    if backend_name:
        for backend in backends:
            if backend.name == backend_name:
                return backend
        raise RuntimeError(f"Backend {backend_name!r} was not found.")
    return backends[0]


def build_circuit() -> QuantumCircuit:
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    return circuit


def main() -> None:
    load_local_env()

    client = get_client()
    backend = resolve_backend(client)
    circuit = build_circuit()
    observable = SparsePauliOp.from_list([
        ("ZZ", 1.0),
        ("XX", 0.5)
    ])

    print("Circuit")
    print(circuit.draw(output="text"))
    print(f"\nObservable: {observable}")

    expval = client.expval(circuit, observable, backend)
    print(f"\nExpectation value: {expval}")


if __name__ == "__main__":
    main()
