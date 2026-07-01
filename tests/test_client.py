"""
Test suite for the PyQCSNU client.
"""

import os
import pytest
import responses
from datetime import datetime
from unittest.mock import patch
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import HGate, CXGate, RXGate
from qiskit.providers import BackendV2, JobV1

from pyqcsnu import (
    SNUQ,
    SNUQBackend,
    Circuit,
    Job,
    Result,
    Backend,
    MitigationParams,
    AuthenticationError,
    JobError,
    BackendError,
    QuantumClientError
)
from pyqcsnu.exceptions import APIError
from pyqcsnu.backend import normalize_counts_for_qiskit

# Test data
TEST_TOKEN = "e9df270d2fc9ae6118cfaa00f7d295676d983b10"
TEST_USERNAME = "admin"
TEST_PASSWORD = "adminpassword"
TEST_BASE_URL = "http://0.0.0.0:8000"

# Sample circuit
BELL_CIRCUIT = """
OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

h q[0];
cx q[0], q[1];

measure q[0] -> c[0];
measure q[1] -> c[1];
"""

@pytest.fixture
def client():
    """Create a test client instance with token."""
    return SNUQ(base_url=TEST_BASE_URL, token=TEST_TOKEN)

@pytest.fixture
def mock_responses():
    """Setup mock responses for API calls."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps

def test_client_initialization():
    """Test client initialization with different configurations."""
    # Test with custom base URL
    client = SNUQ(base_url=TEST_BASE_URL)
    assert client.base_url == TEST_BASE_URL.rstrip('/')
    
    # Test with environment variable
    os.environ["PYQCSNU_BASE_URL"] = TEST_BASE_URL
    client = SNUQ()
    assert client.base_url == TEST_BASE_URL.rstrip('/')
    del os.environ["PYQCSNU_BASE_URL"]
    
    # Test with token
    client = SNUQ(token=TEST_TOKEN)
    assert client.token == TEST_TOKEN
    assert client.session.headers["Authorization"] == f"Token {TEST_TOKEN}"

def test_login_with_username_password(client, mock_responses):
    """Test login with username and password."""
    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/token/",
        json={"token": TEST_TOKEN},
        status=200
    )
    
    assert client.login(TEST_USERNAME, TEST_PASSWORD)
    assert client.token == TEST_TOKEN
    assert client.session.headers["Authorization"] == f"Token {TEST_TOKEN}"

def test_login_with_token(client, mock_responses):
    """Test login with token."""
    # Mock successful token validation
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/backends/",
        json=[],
        status=200
    )
    
    client.login_with_token(TEST_TOKEN)
    assert client.token == TEST_TOKEN
    assert client.session.headers["Authorization"] == f"Token {TEST_TOKEN}"

def test_login_with_invalid_token(client, mock_responses):
    """Test login with invalid token."""
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/backends/",
        json={"error": "Invalid token"},
        status=401
    )
    
    with pytest.raises(AuthenticationError):
        client.login_with_token("invalid-token")
    assert client.token is None
    assert "Authorization" not in client.session.headers

def test_create_job(client, mock_responses):
    """Test job creation."""
    circuit = Circuit.from_qasm(BELL_CIRCUIT, name="bell_state")
    job_data = {
        "id": 1,
        "status": "created",
        "circuit": circuit.to_dict(),
        "backend": "Cassiopeia",
        "shots": 1024,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/runner/jobs/create/",
        json=job_data,
        status=200
    )
    
    job = client.create_job(
        circuit=circuit,
        backend="Cassiopeia",
        shots=1024
    )
    
    assert isinstance(job, Job)
    assert job.id == 1
    assert job.status == "created"
    assert job.backend == "Cassiopeia"
    assert job.shots == 1024

def test_create_job_with_mitigation(client, mock_responses):
    """Test job creation with error mitigation."""
    circuit = Circuit.from_qasm(BELL_CIRCUIT, name="bell_state")
    mitigation = MitigationParams(
        technique="zne",
        params={"scale_factors": [1.0, 2.0, 3.0]}
    )
    
    job_data = {
        "id": 1,
        "status": "created",
        "circuit": circuit.to_dict(),
        "backend": "Cassiopeia",
        "shots": 1024,
        "mitigation_params": mitigation.to_dict(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/runner/jobs/create/",
        json=job_data,
        status=200
    )
    
    job = client.create_job(
        circuit=circuit,
        backend="Cassiopeia",
        shots=1024,
        mitigation_params=mitigation
    )
    
    assert job.mitigation_params is not None
    assert job.mitigation_params.technique == "zne"

def test_list_jobs(client, mock_responses):
    """Test listing jobs."""
    circuit = Circuit.from_qasm(BELL_CIRCUIT, name="bell_state")
    jobs_data = [
        {
            "id": 1,
            "status": "completed",
            "circuit": circuit.to_dict(),
            "backend": "Cassiopeia",
            "shots": 1024,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        },
        {
            "id": 2,
            "status": "running",
            "circuit": circuit.to_dict(),
            "backend": "Cassiopeia",
            "shots": 1024,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
    ]
    
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/",
        json=jobs_data,
        status=200
    )
    
    jobs = client.list_jobs()
    assert len(jobs) == 2
    assert all(isinstance(job, Job) for job in jobs)
    assert jobs[0].status == "completed"
    assert jobs[1].status == "running"

def test_get_job_results(client, mock_responses):
    """Test getting job results."""
    result_data = {
        "job_id": 1,
        "counts": {
            "00": 500,
            "11": 524
        },
        "metadata": {
            "execution_time": 1.5
        }
    }
    
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/1/results/",
        json=result_data,
        status=200
    )
    
    result = client.get_job_results(1)
    assert isinstance(result, Result)
    assert result.job_id == 1
    assert result.counts["00"] == 500
    assert result.counts["11"] == 524
    
    # Test result processing methods
    assert result.get_probability("00") == pytest.approx(0.488, rel=1e-3)
    assert result.get_probability("11") == pytest.approx(0.512, rel=1e-3)
    
    # Test expectation value calculation
    observable = {
        "00": 1.0,
        "11": 1.0,
        "01": -1.0,
        "10": -1.0
    }
    expectation = result.get_expectation_value(observable)
    assert expectation == pytest.approx(1.0, rel=1e-3)

def test_wait_for_job(client, mock_responses):
    """Test waiting for job completion."""
    # Mock job status progression
    statuses = ["created", "running", "completed"]
    circuit = Circuit.from_qasm(BELL_CIRCUIT, name="bell_state")
    job_data = {
        "id": 1,
        "circuit": circuit.to_dict(),
        "backend": "Cassiopeia",
        "shots": 1024,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    for status in statuses:
        job_data["status"] = status
        mock_responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/api/runner/jobs/1/",
            json=job_data,
            status=200
        )
    
    # Mock final results
    result_data = {
        "job_id": 1,
        "counts": {"00": 500, "11": 524}
    }
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/1/results/",
        json=result_data,
        status=200
    )
    
    # Test with status callback
    status_updates = []
    def status_callback(status, job_data):
        status_updates.append(status)
    
    success, result = client.wait_for_job(
        job_id=1,
        polling_interval=0.1,
        timeout=1.0,
        status_callback=status_callback
    )
    
    assert success
    assert isinstance(result, Result)
    assert status_updates == ["created", "running", "completed"]

def test_error_handling(client, mock_responses):
    """Test error handling for various scenarios."""
    # Test authentication error
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/",
        json={"error": "Authentication failed"},
        status=401
    )
    
    with pytest.raises(AuthenticationError):
        client.list_jobs()
    
    # Test job error
    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/runner/jobs/create/",
        json={"error": "Invalid circuit"},
        status=400
    )
    
    with pytest.raises(JobError):
        # Create an invalid circuit
        circuit = Circuit(
            name="invalid_circuit",
            num_qubits=2,
            gates=[{"name": "invalid_gate", "qubits": [0, 1]}]
        )
        client.create_job(circuit=circuit, backend="Cassiopeia")
    
    # Test server error
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/backends/",
        json={"error": "Internal server error"},
        status=500
    )
    
    with pytest.raises(QuantumClientError):
        client.list_backends()

def test_backend_management(client, mock_responses):
    """Test backend management functionality."""
    backends_data = [
        {
            "name": "Cassiopeia",
            "status": "online",
            "n_qubits": 5,
            "capabilities": {
                "max_shots": 10000,
                "supported_gates": ["h", "cx", "x", "y", "z"]
            }
        }
    ]
    
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/backends/",
        json=backends_data,
        status=200
    )
    
    backends = client.list_backends()
    assert len(backends) == 1
    assert isinstance(backends[0], Backend)
    assert isinstance(backends[0], BackendV2)
    assert backends[0].name == "Cassiopeia"
    assert backends[0].status == "online"
    assert backends[0].n_qubits == 5
    assert "cx" in backends[0].operation_names
    
    # Test backend status
    status_data = {
        "status": "online",
        "queue_length": 2,
        "estimated_wait_time": 300
    }
    
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/status/?name=Cassiopeia",
        json=status_data,
        status=200
    )
    
    status = client.get_backend_status("Cassiopeia")
    assert status["status"] == "online"
    assert status["queue_length"] == 2

def test_get_backend(client, mock_responses):
    """Test retrieving a backend object by name."""
    backends_data = [
        {
            "name": "Cassiopeia",
            "status": "online",
            "n_qubits": 5,
            "capabilities": {
                "max_shots": 10000,
                "supported_gates": ["h", "cx", "x", "y", "z"],
            },
        }
    ]

    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/backends/",
        json=backends_data,
        status=200,
    )
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/backends/",
        json=backends_data,
        status=200,
    )

    assert client.get_backend().name == "Cassiopeia"
    assert client.get_backend("Cassiopeia").name == "Cassiopeia"

def test_get_backend_requires_name_when_multiple(client, mock_responses):
    """Test that unnamed backend lookup is rejected when multiple are available."""
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/backends/",
        json=[
            {"name": "Cassiopeia", "n_qubits": 5},
            {"name": "Trinity", "n_qubits": 2},
        ],
        status=200,
    )

    with pytest.raises(BackendError):
        client.get_backend()

def test_create_job_with_qiskit_circuit(client, mock_responses):
    """Test creating a job with a Qiskit circuit."""
    # Create a simple Qiskit circuit
    qc = QuantumCircuit(2, name="test_circuit")
    qc.h(0)
    qc.cx(0, 1)
    qc.rx(0.5, 0)
    
    # Mock the job creation response
    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/runner/jobs/create/",
        json={
            "id": "test-job-1",
            "status": "pending",
            "circuit": Circuit.from_qiskit(qc).to_dict(),
            "backend": "test_backend",
            "shots": 1000,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        },
        status=201
    )
    
    # Create job with Qiskit circuit
    job = client.create_job(
        circuit=qc,
        backend="test_backend",
        shots=1000,
        name="test_job"
    )
    
    assert isinstance(job, Job)
    assert job.id == "test-job-1"
    assert job.status == "pending"
    assert job.backend == "test_backend"
    assert job.shots == 1000
    
    # Verify the circuit was converted correctly
    circuit = Circuit.from_qiskit(qc)
    assert len(circuit.gates) == 3
    assert circuit.gates[0]["name"] == "h"
    assert circuit.gates[1]["name"] == "cx"
    assert circuit.gates[2]["name"] == "rx"
    assert circuit.gates[2]["params"][0]["value"] == 0.5

def test_circuit_conversion():
    """Test conversion between Qiskit and our Circuit format."""
    # Create a Qiskit circuit with various gates
    qc = QuantumCircuit(3, name="conversion_test")
    qc.h(0)
    qc.cx(0, 1)
    qc.rx(0.5, 0)
    qc.ry(0.3, 1)
    qc.rz(0.7, 2)
    qc.swap(0, 2)
    
    # Convert to our format
    circuit = Circuit.from_qiskit(qc)
    assert circuit.name == "conversion_test"
    assert circuit.num_qubits == 3
    assert len(circuit.gates) == 6
    
    # Convert back to Qiskit
    qc2 = circuit.to_qiskit()
    assert qc2.num_qubits == 3
    assert len(qc2.data) == 6
    
    # Verify gates
    assert qc2.data[0][0].name == "h"
    assert qc2.data[1][0].name == "cx"
    assert qc2.data[2][0].name == "rx"
    assert qc2.data[2][0].params[0] == 0.5
    assert qc2.data[3][0].name == "ry"
    assert qc2.data[3][0].params[0] == 0.3
    assert qc2.data[4][0].name == "rz"
    assert qc2.data[4][0].params[0] == 0.7
    assert qc2.data[5][0].name == "swap"

def test_circuit_with_parameters():
    """Test circuit conversion with parameterized gates."""
    from qiskit.circuit import Parameter
    
    # Create a parameterized circuit
    theta = Parameter('θ')
    phi = Parameter('φ')
    qc = QuantumCircuit(2, name="parameterized")
    qc.rx(theta, 0)
    qc.ry(phi, 1)
    qc.cx(0, 1)
    
    # Convert to our format
    circuit = Circuit.from_qiskit(qc)
    assert len(circuit.parameters) == 2
    assert 'θ' in circuit.parameters
    assert 'φ' in circuit.parameters
    
    # Set parameter values
    circuit.parameters['θ'] = 0.5
    circuit.parameters['φ'] = 0.3
    
    # Convert back to Qiskit
    qc2 = circuit.to_qiskit()
    assert qc2.data[0][0].params[0] == 0.5
    assert qc2.data[1][0].params[0] == 0.3 

def test_run_requires_snuq_backend(client):
    """Test that client.run expects an SNUQBackend instance."""
    qc = QuantumCircuit(1, 1)
    qc.measure(0, 0)

    with pytest.raises(TypeError):
        client.run(qc, backend="Cassiopeia")

def test_client_run_with_snuq_backend(client, mock_responses):
    """Test running a circuit with an SNUQBackend instance."""
    backend = SNUQBackend(
        client=client,
        name="Cassiopeia",
        n_qubits=1,
        metadata={"capabilities": {"supported_gates": ["measure"]}},
    )
    qc = QuantumCircuit(1, 1, name="client_run")
    qc.measure(0, 0)

    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/runner/jobs/create/",
        json={
            "id": 7,
            "status": "created",
            "circuit": Circuit.from_qiskit(qc).to_dict(),
            "backend": "Cassiopeia",
            "shots": 128,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        status=201,
    )
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/7/",
        json={
            "id": 7,
            "status": "completed",
            "circuit": Circuit.from_qiskit(qc).to_dict(),
            "backend": "Cassiopeia",
            "shots": 128,
            "processed_results": {"counts": {"0": 80, "1": 48}},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        status=200,
    )

    result = client.run(qc, backend=backend, shots=128)

    assert result.backend_name == "Cassiopeia"
    assert result.get_counts() == {"0": 80, "1": 48}
    assert result.results[0].meas_level == 2

def test_snuq_backend_run_returns_qiskit_job(client, mock_responses):
    """Test BackendV2.run returns a Qiskit job and supports circuit lists."""
    backend = SNUQBackend(client=client, name="Cassiopeia", n_qubits=1)
    circuits = []
    for idx in range(2):
        qc = QuantumCircuit(1, 1, name=f"backend_run_{idx}")
        qc.measure(0, 0)
        circuits.append(qc)

    for idx, qc in enumerate(circuits, start=1):
        mock_responses.add(
            responses.POST,
            f"{TEST_BASE_URL}/api/runner/jobs/create/",
            json={
                "id": idx,
                "status": "created",
                "circuit": Circuit.from_qiskit(qc).to_dict(),
                "backend": "Cassiopeia",
                "shots": 64,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            status=201,
        )
        mock_responses.add(
            responses.GET,
            f"{TEST_BASE_URL}/api/runner/jobs/{idx}/",
            json={
                "id": idx,
                "status": "completed",
                "circuit": Circuit.from_qiskit(qc).to_dict(),
                "backend": "Cassiopeia",
                "shots": 64,
                "processed_results": {"counts": {"0": 64 - idx, "1": idx}},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            status=200,
        )

    job = backend.run(circuits, shots=64)
    result = job.result()

    assert isinstance(job, JobV1)
    assert job.backend() is backend
    assert result.job_id == "1,2"
    assert len(result.results) == 2
    assert result.get_counts(0) == {"0": 63, "1": 1}
    assert result.get_counts(1) == {"0": 62, "1": 2}

def test_snuq_backend_job_result_reads_results_endpoint(client, mock_responses):
    """Test BackendV2 job result handles completed jobs without inline results."""
    backend = SNUQBackend(client=client, name="TISimulator", n_qubits=1)
    qc = QuantumCircuit(1, 1, name="results_endpoint")
    qc.metadata = {"ideal_probabilities": {"0": 1.0}}
    qc.measure(0, 0)

    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/runner/jobs/create/",
        json={
            "id": 9,
            "status": "created",
            "circuit": Circuit.from_qiskit(qc).to_dict(),
            "backend": "TISimulator",
            "shots": 32,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        status=201,
    )
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/9/",
        json={
            "id": 9,
            "status": "completed",
            "circuit": Circuit.from_qiskit(qc).to_dict(),
            "backend": "TISimulator",
            "shots": 32,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        status=200,
    )
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/9/results/",
        json={
            "job_id": 9,
            "backend": "TISimulator",
            "shots": 32,
            "processed_results": {"counts": {"0": 30, "1": 2}},
        },
        status=200,
    )

    result = backend.run(qc, shots=32).result()

    assert result.get_counts() == {"0": 30, "1": 2}
    assert result.results[0].header["metadata"] == {"ideal_probabilities": {"0": 1.0}}

def test_snuq_backend_job_status_done_after_result(client, mock_responses):
    """Test completed job remains DONE even if later status polling fails."""
    backend = SNUQBackend(client=client, name="TISimulator", n_qubits=1)
    qc = QuantumCircuit(1, 1)
    qc.measure(0, 0)

    mock_responses.add(
        responses.POST,
        f"{TEST_BASE_URL}/api/runner/jobs/create/",
        json={
            "id": 10,
            "status": "created",
            "circuit": Circuit.from_qiskit(qc).to_dict(),
            "backend": "TISimulator",
            "shots": 16,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        status=201,
    )
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/runner/jobs/10/",
        json={
            "id": 10,
            "status": "completed",
            "circuit": Circuit.from_qiskit(qc).to_dict(),
            "backend": "TISimulator",
            "shots": 16,
            "processed_results": {"counts": {"0": 16}},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
        status=200,
    )

    job = backend.run(qc, shots=16)
    job.result()

    assert job.status().name == "DONE"

def test_snuq_backend_target_supports_common_transpiler_output():
    """Test target accepts u/cx/barrier/measure circuits."""
    backend = SNUQBackend(
        name="Cassiopeia",
        n_qubits=3,
        native_gates=[{"unexpected": "shape"}],
    )
    qc = QuantumCircuit(3, 3)
    qc.u(0.1, 0.2, 0.3, 0)
    qc.cx(0, 1)
    qc.barrier()
    qc.measure([0, 1, 2], [0, 1, 2])

    transpiled = transpile(qc, backend=backend)

    assert {"u", "cx", "barrier", "measure"}.issubset(set(backend.operation_names))
    assert transpiled.num_qubits == 3

def test_snuq_backend_reads_controlserver_native_graph_data():
    """Test native gates and links are read from controlserver graph_data."""
    backend = SNUQBackend(
        name="TISimulator",
        graph_data={
            "nodes": [
                {"id": 0, "supported_gates": ["gpi", "gpi2", "measure"]},
                {"id": 1, "supported_gates": ["gpi", "gpi2", "measure"]},
            ],
            "links": [
                {"source": 0, "target": 1, "gate_type": "xx"},
            ],
        },
    )

    assert backend.controlserver_native_gates == ["gpi", "gpi2", "measure", "xx"]
    assert {"gpi", "gpi2", "xx", "measure"}.issubset(set(backend.operation_names))
    assert {"u", "cx"}.issubset(set(backend.operation_names))
    assert list(backend.coupling_map.get_edges()) == [(0, 1)]

def test_counts_are_projected_to_classical_width():
    """Test full-device simulator counts are projected to measured clbits."""
    qc = QuantumCircuit(5, 3)
    qc.measure([0, 1, 2], [0, 1, 2])

    counts = normalize_counts_for_qiskit(
        {
            "00000": 1,
            "00001": 2,
            "00010": 4,
            "00100": 8,
            "10000": 16,
        },
        qc,
    )

    assert counts == {
        "000": 17,
        "001": 2,
        "010": 4,
        "100": 8,
    }

def test_counts_projection_respects_measurement_mapping():
    """Test count projection follows qargs to cargs mapping."""
    qc = QuantumCircuit(5, 3)
    qc.measure(2, 0)
    qc.measure(0, 2)

    counts = normalize_counts_for_qiskit(
        {
            "00001": 3,
            "00100": 5,
            "00101": 7,
        },
        qc,
    )

    assert counts == {
        "100": 3,
        "001": 5,
        "101": 7,
    }

def test_hardware_order_counts_are_reversed_to_qiskit_display_order():
    """Test Trinity/PMT-style q0q1q2 keys become Qiskit c2c1c0 keys."""
    qc = QuantumCircuit(3, 3)
    qc.measure([0, 1, 2], [0, 1, 2])

    counts = normalize_counts_for_qiskit(
        {
            "100": 3,
            "010": 5,
            "001": 7,
        },
        qc,
        source_bit_order="hardware",
    )

    assert counts == {
        "001": 3,
        "010": 5,
        "100": 7,
    }

def test_qiskit_order_counts_remain_unchanged_for_simulator_width_counts():
    """Test TISimulator-style qiskit display keys are not reversed."""
    qc = QuantumCircuit(3, 3)
    qc.measure([0, 1, 2], [0, 1, 2])

    counts = normalize_counts_for_qiskit(
        {
            "001": 3,
            "010": 5,
            "100": 7,
        },
        qc,
        source_bit_order="qiskit",
    )

    assert counts == {
        "001": 3,
        "010": 5,
        "100": 7,
    }
