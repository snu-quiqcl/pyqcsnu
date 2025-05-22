# pyqcsnu

*A Python client for QuIQCL Quantum‑Computing Services*

---

`pyqcsnu` lets you talk to the REST API that powers QuIQCL
quantum‑computing cluster from pure Python.  With a single import you can

* authenticate against the service,
* submit **Qiskit** circuits as jobs,
* block until the run is finished,
* and receive results in `qiskit.result.Result` format—ready for all downstream
  Qiskit tooling.

---

## Features

| Capability                       | What it means for you                                                                           |
| -------------------------------- | ----------------------------------------------------------------------------------------------- |
| **Plug‑and‑play Qiskit support** | Pass a `QuantumCircuit`, get back a `Result`.                                                   |
| **High‑level `run()` helper**    | One call: *submit → wait → fetch → convert*.                                                    |
| **Explicit low‑level API**       | Fine‑grained control via `create_job`, `wait_for_job`, `get_job_results`, …                     |
| **Typed data models**            | `pydantic` models (`BlackholeJob`, `BlackholeResult`, …) for safe parsing & IDE autocompletion. |
| **Error classes**                | Clear exception hierarchy: `AuthenticationError`, `JobError`, …                                 |

---

## Installation

```bash
pip install pyqcsnu
```

Requires **Python 3.9+** and a network path to the SNU QC service.

---

## Quick start

```python
from qiskit import QuantumCircuit
from pyqcsnu import SNUQ

# 1  Connect & authenticate
client = SNUQ()
client.login("userid", "userpw")    # or via endowed TOKEN

# 2  Build a circuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

# 3  Run & get a Qiskit Result
result = client.run(qc, backend="Cassiopeia", shots=2048)
print(result.get_counts())  # {'00': 1012, '11': 1036}
```

---

## Library layout

```
pyqcsnu/
├── client.py   # SNUQ: the main API client
└── models.py   # Pydantic data models used throughout
```

### `SNUQ` essentials

| Method                        | Purpose                                             |
| ----------------------------- | --------------------------------------------------- |
| `login(username, password)`   | Obtain a token and store it for subsequent calls    |
| `login_with_token(token)`     | Skip username/password; validate an existing token  |
| `run(circuit, backend, **kw)` | One‑shot helper that returns `qiskit.result.Result` |
| `create_job(...)`             | Submit without waiting                              |
| `wait_for_job(job_id, ...)`   | Poll until *completed*/ *error*/ *timeout*          |
| `get_job_results(job_id)`     | Fetch `BlackholeResult` only                        |

### Data models (in `models.py`)

* `BlackholeJob`       – job metadata & status
* `BlackholeResult`    – counts / probabilities / metadata
* `BlackholeExperiment`– low‑level pulse‑level run information
* `SNUBackend`         – static & live backend specs
* `MitigationParams`   – optional error‑mitigation settings

Each model is a Pydantic `BaseModel`, so you can `.model_dump()` them straight
to JSON or build them via `.model_validate()`.

---

## Advanced usage

### Submit now, fetch later

```python
job = client.create_job(qc, backend="ion_trap_5q", shots=5000)
print(job.id, job.status)

# ... do other work ...

if job.status != "completed":
    ok, result_or_err = client.wait_for_job(job.id, polling_interval=10, timeout=900)
    if ok:
        result = result_or_err      # -> BlackholeResult
    else:
        raise RuntimeError(result_or_err["error"])
```

### Environment variables

| Variable           | Role                                                       |
| ------------------ | ---------------------------------------------------------- |
| `PYQCSNU_TOKEN`    | If set, `SNUQ()` will pick it up so you can skip `login()` |

---

## Error handling

```python
from pyqcsnu.exceptions import AuthenticationError, JobError

try:
    result = client.run(qc, backend="faulty_backend")
except AuthenticationError:
    print("⚠️  Please log in first.")
except JobError as e:
    print("Job failed:", e)
```

---

## Contributing

Issues and pull requests are welcome!  Clone the repo, create a virtualenv, run
`make dev` to install dev dependencies, and open a PR against `main`.

---

## License

`pyqcsnu` is released under the **MIT License**.  See [LICENSE](LICENSE) for
full text.
