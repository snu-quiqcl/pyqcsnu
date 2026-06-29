"""
Main client class for interacting with the quantum computing services.
"""

import json
import time
import os
from typing import Dict, List, Optional, Union, Tuple, Any
import requests
from requests.exceptions import RequestException
import logging

logger = logging.getLogger(__name__)
from qiskit import QuantumCircuit
from datetime import datetime, timezone
from qiskit.result import Result
from qiskit.quantum_info import Pauli, SparsePauliOp
from qiskit.qasm2 import dumps
import numpy as np

from .models import BlackholeJob, BlackholeExperiment, BlackholeResult, SNUBackend, MitigationParams, Hamiltonian
from .exceptions import (
    QuantumClientError,
    AuthenticationError,
    JobError,
    IonLossError,
    ExperimentError,
    BackendError,
)

logging.basicConfig(
    level=logging.DEBUG,
    filename = os.getenv("PYQCSNU_LOG_FILE", "pyqcsnu.log"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    filemode="w",
)

class SNUQ:
    """Client for interacting with the SNU quantum computing services API."""
    
    # Default base URL - will be overridden by environment variable
    BASE_URL = "http://localhost:8000"
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True
    ):
        """
        Initialize the SNU quantum computing services client.
        
        Args:
            base_url: Base URL of the API server. If None, uses environment variable
                     PYQCSNU_BASE_URL or falls back to default
            token: Authentication token. If None, you must call login() before making requests
            timeout: Default timeout for requests in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        # Get base URL from environment variable if not provided
        self.base_url = (base_url or os.getenv("PYQCSNU_BASE_URL") or self.BASE_URL).rstrip("/")

        self.token = token
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        # Set token if provided
        if token:
            self.set_token(token)

        logger.debug(
            "Client initialized: base_url=%s, timeout=%s, verify_ssl=%s, token_provided=%s",
            self.base_url,
            self.timeout,
            self.verify_ssl,
            token is not None,
        )

    def set_token(self, token: str) -> None:
        """
        Set or update the authentication token.
        
        Args:
            token: The authentication token to use
        """
        self.token = token
        self.session.headers.update({"Authorization": f"Token {token}"})
        logger.debug("Authentication token set")

    def login(self, username: str, password: str) -> bool:
        """
        Authenticate with the API server and get a token.
        
        Args:
            username: User's username
            password: User's password
            
        Returns:
            True if login was successful
            
        Raises:
            AuthenticationError: If login fails
        """
        urls = [
            f"{self.base_url}/api/token/",
            f"{self.base_url}/api/user/login/",
        ]
        logger.info("Logging in user %s", username)
        last_error = None
        try:
            for url in urls:
                response = self.session.post(
                    url,
                    json={"username": username, "password": password},
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.set_token(data["token"])
                    logger.info("Login successful")
                    return 'success'

                last_error = response.text
                if response.status_code != 404:
                    break

            logger.error("Login failed: %s", last_error)
            raise AuthenticationError(f"Login failed: {last_error}")
        except RequestException as e:
            logger.error("Login request exception: %s", e)
            raise AuthenticationError(f"Login request failed: {str(e)}")

    def login_with_token(self, token: str) -> None:
        """
        Login using a pre-existing token.
        
        Args:
            token: The authentication token to use
            
        Raises:
            AuthenticationError: If token is invalid
        """
        self.set_token(token)
        logger.info("Logging in with existing token")
        # Verify token is valid by making a simple request
        try:
            try:
                self._make_request("GET", "/api/hardware/backends/")
            except BackendError as exc:
                if getattr(exc, "status_code", None) != 404:
                    raise
                self._make_request("GET", "/api/hardware/")
        except AuthenticationError:
            self.token = None
            self.session.headers.pop("Authorization", None)
            logger.error("Invalid token provided")
            raise AuthenticationError("Invalid token")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> Dict:
        """
        Make an API request with proper error handling.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request data (for POST/PUT)
            params: URL parameters (for GET)
            timeout: Optional timeout override
            
        Returns:
            Response JSON data
            
        Raises:
            QuantumClientError: For general API errors
            AuthenticationError: For authentication issues
            JobError: For job-related errors
            ExperimentError: For experiment-related errors
            BackendError: For backend-related errors
        """
        public_endpoints = ("/api/user/login/", "/api/user/register/")
        if not self.token and endpoint not in public_endpoints:
            raise AuthenticationError("Not authenticated. Call login() first.")

        url = f"{self.base_url}{endpoint}"
        timeout = timeout or self.timeout

        logger.debug(
            "HTTP %s request to %s with params=%s data=%s", method, url, params, data
        )

        try:
            if method == "GET":
                response = self.session.get(url, params=params, timeout=timeout, verify=self.verify_ssl)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=timeout, verify=self.verify_ssl)
            elif method == "PUT":
                response = self.session.put(url, json=data, timeout=timeout, verify=self.verify_ssl)
            elif method == "DELETE":
                response = self.session.delete(url, timeout=timeout, verify=self.verify_ssl)
            else:
                raise QuantumClientError(f"Unsupported method: {method}")

            logger.debug("Response status: %s", response.status_code)

            # Handle different status codes
            if response.status_code >= 500:
                exc = QuantumClientError(f"Server error: {response.text}")
                exc.status_code = response.status_code
                raise exc
            elif response.status_code == 401:
                exc = AuthenticationError("Authentication failed")
                exc.status_code = response.status_code
                raise exc
            elif response.status_code == 403:
                exc = AuthenticationError("Permission denied")
                exc.status_code = response.status_code
                raise exc
            elif response.status_code >= 400:
                try:
                    error_data = response.json() if response.text else {"detail": "Unknown error"}
                except json.JSONDecodeError:
                    error_data = {"detail": response.text or "Unknown error"}
                error_message = error_data.get("detail") or error_data.get("error") or error_data.get("message") or "Operation failed"
                if "job" in endpoint:
                    exc = JobError(error_message)
                elif "experiment" in endpoint:
                    exc = ExperimentError(error_message)
                elif "backend" in endpoint or "hardware" in endpoint:
                    exc = BackendError(error_message)
                else:
                    exc = QuantumClientError(error_message)
                exc.status_code = response.status_code
                raise exc

            # Parse response
            try:
                parsed = response.json()
            except json.JSONDecodeError:
                parsed = {"message": response.text}

            logger.debug("Response parsed successfully")
            return parsed

        except RequestException as e:
            logger.error("Request failed: %s", e)
            raise QuantumClientError(f"Request failed: {str(e)}")

    # Job Management Methods
    def create_job(
        self,
        circuit: Union[QuantumCircuit, Dict, str],
        backend: str,
        shots: int = 1024,
        mitigation_params: Optional[MitigationParams] = None,
        hamiltonian: Optional[Hamiltonian] = None,
        name: Optional[str] = None
    ) -> BlackholeJob:
        """Create a new quantum job.
        
        Args:
            circuit: Circuit to execute. Can be:
                – A Qiskit QuantumCircuit instance (converted to qasm via circuit.qasm() or a fallback conversion)
                – A dict (or JSON string) with a 'qasm' key (or converted to dict and qasm extracted)
            backend: Name of the backend to use
            shots: Number of shots to execute
            mitigation_params: Optional error mitigation parameters
            name: Optional name for the job (ignored if circuit is a dict or JSON string)
            
        Returns:
            BlackholeJob instance
            
        Raises:
            AuthenticationError: If not authenticated
            APIError: If API request fails
            ValueError: If circuit format is invalid
        """
        if not self.token:
            raise AuthenticationError("Not authenticated. Call login() first.")

        logger.info("Creating job on backend %s", backend)
        qasm = None
        if isinstance(circuit, QuantumCircuit):
            try:
                qasm = dumps(circuit)
            except Exception as e:
                raise ValueError(f"Failed to convert QuantumCircuit to qasm: {e}")
        elif isinstance(circuit, str):
            try:
                circuit_dict = json.loads(circuit)
            except json.JSONDecodeError:
                raise ValueError("Invalid circuit JSON string")
            if "qasm" in circuit_dict:
                qasm = circuit_dict["qasm"]
            else:
                raise ValueError("Circuit dict (or JSON string) must contain a 'qasm' key.")
        elif isinstance(circuit, dict) and "qasm" in circuit:
            qasm = circuit["qasm"]
        elif hasattr(circuit, "qasm") and getattr(circuit, "qasm"):
            qasm = circuit.qasm
        elif hasattr(circuit, "to_dict"):
            circuit_dict = circuit.to_dict()
            if circuit_dict.get("qasm"):
                qasm = circuit_dict["qasm"]
            else:
                try:
                    qasm = dumps(circuit.to_qiskit())
                except Exception:
                    qasm = json.dumps(circuit_dict)
        else:
            raise ValueError("Circuit must be a QuantumCircuit, a dict (or JSON string) with a 'qasm' key.")
        # Prepare job data (using a dict with a 'qasm' key)
        job_data = { "circuit_info": qasm, "backend": backend, "shots": shots }
        if mitigation_params:
            job_data["mitigation_params"] = mitigation_params.to_dict()
        if name:
            job_data["job_name"] = name
        if hamiltonian:
            job_data["hamiltonian"] = hamiltonian.to_dict()
            job_data["experiment_type"] = "EXPVAL"

        # Create job
        try:
            response = self._make_request("POST", "/api/runner/jobs/create/", data=job_data)
        except JobError as exc:
            if getattr(exc, "status_code", None) != 404:
                raise
            response = self._make_request("POST", "/api/runner/jobs/", data=job_data)
        logger.info("Job created with ID %s", response.get("id"))
        return BlackholeJob.from_dict(response)

    def list_jobs(self, status: Optional[str] = None) -> List[BlackholeJob]:
        """
        List all jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter (e.g., "running", "completed", "error")
            
        Returns:
            List of BlackholeJob objects
        """
        params = {"status": status} if status else None
        logger.debug("Listing jobs with params %s", params)
        response = self._make_request("GET", "/api/runner/jobs/", params=params)
        return [BlackholeJob.from_dict(job_data) for job_data in response]

    def get_job(self, job_id: int) -> BlackholeJob:
        """
        Get details for a specific job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            BlackholeJob object with current status and details
        """
        logger.debug("Fetching job %s", job_id)
        response = self._make_request("GET", f"/api/runner/jobs/{job_id}/")
        return BlackholeJob.from_dict(response)

    def get_results(self, job_id: int) -> BlackholeResult:
        """
        Get results for a completed job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            BlackholeResult object containing the job results
        """
        logger.debug("Fetching results for job %s", job_id)
        try:
            response = self._make_request("GET", f"/api/runner/jobs/{job_id}/results/")
        except JobError as exc:
            if getattr(exc, "status_code", None) != 404:
                raise
            response = self._make_request("GET", f"/api/runner/archives/{job_id}/")
        return BlackholeResult.from_dict(response)

    def get_job_results(self, job_id: int) -> BlackholeResult:
        """Backward-compatible alias for get_results."""
        return self.get_results(job_id)

    def cancel_job(self, job_id: int) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            True if cancellation was successful
            
        Raises:
            JobError: If cancellation fails
        """
        logger.info("Cancelling job %s", job_id)
        response = self._make_request("DELETE", f"/api/runner/jobs/{job_id}/")
        return "cancelled" in response.get("detail", "").lower()

    def wait_for_job(
        self,
        job_id: int,
        polling_interval: int = 5,
        timeout: int = 300,
        status_callback: Optional[callable] = None
    ) -> Tuple[bool, Union[BlackholeJob, Dict]]:
        """
        Wait for a job to complete, with optional status updates.
        
        Args:
            job_id: ID of the job to wait for
            polling_interval: Time between status checks in seconds
            timeout: Maximum time to wait in seconds
            status_callback: Optional callback function(status, job_data) for status updates
            
        Returns:
            Tuple of (success, result) where result is either a completed BlackholeJob object or error dict
        """
        logger.info("Waiting for job %s", job_id)
        start_time = time.time()
        ion_loss_seen = False
        
        while time.time() - start_time < timeout:
            try:
                job = self.get_job(job_id)

                if status_callback:
                    status_callback(job.status, job.to_dict())

                logger.debug("Job %s status: %s", job_id, job.status)
                
                if job.status == "completed":
                    logger.info("Job %s completed", job_id)
                    if job.processed_results is None:
                        try:
                            return True, self.get_job_results(job_id)
                        except JobError:
                            pass
                    return True, job
                elif job.status == "ion_lost":
                    ion_loss_seen = True
                    logger.error(
                        "Job %s paused after ion loss: %s",
                        job_id,
                        job.error_message or "backend inspection required",
                    )
                elif job.status == "error":
                    logger.error("Job %s errored: %s", job_id, job.error_message)
                    return False, {"error": job.error_message or "Job failed"}
                elif job.status == "cancelled":
                    logger.warning("Job %s was cancelled", job_id)
                    return False, {"error": "Job was cancelled"}
                
                time.sleep(polling_interval)
                
            except (JobError, QuantumClientError) as e:
                logger.error("Error while waiting for job %s: %s", job_id, e)
                return False, {"error": str(e)}

        logger.error("Timeout waiting for job %s completion", job_id)
        if ion_loss_seen:
            return False, {
                "error": (
                    "Ion loss was detected and the backend is waiting for inspection. "
                    "The job remains queued for retry when service resumes."
                ),
                "error_type": "ion_loss",
                "status": "ion_lost",
            }
        return False, {"error": "Timeout waiting for job completion"}

    # Experiment Management Methods
    def create_experiment(
        self,
        pulse_schedule: Dict,
        external_run_id: int
    ) -> BlackholeExperiment:
        """
        Create a new experiment run.
        
        Args:
            pulse_schedule: Pulse schedule in TQGA format
            external_run_id: ID assigned by hardware
            
        Returns:
            BlackholeExperiment object representing the created experiment
        """
        data = {
            "pulse_schedule": pulse_schedule,
            "external_run_id": external_run_id
        }
        logger.info("Creating experiment run")
        response = self._make_request("POST", "/api/executions/", data=data)
        logger.debug("Experiment created with response %s", response)
        return BlackholeExperiment.from_dict(response)

    def get_experiment(self, experiment_id: int) -> BlackholeExperiment:
        """
        Get details for a specific experiment.
        
        Args:
            experiment_id: ID of the experiment
            
        Returns:
            BlackholeExperiment object with current status and details
        """
        logger.debug("Fetching experiment %s", experiment_id)
        response = self._make_request("GET", f"/api/executions/{experiment_id}/")
        return BlackholeExperiment.from_dict(response)

    # Backend Management Methods
    def list_backends(self) -> List[SNUBackend]:
        """
        Retrieve every hardware record.

        Returns
        -------
        List[SNUBackend]
            Each item has .name, .graph_data, .pending_jobs (and legacy fields = None).
        """
        logger.debug("Listing available backends")
        try:
            response = self._make_request("GET", "/api/hardware/backends/")
        except BackendError as exc:
            if getattr(exc, "status_code", None) != 404:
                raise
            response = self._make_request("GET", "/api/hardware/")
        return [SNUBackend.from_dict(obj) for obj in response]


    def get_backend_status(self, backend_name: str) -> Dict[str, Any]:
        """
        Get live job-queue length for a single backend.

        The `hardware-status` view is mounted at `/api/hardware/status/`
        and expects `?name=<backend>` as a query parameter.
        """
        logger.debug("Fetching backend status for %s", backend_name)
        return self._make_request(
            "GET",
            "/api/hardware/status/",
            params={"name": backend_name},
        )
    
    def run(
        self,
        circuit: QuantumCircuit,
        backend: str,
        *,
        shots: int = 1024,
        mitigation_params: Optional[MitigationParams] = None,
        name: Optional[str] = None,
        polling_interval: int = 0.5,
        timeout: int = 300,
    ) -> Result:
        """
        Submit `circuit`, block until it finishes, and return a Qiskit `Result`.

        Parameters
        ----------
        circuit
            The QuantumCircuit to execute.
        backend
            Backend name recognised by the server.
        shots
            Number of shots for execution.
        mitigation_params
            Optional error-mitigation parameters.
        name
            Human-readable identifier stored on the server.
        polling_interval
            Seconds between status checks.
        timeout
            Abort waiting after this many seconds.

        Returns
        -------
        qiskit.result.Result
            Qiskit-compatible result object (counts in ``Result.get_counts()``).

        Raises
        ------
        AuthenticationError
            If the client is not logged in.
        QuantumClientError | JobError
            If submission fails or the job errors out.
        TimeoutError
            If the job is not finished within *timeout* seconds.
        """
        logger.info("Running circuit on backend %s", backend)
        # 1. Submit
        job = self.create_job(
            circuit=circuit,
            backend=backend,
            shots=shots,
            mitigation_params=mitigation_params,
            name=name,
        )

        # 2. Wait
        ok, res_or_err = self.wait_for_job(
            job_id=job.id,
            polling_interval=polling_interval,
            timeout=timeout,
        )

        if not ok:
            # `res_or_err` is an error dict from wait_for_job
            msg = res_or_err.get("error", "Unknown job failure")
            if res_or_err.get("error_type") == "ion_loss":
                raise IonLossError(f"Job {job.id} paused after ion loss: {msg}")
            raise JobError(f"Job {job.id} failed: {msg}")

        logger.info("Job %s completed successfully", job.id)
        # 3. Convert service result → Qiskit Result
        completed_job: BlackholeJob = res_or_err
        processed_results = completed_job.processed_results or {}
        if "counts" not in processed_results:
            raise JobError(f"Job {job.id} completed without counts in processed_results")
        result_dict = {
            "backend_name": backend,
            "backend_version": "0.0.1",
            #"qobj_id": None,    # deprecated in Qiskit 2.x
            "job_id": str(job.id),
            "success": True,
            "results": [
                {
                    "shots": shots,
                    "status": "DONE",
                    "success": True,
                    "header": {
                        "name": name or f"SNUQ-run-{datetime.now(timezone.utc).isoformat()}",
                        "memory_slots": circuit.num_clbits,
                        "n_qubits": circuit.num_qubits,
                    },
                    "data": {
                        "counts": {k: v for k, v in processed_results["counts"].items()},
                    },
                }
            ],
        }
        return Result.from_dict(result_dict)
    
    def expval(self,
        circuit: QuantumCircuit,
        operators: Union[Pauli, SparsePauliOp],
        backend: str,
        *,
        shots: int = 1024,
        mitigation_params: Optional[MitigationParams] = None,
        name: Optional[str] = None,
        polling_interval: int = 0.5,
        timeout: int = 300,
    ) -> float:
        """
        Submit `circuit` and `hamiltonian`, block until it finishes, and return a Qiskit `Result`.

        Parameters
        ----------
        circuit
            The QuantumCircuit to execute.
        hamiltonian
            The Hamiltonian to evaluate.
        backend
            Backend name recognised by the server.
        shots
            Number of shots for execution.
        mitigation_params
            Optional error-mitigation parameters.
        name
            Human-readable identifier stored on the server.
        polling_interval
            Seconds between status checks.
        timeout
            Abort waiting after this many seconds.

        Returns
        -------
        float
            The expectation value of the Hamiltonian.
        """

        logger.info("Running expectation value on backend %s", backend)

        num_qubits = circuit.num_qubits

        if isinstance(operators, Pauli):
            label = operators.to_label()
            if len(label) < num_qubits:
                raise ValueError("The length of the operators must match the length of the circuit.")
            operators = Hamiltonian.from_dict({
                "operators": [label],
                "coefficients": [1.0]
            })

        elif isinstance(operators, SparsePauliOp):
            labels = []
            for p in operators.paulis:
                if len(p.to_label()) < num_qubits:
                    raise ValueError("The length of the operators must match the length of the circuit.")
                else: labels.append(p.to_label())
            
            coeffs = [float(c.real) for c in operators.coeffs]
            operators = Hamiltonian.from_dict({
                "operators": labels,
                "coefficients": coeffs
            })
        
        job = self.create_job(
            circuit=circuit,
            backend=backend,
            hamiltonian=operators,
            shots=shots,
            mitigation_params=mitigation_params,
            name=name,
        )

        ok, res_or_err = self.wait_for_job(
            job_id=job.id,
            polling_interval=polling_interval,
            timeout=timeout,
        )
        if not ok:
            # `res_or_err` is an error dict from wait_for_job
            msg = res_or_err.get("error", "Unknown job failure")
            if res_or_err.get("error_type") == "ion_loss":
                raise IonLossError(f"Job {job.id} paused after ion loss: {msg}")
            raise JobError(f"Job {job.id} failed: {msg}")
        
        logger.info("Expectation value job %s completed", job.id)
        processed_results = res_or_err.processed_results or {}
        if "expval" not in processed_results:
            raise JobError(f"Job {job.id} completed without expval in processed_results")
        return processed_results["expval"]
