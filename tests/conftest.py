"""
Test configuration and fixtures for PyQCSNU tests.
"""

import os
import pytest
from datetime import datetime

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    # Save original environment
    original_env = dict(os.environ)
    
    # Set test environment variables
    os.environ["PYQCSNU_BASE_URL"] = "http://0.0.0.0:8000"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def sample_circuit():
    """Create a sample Bell state circuit."""
    from pyqcsnu import Circuit
    
    return Circuit(
        qasm="""
        OPENQASM 2.0;
        include "qelib1.inc";
        
        qreg q[2];
        creg c[2];
        
        h q[0];
        cx q[0], q[1];
        
        measure q[0] -> c[0];
        measure q[1] -> c[1];
        """,
        name="bell_state"
    )

@pytest.fixture
def sample_job_data(sample_circuit):
    """Create sample job data."""
    return {
        "id": 1,
        "status": "created",
        "circuit": sample_circuit.to_dict(),
        "backend": "Cassiopeia",
        "shots": 1024,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

@pytest.fixture
def sample_result_data():
    """Create sample result data."""
    return {
        "job_id": 1,
        "counts": {
            "00": 500,
            "11": 524
        },
        "metadata": {
            "execution_time": 1.5,
            "backend": "Cassiopeia"
        }
    }

@pytest.fixture
def sample_backend_data():
    """Create sample backend data."""
    return {
        "name": "Cassiopeia",
        "status": "online",
        "n_qubits": 5,
        "capabilities": {
            "max_shots": 10000,
            "supported_gates": ["h", "cx", "x", "y", "z"]
        }
    } 