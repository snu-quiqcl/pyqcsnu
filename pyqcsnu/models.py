"""
Data models for the quantum computing client.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json

@dataclass
class Circuit:
    """Represents a quantum circuit."""
    
    qasm: str
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert circuit to dictionary format."""
        return {
            "qasm": self.qasm,
            "name": self.name,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Circuit':
        """Create a Circuit instance from a dictionary."""
        return cls(
            qasm=data["qasm"],
            name=data.get("name"),
            metadata=data.get("metadata", {})
        )

@dataclass
class MitigationParams:
    """Parameters for error mitigation techniques."""
    
    technique: str
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert mitigation parameters to dictionary format."""
        return {
            "technique": self.technique,
            "params": self.params
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MitigationParams':
        """Create a MitigationParams instance from a dictionary."""
        return cls(
            technique=data["technique"],
            params=data.get("params", {})
        )

@dataclass
class Backend:
    """Represents a quantum computing backend."""
    
    name: str
    status: str
    n_qubits: int
    capabilities: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert backend to dictionary format."""
        return {
            "name": self.name,
            "status": self.status,
            "n_qubits": self.n_qubits,
            "capabilities": self.capabilities,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Backend':
        """Create a Backend instance from a dictionary."""
        return cls(
            name=data["name"],
            status=data["status"],
            n_qubits=data["n_qubits"],
            capabilities=data.get("capabilities", {}),
            metadata=data.get("metadata", {})
        )

@dataclass
class Job:
    """Represents a quantum computing job."""
    
    id: int
    status: str
    circuit: Circuit
    backend: str
    shots: int
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    mitigation_params: Optional[MitigationParams] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert job to dictionary format."""
        return {
            "id": self.id,
            "status": self.status,
            "circuit": self.circuit.to_dict(),
            "backend": self.backend,
            "shots": self.shots,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "mitigation_params": self.mitigation_params.to_dict() if self.mitigation_params else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Job':
        """Create a Job instance from a dictionary."""
        return cls(
            id=data["id"],
            status=data["status"],
            circuit=Circuit.from_dict(data["circuit"]),
            backend=data["backend"],
            shots=data["shots"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error_message=data.get("error_message"),
            mitigation_params=MitigationParams.from_dict(data["mitigation_params"]) if data.get("mitigation_params") else None,
            metadata=data.get("metadata", {})
        )

@dataclass
class Experiment:
    """Represents a quantum experiment run."""
    
    id: int
    status: str
    pulse_schedule: Dict[str, Any]
    external_run_id: int
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert experiment to dictionary format."""
        return {
            "id": self.id,
            "status": self.status,
            "pulse_schedule": self.pulse_schedule,
            "external_run_id": self.external_run_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Experiment':
        """Create an Experiment instance from a dictionary."""
        return cls(
            id=data["id"],
            status=data["status"],
            pulse_schedule=data["pulse_schedule"],
            external_run_id=data["external_run_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {})
        )

@dataclass
class Result:
    """Represents the results of a quantum computing job."""
    
    job_id: int
    counts: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed_data: Optional[Dict[str, Any]] = None
    error_mitigation: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary format."""
        return {
            "job_id": self.job_id,
            "counts": self.counts,
            "metadata": self.metadata,
            "processed_data": self.processed_data,
            "error_mitigation": self.error_mitigation
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Result':
        """Create a Result instance from a dictionary."""
        return cls(
            job_id=data["job_id"],
            counts=data["counts"],
            metadata=data.get("metadata", {}),
            processed_data=data.get("processed_data"),
            error_mitigation=data.get("error_mitigation")
        )
    
    def get_expectation_value(self, observable: Dict[str, float]) -> float:
        """
        Calculate the expectation value for a given observable.
        
        Args:
            observable: Dictionary mapping bitstrings to their coefficients
            
        Returns:
            Expectation value
        """
        expectation = 0.0
        total_shots = sum(self.counts.values())
        
        for bitstring, count in self.counts.items():
            if bitstring in observable:
                expectation += observable[bitstring] * (count / total_shots)
        
        return expectation
    
    def get_probability(self, bitstring: str) -> float:
        """
        Get the probability of a specific bitstring.
        
        Args:
            bitstring: The bitstring to get the probability for
            
        Returns:
            Probability of the bitstring
        """
        total_shots = sum(self.counts.values())
        return self.counts.get(bitstring, 0) / total_shots 