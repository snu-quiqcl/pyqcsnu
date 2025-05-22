# PyQCSNU

Python packages for accessing QuIQCL quantum services

## Installation

```bash
pip install pyqcsnu
```

For development installation:

```bash
git clone https://github.com/snu-quiqcl/pyqcsnu.git
cd pyqcsnu
pip install -e ".[dev]"
```

## Configuration

The client can be configured in several ways:

1. **Base URL Configuration**:
   - Pass directly to client: `client = QuantumClient(base_url="https://api.example.com")`
   - Set environment variable: `export PYQCSNU_BASE_URL="https://api.example.com"`
   - Default: `http://localhost:8000`

2. **Authentication**:
   - Login with username/password: `client.login(username="user", password="pass")`
   - Login with token: `client.login_with_token(token="your-token")`
   - Set token during initialization: `client = QuantumClient(token="your-token")`

## Quick Start

```python
from pyqcsnu import QuantumClient, Circuit

# Initialize the client (base URL can be configured via environment variable)
client = QuantumClient()

# Login using one of these methods:
# 1. Username/password
client.login(username="your_username", password="your_password")

# 2. Token
client.login_with_token(token="your-token")

# Create a simple Bell state circuit
bell_circuit = Circuit(
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

# Submit the job
job = client.create_job(
    circuit=bell_circuit,
    backend="cassiopeia",
    shots=1024
)

# Wait for results with status updates
def status_callback(status, job_data):
    print(f"Job status: {status}")

success, result = client.wait_for_job(
    job_id=job.id,
    polling_interval=5,
    timeout=300,
    status_callback=status_callback
)

if success:
    # Get probabilities for each state
    for bitstring in ["00", "01", "10", "11"]:
        prob = result.get_probability(bitstring)
        print(f"P({bitstring}) = {prob:.4f}")
    
    # Calculate expectation value for Z⊗Z
    observable = {
        "00": 1.0,
        "01": -1.0,
        "10": -1.0,
        "11": 1.0
    }
    expectation = result.get_expectation_value(observable)
    print(f"⟨Z⊗Z⟩ = {expectation:.4f}")
```

## Features

- **Easy-to-use API**: Simple and intuitive interface for quantum computing operations
- **Type Safety**: Full type hints and validation
- **Error Handling**: Comprehensive error handling with custom exceptions
- **Async Support**: Built-in support for asynchronous operations
- **Result Processing**: Built-in methods for common quantum computing calculations
- **Backend Management**: Easy access to backend status and capabilities

## Advanced Usage

### Error Mitigation

```python
from pyqcsnu import MitigationParams

# Create a job with error mitigation
mitigation = MitigationParams(
    technique="zne",
    params={
        "scale_factors": [1.0, 2.0, 3.0],
        "extrapolator": "linear"
    }
)

job = client.create_job(
    circuit=circuit,
    backend="cassiopeia",
    shots=1024,
    mitigation_params=mitigation
)
```

### Experiment Management

```python
# Create a pulse-level experiment
experiment = client.create_experiment(
    pulse_schedule={
        "channels": ["ch0", "ch1"],
        "instructions": [
            {"name": "delay", "t": 0, "duration": 100},
            {"name": "pulse", "channel": "ch0", "t": 100, "duration": 50}
        ]
    },
    external_run_id=12345
)

# Get experiment status
experiment = client.get_experiment(experiment.id)
print(f"Experiment status: {experiment.status}")
```

### Backend Management

```python
# List available backends
backends = client.list_backends()
for backend in backends:
    print(f"Backend: {backend.name}")
    print(f"Status: {backend.status}")
    print(f"Qubits: {backend.n_qubits}")
    print("---")

# Get backend calibration data
calibration = client.get_backend_calibration("cassiopeia")
print("Calibration data:", calibration)
```

## Development

### Running Tests

```bash
pytest
```

### Code Style

```bash
# Format code
black .
isort .

# Type checking
mypy .

# Linting
flake8
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
