"""Qiskit backend adapter for SNUQ hardware."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from qiskit import QuantumCircuit
from qiskit.circuit import Barrier, Gate, Parameter
from qiskit.circuit.library import (
    CXGate,
    CZGate,
    HGate,
    Measure,
    RXGate,
    RYGate,
    RZGate,
    SGate,
    SdgGate,
    SwapGate,
    TGate,
    TdgGate,
    U1Gate,
    U2Gate,
    U3Gate,
    UGate,
    XGate,
    YGate,
    ZGate,
)
from qiskit.providers import BackendV2, JobStatus, JobV1
from qiskit.providers.options import Options
from qiskit.result import Result
from qiskit.transpiler import Target

from .exceptions import IonLossError, JobError
from .models import BlackholeJob, BlackholeResult, Hamiltonian, MitigationParams


_GATE_CLASSES = {
    "h": HGate,
    "x": XGate,
    "y": YGate,
    "z": ZGate,
    "s": SGate,
    "sdg": SdgGate,
    "t": TGate,
    "tdg": TdgGate,
    "rx": RXGate,
    "ry": RYGate,
    "rz": RZGate,
    "u": UGate,
    "u1": U1Gate,
    "u2": U2Gate,
    "u3": U3Gate,
    "cx": CXGate,
    "cz": CZGate,
    "swap": SwapGate,
    "measure": Measure,
    "barrier": Barrier,
}
_DEFAULT_GATE_NAMES = [
    "u",
    "u1",
    "u2",
    "u3",
    "h",
    "x",
    "y",
    "z",
    "s",
    "sdg",
    "t",
    "tdg",
    "rx",
    "ry",
    "rz",
    "cx",
    "cz",
    "swap",
    "barrier",
    "measure",
]
_CUSTOM_GATE_SPECS = {
    "gpi": (1, 1),
    "gpi2": (1, 1),
    "xx": (2, 0),
    "rxx": (2, 0),
}


class SNUQBackend(BackendV2):
    """Qiskit ``BackendV2`` wrapper for an SNUQ hardware backend."""

    def __init__(
        self,
        client=None,
        name: str = "SNUQ",
        graph_data: Optional[Dict[str, Any]] = None,
        pending_jobs: int = 0,
        active: bool = True,
        description: str = "",
        num_qubits: Optional[int] = None,
        native_gates: Optional[List[Dict[str, Any]]] = None,
        status: Optional[str] = None,
        n_qubits: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_circuits: Optional[int] = 1,
        counts_bit_order: Optional[str] = None,
        **fields,
    ):
        self._client = client
        self.graph_data = graph_data or {}
        self.pending_jobs = pending_jobs
        self.active = active
        self.status = status
        self.n_qubits = n_qubits if n_qubits is not None else num_qubits
        self.native_gates = native_gates or []
        self.controlserver_native_gates = self._controlserver_native_gate_names()
        self.metadata = metadata or {}
        self.counts_bit_order = counts_bit_order or self.metadata.get("counts_bit_order") or _default_counts_bit_order(name)
        self._num_qubits = num_qubits or n_qubits or self._infer_num_qubits()
        self._max_circuits = max_circuits
        self._target = None
        super().__init__(
            name=name,
            description=description,
            backend_version=self.metadata.get("backend_version", "0.0.1"),
            **fields,
        )

    @classmethod
    def _default_options(cls):
        options = Options(
            shots=1024,
            meas_level=2,
            meas_return="single",
            init_qubits=True,
            rep_delay=None,
            polling_interval=0.5,
            timeout=300,
            mitigation_params=None,
            name=None,
        )
        options.set_validator("shots", (1, 10_000_000))
        options.set_validator("meas_level", [1, 2])
        options.set_validator("meas_return", ["single", "avg", None])
        options.set_validator("init_qubits", bool)
        return options

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client=None) -> "SNUQBackend":
        metadata = dict(data.get("metadata", {}))
        for key, value in data.items():
            if key not in {
                "name",
                "graph_data",
                "pending_jobs",
                "active",
                "description",
                "num_qubits",
                "native_gates",
                "status",
                "n_qubits",
                "metadata",
                "counts_bit_order",
            }:
                metadata.setdefault(key, value)
        capabilities = data.get("capabilities", {})
        max_circuits = (
            data.get("max_circuits")
            or capabilities.get("max_experiments")
            or capabilities.get("max_circuits")
            or 1
        )
        max_shots = data.get("max_shots") or capabilities.get("max_shots")
        fields = {}
        if max_shots:
            fields["shots"] = min(1024, int(max_shots))
        return cls(
            client=client,
            name=data["name"],
            graph_data=data.get("graph_data", {}),
            pending_jobs=data.get("pending_jobs", 0),
            active=data.get("active", True),
            description=data.get("description", ""),
            num_qubits=data.get("num_qubits"),
            native_gates=data.get("native_gates", []),
            status=data.get("status"),
            n_qubits=data.get("n_qubits", data.get("num_qubits")),
            metadata=metadata,
            max_circuits=max_circuits,
            counts_bit_order=data.get("counts_bit_order"),
            **fields,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "graph_data": self.graph_data,
            "pending_jobs": self.pending_jobs,
            "active": self.active,
            "description": self.description,
            "num_qubits": self._num_qubits,
            "native_gates": self.native_gates,
            "status": self.status,
            "n_qubits": self.n_qubits,
            "metadata": self.metadata,
            "controlserver_native_gates": self.controlserver_native_gates,
            "counts_bit_order": self.counts_bit_order,
        }

    @property
    def target(self):
        if self._target is None:
            self._target = self._build_target()
        return self._target

    @property
    def max_circuits(self):
        return self._max_circuits

    @property
    def client(self):
        return self._client

    def bind_client(self, client) -> "SNUQBackend":
        self._client = client
        return self

    def run(self, run_input, **options):
        if self._client is None:
            raise JobError("SNUQBackend is not bound to an SNUQ client.")

        run_options = dict(self.options.__dict__)
        run_options.update(options)
        run_options.setdefault("counts_bit_order", self.counts_bit_order)

        circuits = _as_circuit_list(run_input)
        service_jobs = [
            self._client.create_job(
                circuit=circuit,
                backend=self.name,
                shots=run_options["shots"],
                mitigation_params=run_options.get("mitigation_params"),
                name=run_options.get("name") or circuit.name,
            )
            for circuit in circuits
        ]
        return SNUQJob(self, service_jobs, circuits, run_options)

    def _infer_num_qubits(self) -> int:
        graph_nodes = self.graph_data.get("nodes") or self.graph_data.get("qubits") or []
        if graph_nodes:
            return len(graph_nodes)
        capabilities = self.metadata.get("capabilities", {})
        return capabilities.get("n_qubits") or capabilities.get("num_qubits") or 0

    def _build_target(self) -> Target:
        target = Target(
            description=self.description,
            num_qubits=self._num_qubits or 0,
        )
        for gate_name in self._supported_gate_names():
            gate_class = _GATE_CLASSES.get(gate_name)
            if gate_class is None and gate_name not in _CUSTOM_GATE_SPECS:
                continue
            qargs = self._qargs_for_gate(gate_name)
            if qargs:
                instruction = _make_instruction(gate_name, gate_class, self._num_qubits)
                target.add_instruction(instruction, qargs)
        if "measure" not in target.operation_names and self._num_qubits:
            target.add_instruction(Measure(), {(idx,): None for idx in range(self._num_qubits)})
        return target

    def _supported_gate_names(self) -> List[str]:
        names = []
        for gate in self.native_gates:
            if isinstance(gate, str):
                names.append(gate)
            elif isinstance(gate, dict):
                names.append(gate.get("name") or gate.get("gate"))
        capabilities = self.metadata.get("capabilities", {})
        names.extend(capabilities.get("supported_gates", []))
        names.extend(self.controlserver_native_gates)
        normalized_name = []
        for name in names:
            if name and name.lower() not in normalized_name:
                normalized_name.append(name.lower())
        if not any(name in _GATE_CLASSES or name in _CUSTOM_GATE_SPECS for name in normalized_name):
            normalized_name = []
        for name in _DEFAULT_GATE_NAMES:
            if name not in normalized_name:
                normalized_name.append(name)
        return normalized_name

    def _qargs_for_gate(self, gate_name: str) -> Dict[tuple, None]:
        if not self._num_qubits:
            return {}
        if gate_name in {"cx", "cz", "swap", "xx", "rxx"}:
            edges = self._coupling_edges()
            if not edges:
                edges = [
                    (control, target)
                    for control in range(self._num_qubits)
                    for target in range(self._num_qubits)
                    if control != target
                ]
            return {tuple(edge): None for edge in edges}
        if gate_name == "barrier":
            return {tuple(range(self._num_qubits)): None}
        return {(idx,): None for idx in range(self._num_qubits)}

    def _coupling_edges(self) -> List[tuple]:
        edges = (
            self.graph_data.get("edges")
            or self.graph_data.get("links")
            or self.graph_data.get("coupling_map")
            or []
        )
        normalized_edge = []
        for edge in edges:
            if isinstance(edge, dict):
                source = edge.get("source", edge.get("from"))
                target = edge.get("target", edge.get("to"))
                if source is not None and target is not None:
                    normalized_edge.append((int(source), int(target)))
            elif isinstance(edge, Sequence) and len(edge) >= 2:
                normalized_edge.append((int(edge[0]), int(edge[1])))
        return normalized_edge

    def _controlserver_native_gate_names(self) -> List[str]:
        names = []
        for node in self.graph_data.get("nodes", []):
            if isinstance(node, dict):
                names.extend(node.get("supported_gates", []))
        for edge in self.graph_data.get("links", []):
            if isinstance(edge, dict) and edge.get("gate_type"):
                names.append(edge["gate_type"])
        for edge in self.graph_data.get("edges", []):
            if isinstance(edge, dict) and edge.get("gate_type"):
                names.append(edge["gate_type"])
        normalized_names = []
        for name in names:
            if name and name.lower() not in normalized_names:
                normalized_names.append(name.lower())
        return normalized_names


class SNUQJob(JobV1):
    """Qiskit job wrapper for one or more SNUQ service jobs."""

    def __init__(
        self,
        backend: SNUQBackend,
        service_jobs: List[BlackholeJob],
        circuits: List[QuantumCircuit],
        options: Dict[str, Any],
    ):
        job_id = ",".join(str(job.id) for job in service_jobs)
        super().__init__(backend=backend, job_id=job_id)
        self._service_jobs = service_jobs
        self._circuits = circuits
        self._options = options
        self._result = None
        self._error_message = None

    def submit(self):
        return None

    def result(self) -> Result:
        try:
            if self._result is None:
                experiment_results = []
                for service_job, circuit in zip(self._service_jobs, self._circuits):
                    ok, res_or_err = self.backend().client.wait_for_job(
                        job_id=service_job.id,
                        polling_interval=self._options.get("polling_interval", 0.5),
                        timeout=self._options.get("timeout", 300),
                    )
                    if not ok:
                        msg = res_or_err.get("error", "Unknown job failure")
                        if res_or_err.get("error_type") == "ion_loss":
                            raise IonLossError(f"Job {service_job.id} paused after ion loss: {msg}")
                        raise JobError(f"Job {service_job.id} failed: {msg}")
                    experiment_results.append(
                        _experiment_result_dict(
                            job=res_or_err,
                            circuit=circuit,
                            backend_name=self.backend().name,
                            options=self._options,
                        )
                    )
                self._result = Result.from_dict(
                    {
                        "backend_name": self.backend().name,
                        "backend_version": self.backend().backend_version,
                        "job_id": self.job_id(),
                        "success": True,
                        "results": experiment_results,
                    }
                )
            return self._result
        except Exception as exc:
            self._error_message = str(exc)
            raise

    def status(self) -> JobStatus:
        if self._result is not None:
            return JobStatus.DONE
        if self._error_message is not None:
            return JobStatus.ERROR
        statuses = []
        for job in self._service_jobs:
            try:
                current = self.backend().client.get_job(job.id)
            except Exception:
                statuses.append(_job_status(job.status))
                continue
            statuses.append(_job_status(current.status))
        if all(status == JobStatus.DONE for status in statuses):
            return JobStatus.DONE
        if any(status == JobStatus.ERROR for status in statuses):
            return JobStatus.ERROR
        if any(status == JobStatus.CANCELLED for status in statuses):
            return JobStatus.CANCELLED
        if any(status == JobStatus.RUNNING for status in statuses):
            return JobStatus.RUNNING
        return JobStatus.QUEUED

    def cancel(self):
        cancelled = True
        for job in self._service_jobs:
            cancelled = self.backend().client.cancel_job(job.id) and cancelled
        return cancelled

    def error_message(self):
        return self._error_message or ""


def _as_circuit_list(run_input) -> List[QuantumCircuit]:
    if isinstance(run_input, QuantumCircuit):
        return [run_input]
    if isinstance(run_input, Iterable):
        circuits = list(run_input)
        if all(isinstance(circuit, QuantumCircuit) for circuit in circuits):
            return circuits
    raise TypeError("run_input must be a QuantumCircuit or a list of QuantumCircuit objects.")


def _make_instruction(gate_name: str, gate_class, num_qubits: int):
    theta = Parameter("theta")
    phi = Parameter("phi")
    lam = Parameter("lambda")
    if gate_name in _CUSTOM_GATE_SPECS:
        gate_qubits, param_count = _CUSTOM_GATE_SPECS[gate_name]
        params = [Parameter(f"theta_{idx}") for idx in range(param_count)]
        return Gate(gate_name, gate_qubits, params)
    if gate_name in {"rx", "ry", "rz", "u1"}:
        return gate_class(theta)
    if gate_name == "u2":
        return gate_class(phi, lam)
    if gate_name in {"u", "u3"}:
        return gate_class(theta, phi, lam)
    if gate_name == "barrier":
        return gate_class(num_qubits)
    return gate_class()


def _experiment_result_dict(
    job: Union[BlackholeJob, BlackholeResult],
    circuit: QuantumCircuit,
    backend_name: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    processed_results = _processed_results(job)
    if "counts" not in processed_results:
        raise JobError(f"Job {_service_job_id(job)} completed without counts in processed_results")
    counts = normalize_counts_for_qiskit(
        processed_results["counts"],
        circuit,
        source_bit_order=options.get("counts_bit_order", "qiskit"),
    )
    header = {
        "name": options.get("name") or circuit.name or f"SNUQ-run-{datetime.now(timezone.utc).isoformat()}",
        "memory_slots": circuit.num_clbits,
        "n_qubits": circuit.num_qubits,
        "metadata": circuit.metadata or {},
    }
    return {
        "shots": options["shots"],
        "status": "DONE",
        "success": True,
        "meas_level": options.get("meas_level", 2),
        "meas_return": options.get("meas_return"),
        "header": header,
        "data": {
            "counts": counts,
        },
        "backend_name": backend_name,
    }


def normalize_counts_for_qiskit(
    counts: Dict[str, int],
    circuit: QuantumCircuit,
    source_bit_order: str = "qiskit",
) -> Dict[str, int]:
    """Project service count strings onto Qiskit's classical-bit display order."""
    if not counts or circuit.num_clbits == 0:
        return {key: int(value) for key, value in counts.items()}

    measurement_map = _measurement_map(circuit)
    if not measurement_map:
        return {key: int(value) for key, value in counts.items()}

    normalized: Dict[str, int] = {}
    for raw_key, value in counts.items():
        key = str(raw_key).replace(" ", "")
        if not key or any(bit not in "01" for bit in key):
            normalized[str(raw_key)] = normalized.get(str(raw_key), 0) + int(value)
            continue

        if (
            source_bit_order == "qiskit"
            and len(key) == circuit.num_clbits
            and _is_identity_measurement(measurement_map)
        ):
            normalized[key] = normalized.get(key, 0) + int(value)
            continue

        classical_bits = ["0"] * circuit.num_clbits
        for qubit_index, clbit_index in measurement_map.items():
            if source_bit_order == "hardware":
                source_index = qubit_index
            else:
                source_index = len(key) - 1 - qubit_index
            target_index = circuit.num_clbits - 1 - clbit_index
            if 0 <= source_index < len(key) and 0 <= target_index < circuit.num_clbits:
                classical_bits[target_index] = key[source_index]
        normalized_key = "".join(classical_bits)
        normalized[normalized_key] = normalized.get(normalized_key, 0) + int(value)
    return normalized


def _measurement_map(circuit: QuantumCircuit) -> Dict[int, int]:
    mapping = {}
    for instruction in circuit.data:
        operation = getattr(instruction, "operation", instruction[0])
        if operation.name != "measure":
            continue
        qubits = getattr(instruction, "qubits", instruction[1])
        clbits = getattr(instruction, "clbits", instruction[2])
        if not qubits or not clbits:
            continue
        qubit_index = circuit.find_bit(qubits[0]).index
        clbit_index = circuit.find_bit(clbits[0]).index
        mapping[qubit_index] = clbit_index
    return mapping


def _is_identity_measurement(measurement_map: Dict[int, int]) -> bool:
    return all(qubit == clbit for qubit, clbit in measurement_map.items())


def _default_counts_bit_order(backend_name: str) -> str:
    if "simulator" in (backend_name or "").lower():
        return "qiskit"
    return "hardware"


def _processed_results(job: Union[BlackholeJob, BlackholeResult]) -> Dict[str, Any]:
    if isinstance(job, BlackholeResult):
        return job.results or {}
    return job.processed_results or {}


def _service_job_id(job: Union[BlackholeJob, BlackholeResult]):
    return job.job_id if isinstance(job, BlackholeResult) else job.id


def _job_status(status: str) -> JobStatus:
    normalized_status = (status or "").lower()
    if normalized_status in {"completed", "done"}:
        return JobStatus.DONE
    if normalized_status in {"running", "executing"}:
        return JobStatus.RUNNING
    if normalized_status in {"cancelled", "canceled"}:
        return JobStatus.CANCELLED
    if normalized_status in {"error", "failed", "ion_lost", "mode_interrupted"}:
        return JobStatus.ERROR
    if normalized_status in {"created", "pending", "queued"}:
        return JobStatus.QUEUED
    return JobStatus.INITIALIZING


def ensure_backend(backend: Union[SNUQBackend, str], client=None) -> SNUQBackend:
    """Validate or adapt a backend argument."""
    if isinstance(backend, SNUQBackend):
        if backend.client is None and client is not None:
            backend.bind_client(client)
        return backend
    raise TypeError("backend must be an SNUQBackend instance.")
