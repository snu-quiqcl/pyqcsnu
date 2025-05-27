"""
Main client class for interacting with the quantum computing services.
"""

import json
import time
import os
from typing import Dict, List, Optional, Union, Tuple, Any
import requests
from requests.exceptions import RequestException
from qiskit import QuantumCircuit
from datetime import datetime, timezone
from qiskit.result import Result
from qiskit.quantum_info import Pauli, SparsePauliOp, PauliSumOp

from .models import BlackholeJob, BlackholeExperiment, BlackholeResult, SNUBackend, MitigationParams, Hamiltonian
from .exceptions import (
    QuantumClientError,
    AuthenticationError,
    JobError,
    ExperimentError,
    BackendError,
)

class SNUQ:
    """Client for interacting with the SNU quantum computing services API."""
    
    # Default base URL - will be overridden by environment variable
    BASE_URL = "http://localhost:8000"
    
    def __init__(
        self,
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
        self.base_url = self.BASE_URL
        
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

    def set_token(self, token: str) -> None:
        """
        Set or update the authentication token.
        
        Args:
            token: The authentication token to use
        """
        self.token = token
        self.session.headers.update({"Authorization": f"Token {token}"})

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
        url = f"{self.base_url}/api/user/login/"
        try:
            response = self.session.post(
                url,
                json={"username": username, "password": password},
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code == 200:
                data = response.json()
                self.set_token(data["token"])
                return 'success'
            else:
                raise AuthenticationError(f"Login failed: {response.text}")
                
        except RequestException as e:
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
        # Verify token is valid by making a simple request
        try:
            self._make_request("GET", "/api/hardware/")
        except AuthenticationError:
            self.token = None
            self.session.headers.pop("Authorization", None)
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
        if not self.token and endpoint != "/api/token/":
            raise AuthenticationError("Not authenticated. Call login() first.")

        url = f"{self.base_url}{endpoint}"
        timeout = timeout or self.timeout

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

            # Handle different status codes
            if response.status_code >= 500:
                raise QuantumClientError(f"Server error: {response.text}")
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed")
            elif response.status_code == 403:
                raise AuthenticationError("Permission denied")
            elif response.status_code >= 400:
                error_data = response.json() if response.text else {"error": "Unknown error"}
                if "job" in endpoint:
                    raise JobError(error_data.get("error", "Job operation failed"))
                elif "experiment" in endpoint:
                    raise ExperimentError(error_data.get("error", "Experiment operation failed"))
                elif "backend" in endpoint:
                    raise BackendError(error_data.get("error", "Backend operation failed"))
                else:
                    raise QuantumClientError(error_data.get("error", "Operation failed"))

            # Parse response
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"message": response.text}

        except RequestException as e:
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
        qasm = None
        if isinstance(circuit, QuantumCircuit):
            # Convert QuantumCircuit to qasm (using circuit.qasm() if available, or a fallback conversion)
            if hasattr(circuit, "qasm") and callable(circuit.qasm):
                qasm = circuit.qasm()
            else:
                # Fallback conversion (for example, using a dummy circuit with a h gate on qubit 0)
                qasm = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nh q[0];\n"
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
        else:
            raise ValueError("Circuit must be a QuantumCircuit, a dict (or JSON string) with a 'qasm' key.")
        # Prepare job data (using a dict with a 'qasm' key)
        job_data = { "circuit_info": qasm, "backend": backend, "shots": shots }
        if mitigation_params:
            job_data["mitigation_params"] = mitigation_params.to_dict()
        if name:
            job_data["name"] = name
        if hamiltonian:
            job_data["hamiltonian"] = hamiltonian.to_dict()
            job_data["experiment_type"] = "EXPVAL"
        
        # Create job
        response = self._make_request("POST", "/api/runner/jobs/create/", data=job_data)
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
        response = self._make_request("GET", f"/api/runner/jobs/{job_id}/")
        return BlackholeJob.from_dict(response)

    def get_job_results(self, job_id: int) -> BlackholeResult:
        """
        Get results for a completed job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            BlackholeResult object containing the job results
        """
        response = self._make_request("GET", f"/api/runner/jobs/{job_id}/results/")
        return BlackholeResult.from_dict(response)

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
        response = self._make_request("DELETE", f"/api/runner/jobs/{job_id}/cancel/")
        return response.get("status") == "cancelled"

    def wait_for_job(
        self,
        job_id: int,
        polling_interval: int = 5,
        timeout: int = 300,
        status_callback: Optional[callable] = None
    ) -> Tuple[bool, Union[BlackholeResult, Dict]]:
        """
        Wait for a job to complete, with optional status updates.
        
        Args:
            job_id: ID of the job to wait for
            polling_interval: Time between status checks in seconds
            timeout: Maximum time to wait in seconds
            status_callback: Optional callback function(status, job_data) for status updates
            
        Returns:
            Tuple of (success, result) where result is either a BlackholeResult object or error dict
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                job = self.get_job(job_id)
                
                if status_callback:
                    status_callback(job.status, job.to_dict())
                
                if job.status == "completed":
                    return True, self.get_job_results(job_id)
                elif job.status == "error":
                    return False, {"error": job.error_message or "Job failed"}
                elif job.status == "cancelled":
                    return False, {"error": "Job was cancelled"}
                
                time.sleep(polling_interval)
                
            except (JobError, QuantumClientError) as e:
                return False, {"error": str(e)}
        
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
        response = self._make_request("POST", "/api/experiments/", data=data)
        return BlackholeExperiment.from_dict(response)

    def get_experiment(self, experiment_id: int) -> BlackholeExperiment:
        """
        Get details for a specific experiment.
        
        Args:
            experiment_id: ID of the experiment
            
        Returns:
            BlackholeExperiment object with current status and details
        """
        response = self._make_request("GET", f"/api/experiments/{experiment_id}/")
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
        response = self._make_request("GET", "/api/hardware/")
        return [SNUBackend.from_dict(obj) for obj in response]


    def get_backend_status(self, backend_name: str) -> Dict[str, Any]:
        """
        Get live job-queue length for a single backend.

        The `hardware-status` view is mounted at `/api/hardware/status/`
        and expects `?name=<backend>` as a query parameter.
        """
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
            raise JobError(f"Job {job.id} failed: {msg}")

        # 3. Convert service result → Qiskit Result
        bh_res: BlackholeResult = res_or_err
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
                        # Expecting BlackholeResult.counts == {'00': 512, '11': 512, …}
                        "counts": {k: v for k, v in bh_res.counts.items()},
                    },
                }
            ],
        }
        return Result.from_dict(result_dict)
    
    def expval(self,
        circuit: QuantumCircuit,
        operators: Union[Pauli, SparsePauliOp, PauliSumOp],
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

        if isinstance(operators, Pauli):
            return Hamiltonian.from_dict({
                "operators": [operators.to_label()],
                "coefficients": [1.0]
            })

        # If it’s an Opflow PauliSumOp, extract its primitive -> SparsePauliOp
        if isinstance(operators, PauliSumOp):
            operators = operators.primitive

        if isinstance(operators, SparsePauliOp):
            # .to_list() → List[Tuple[Pauli, complex]]
            terms = operators.to_list()

            labels = [p.to_label() for p, _c in terms]
            coeffs = [float(c.real) for _p, c in terms]

            return Hamiltonian.from_dict({"operators": labels, "coefficients": coeffs})
        
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
            raise JobError(f"Job {job.id} failed: {msg}")
        
        return res_or_err.processed_results