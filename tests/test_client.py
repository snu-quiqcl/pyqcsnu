"""
Test suite for the PyQCSNU client.
"""

import os
import pytest
import responses
from datetime import datetime
from unittest.mock import patch
from qiskit import QuantumCircuit
from qiskit.circuit.library import HGate, CXGate, RXGate

from pyqcsnu import (
    SNUQ,
    Circuit,
    Job,
    Result,
    Backend,
    MitigationParams,
    AuthenticationError,
    JobError,
    QuantumClientError
)
from pyqcsnu.exceptions import APIError

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
    assert backends[0].name == "Cassiopeia"
    assert backends[0].status == "online"
    assert backends[0].n_qubits == 5
    
    # Test backend status
    status_data = {
        "status": "online",
        "queue_length": 2,
        "estimated_wait_time": 300
    }
    
    mock_responses.add(
        responses.GET,
        f"{TEST_BASE_URL}/api/hardware/status/Cassiopeia/",
        json=status_data,
        status=200
    )
    
    status = client.get_backend_status("Cassiopeia")
    assert status["status"] == "online"
    assert status["queue_length"] == 2

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