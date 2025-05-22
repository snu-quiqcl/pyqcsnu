"""
Main client class for interacting with the quantum computing services.
"""

import json
import time
import os
from typing import Dict, List, Optional, Union, Tuple, Any
import requests
from requests.exceptions import RequestException

from .models import Circuit, Job, Experiment, Result, Backend, MitigationParams
from .exceptions import (
    QuantumClientError,
    AuthenticationError,
    JobError,
    ExperimentError,
    BackendError
)

class QuantumClient:
    """Client for interacting with the SNU quantum computing services API."""
    
    # Default base URL - can be overridden by environment variable
    DEFAULT_BASE_URL = "http://localhost:8000"
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True
    ):
        """
        Initialize the quantum computing services client.
        
        Args:
            base_url: Base URL of the API server. If None, uses environment variable
                     PYQCSNU_BASE_URL or falls back to default
            token: Authentication token. If None, you must call login() before making requests
            timeout: Default timeout for requests in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        # Get base URL from environment variable if not provided
        self.base_url = (base_url or 
                        os.environ.get("PYQCSNU_BASE_URL") or 
                        self.DEFAULT_BASE_URL).rstrip('/')
        
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
        url = f"{self.base_url}/api/token/"
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
                return True
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
            self._make_request("GET", "/api/hardware/backends/")
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
        circuit: Union[str, Circuit],
        backend: Union[str, Backend] = "cassiopeia",
        shots: int = 1024,
        mitigation_params: Optional[Union[Dict, MitigationParams]] = None
    ) -> Job:
        """
        Create a new quantum computing job.
        
        Args:
            circuit: QASM circuit string or Circuit object
            backend: Backend name or Backend object
            shots: Number of shots to run
            mitigation_params: Optional error mitigation parameters
            
        Returns:
            Job object representing the created job
            
        Raises:
            JobError: If job creation fails
        """
        if isinstance(circuit, Circuit):
            circuit_info = circuit.to_dict()
        else:
            circuit_info = circuit

        if isinstance(backend, Backend):
            backend_name = backend.name
        else:
            backend_name = backend

        if isinstance(mitigation_params, MitigationParams):
            mitigation_params = mitigation_params.to_dict()

        data = {
            "circuit_info": circuit_info,
            "backend": backend_name,
            "shots": shots
        }
        if mitigation_params:
            data["mitigation_params"] = mitigation_params

        response = self._make_request("POST", "/api/runner/jobs/create/", data=data)
        return Job.from_dict(response)

    def list_jobs(self, status: Optional[str] = None) -> List[Job]:
        """
        List all jobs, optionally filtered by status.
        
        Args:
            status: Optional status filter (e.g., "running", "completed", "error")
            
        Returns:
            List of Job objects
        """
        params = {"status": status} if status else None
        response = self._make_request("GET", "/api/runner/jobs/", params=params)
        return [Job.from_dict(job_data) for job_data in response]

    def get_job(self, job_id: int) -> Job:
        """
        Get details for a specific job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            Job object with current status and details
        """
        response = self._make_request("GET", f"/api/runner/jobs/{job_id}/")
        return Job.from_dict(response)

    def get_job_results(self, job_id: int) -> Result:
        """
        Get results for a completed job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            Result object containing the job results
        """
        response = self._make_request("GET", f"/api/runner/jobs/{job_id}/results/")
        return Result.from_dict(response)

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
    ) -> Tuple[bool, Union[Result, Dict]]:
        """
        Wait for a job to complete, with optional status updates.
        
        Args:
            job_id: ID of the job to wait for
            polling_interval: Time between status checks in seconds
            timeout: Maximum time to wait in seconds
            status_callback: Optional callback function(status, job_data) for status updates
            
        Returns:
            Tuple of (success, result) where result is either a Result object or error dict
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
    ) -> Experiment:
        """
        Create a new experiment run.
        
        Args:
            pulse_schedule: Pulse schedule in TQGA format
            external_run_id: ID assigned by hardware
            
        Returns:
            Experiment object representing the created experiment
        """
        data = {
            "pulse_schedule": pulse_schedule,
            "external_run_id": external_run_id
        }
        response = self._make_request("POST", "/api/experiments/", data=data)
        return Experiment.from_dict(response)

    def get_experiment(self, experiment_id: int) -> Experiment:
        """
        Get details for a specific experiment.
        
        Args:
            experiment_id: ID of the experiment
            
        Returns:
            Experiment object with current status and details
        """
        response = self._make_request("GET", f"/api/experiments/{experiment_id}/")
        return Experiment.from_dict(response)

    # Backend Management Methods
    def list_backends(self) -> List[Backend]:
        """
        List all available quantum computing backends.
        
        Returns:
            List of Backend objects
        """
        response = self._make_request("GET", "/api/hardware/backends/")
        return [Backend.from_dict(backend_data) for backend_data in response]

    def get_backend_status(self, backend_name: str) -> Dict:
        """
        Get current status of a specific backend.
        
        Args:
            backend_name: Name of the backend
            
        Returns:
            Dictionary containing backend status information
        """
        return self._make_request("GET", f"/api/hardware/status/{backend_name}/")

    def get_backend_calibration(self, backend_name: str) -> Dict:
        """
        Get calibration data for a specific backend.
        
        Args:
            backend_name: Name of the backend
            
        Returns:
            Dictionary containing backend calibration data
        """
        return self._make_request("GET", f"/api/hardware/calibration/{backend_name}/") 