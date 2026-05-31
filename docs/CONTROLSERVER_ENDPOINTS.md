# PyQCSNU ↔ Controlserver Endpoint Contract

PyQCSNU talks to the Django controlserver using token-authenticated JSON REST
endpoints under `PYQCSNU_BASE_URL`, which defaults to `http://localhost:8000`.

## Authentication

| PyQCSNU method | Method | Endpoint | Request | Response |
| --- | --- | --- | --- | --- |
| `login(username, password)` | `POST` | `/api/user/login/` | `{"username": "...", "password": "..."}` | `{"token": "...", "user_id": 1, "username": "...", "email": "..."}` |
| `login_with_token(token)` | `GET` | `/api/hardware/` | `Authorization: Token ...` | Any `200 OK` response validates the token |

## Runner Jobs

| PyQCSNU method | Method | Endpoint | Notes |
| --- | --- | --- | --- |
| `create_job(...)` | `POST` | `/api/runner/jobs/create/` | Sends `circuit_info`, `backend`, `shots`, optional `job_name`, `mitigation_params`, `hamiltonian` |
| `list_jobs()` | `GET` | `/api/runner/jobs/` | Returns active `RunnerJobDetailSerializer` rows |
| `get_job(job_id)` | `GET` | `/api/runner/jobs/{job_id}/` | Poll until `status == "completed"` or `status == "error"` |
| `cancel_job(job_id)` | `DELETE` | `/api/runner/jobs/{job_id}/` | Returns `{"detail": "Job cancelled successfully."}` |
| `get_results(job_id)` | `GET` | `/api/runner/archives/{job_id}/` | For jobs already moved into the archive |

## Executions

| PyQCSNU method | Method | Endpoint | Notes |
| --- | --- | --- | --- |
| `create_experiment(...)` | `POST` | `/api/executions/` | Low-level execution creation |
| `get_experiment(experiment_id)` | `GET` | `/api/executions/{experiment_id}/` | Returns an `ExecutionRun` owned by the token user |

## Hardware

| PyQCSNU method | Method | Endpoint | Notes |
| --- | --- | --- | --- |
| `list_backends()` | `GET` | `/api/hardware/` | Lists `QuantumHardware` records |
| `get_backend_status(name)` | `GET` | `/api/status/?name={name}` | Returns `name`, `pending_jobs`, and `active` |

## Result Shape

Sampler jobs complete with:

```json
{
  "processed_results": {
    "counts": {
      "00000": 100
    }
  }
}
```

Expectation-value jobs complete with:

```json
{
  "processed_results": {
    "expval": 0.123
  }
}
```
