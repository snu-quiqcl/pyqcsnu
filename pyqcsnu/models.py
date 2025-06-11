"""
Data models for the quantum computing client.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json
from pydantic import BaseModel, Field
from qiskit import QuantumCircuit


'''
class QCircuit(BaseModel):
    """Model representing a quantum circuit."""
    name: str = Field(..., description="Name of the circuit")
    num_qubits: int = Field(..., description="Number of qubits in the circuit")
    gates: List[Dict[str, Any]] = Field(default_factory=list, description="List of quantum gates")
    parameters: Dict[str, float] = Field(default_factory=dict, description="Circuit parameters")
    qasm: Optional[str] = Field(None, description="OpenQASM representation of the circuit")
    
    @classmethod
    def from_qasm(cls, qasm: str, name: Optional[str] = None) -> 'QCircuit':
        """Create a QCircuit instance from OpenQASM string."""
        lines = qasm.strip().split('\n')
        num_qubits = 0
        gates = []
        for line in lines:
            line = line.strip()
            if line.startswith('qreg'):
                num_qubits = int(line.split('[')[1].split(']')[0])
            elif line and not line.startswith(('OPENQASM', 'include', '//', 'creg', 'measure')):
                if ';' in line:
                    gate_line = line.split(';')[0].strip()
                    if gate_line:
                        parts = gate_line.split()
                        if len(parts) >= 2:
                            gate_name = parts[0]
                            qubits = [int(q.strip('q[]')) for q in parts[1].split(',') if q.strip()]
                            gates.append({
                                "name": gate_name,
                                "qubits": qubits,
                                "clbits": []
                            })
        return cls(
            name=name or "qasm_circuit",
            num_qubits=num_qubits,
            gates=gates,
            qasm=qasm
        )
    
    @classmethod
    def from_qiskit(cls, circuit: QuantumCircuit, name: Optional[str] = None) -> 'QCircuit':
        """Create a QCircuit instance from a Qiskit QuantumCircuit."""
        gates = []
        parameters = {}
        for instruction, qargs, cargs in circuit.data:
            gate_dict = {
                "name": instruction.name,
                "qubits": [q._index for q in qargs],
                "clbits": [c._index for c in cargs],
            }
            if instruction.params:
                param_values = []
                for param in instruction.params:
                    if isinstance(param, Parameter):
                        param_name = param.name
                        if param_name not in parameters:
                            parameters[param_name] = 0.0
                        param_values.append({"name": param_name})
                    else:
                        param_values.append({"value": float(param)})
                gate_dict["params"] = param_values
            gates.append(gate_dict)
        return cls(
            name=name or circuit.name or "qiskit_circuit",
            num_qubits=circuit.num_qubits,
            gates=gates,
            parameters=parameters,
            qasm=None  # Do not use circuit.qasm()
        )
    
    def to_qiskit(self) -> QuantumCircuit:
        """Convert to a Qiskit QuantumCircuit.
        
        Returns:
            QuantumCircuit instance
        """
        circuit = QuantumCircuit(self.num_qubits, name=self.name)
        
        # Map of gate names to Qiskit gate classes
        gate_map = {
            "h": standard_gates.HGate,
            "x": standard_gates.XGate,
            "y": standard_gates.YGate,
            "z": standard_gates.ZGate,
            "cx": standard_gates.CXGate,
            "cz": standard_gates.CZGate,
            "swap": standard_gates.SwapGate,
            "rx": standard_gates.RXGate,
            "ry": standard_gates.RYGate,
            "rz": standard_gates.RZGate,
            "u1": standard_gates.U1Gate,
            "u2": standard_gates.U2Gate,
            "u3": standard_gates.U3Gate,
        }
        
        # Apply gates
        for gate in self.gates:
            gate_name = gate["name"].lower()
            qubits = gate["qubits"]
            
            if gate_name in gate_map:
                gate_class = gate_map[gate_name]
                params = []
                
                # Handle parameters
                if "params" in gate:
                    for param in gate["params"]:
                        if "name" in param:
                            param_name = param["name"]
                            if param_name in self.parameters:
                                params.append(self.parameters[param_name])
                            else:
                                params.append(0.0)  # Default value
                        elif "value" in param:
                            params.append(param["value"])
                
                # Create and apply the gate
                if params:
                    gate_instance = gate_class(*params)
                else:
                    gate_instance = gate_class()
                
                circuit.append(gate_instance, qubits)
            else:
                raise ValueError(f"Unsupported gate: {gate_name}")
        
        return circuit
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert circuit to dictionary format."""
        return {
            "name": self.name,
            "num_qubits": self.num_qubits,
            "gates": self.gates,
            "parameters": self.parameters,
            "qasm": self.qasm
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QCircuit':
        """Create circuit from dictionary format."""
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert circuit to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'QCircuit':
        """Create circuit from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
'''

# Abstract dataclass for parameters for error mitigation
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
    

# Abstract dataclass for the Hamiltonian for expectation value evaluations
@dataclass
class Hamiltonian:
    operators: List[str]
    coefficients: List[float]
    num_qubits: Optional[int] = None

    def __post_init__(self):
        if len(self.operators) != len(self.coefficients):
            raise ValueError(
                f"Expected same length for operators ({len(self.operators)}) "
                f"and coefficients ({len(self.coefficients)})."
            )
        if self.num_qubits is None:
            self.num_qubits = len(self.operators[0])
        for op in self.operators:
            if not isinstance(op, str) or not op:
                raise ValueError(f"Invalid operator: {op!r}")

    def to_dict(self) -> Dict:
        return {
            "num_qubits": self.num_qubits,
            "operators": self.operators,
            "coefficients": self.coefficients,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Hamiltonian":
        if "num_qubits" not in data:
            data["num_qubits"] = len(data["operators"][0])

        return cls(
            num_qubits=data["num_qubits"],
            operators=data["operators"],
            coefficients=data["coefficients"],
        )

@dataclass
class SNUBackend:
    """
    Represents a quantum-hardware record returned by the “hardware” app in the backend server.

    If you still need the older `status`, `n_qubits`, etc., keep them as
    *optional* extras so existing code does not break.
    """
    # --- required by the API --------------------------------------------------
    name: str
    graph_data: Dict[str, Any] = field(default_factory=dict)
    pending_jobs: int = 0

    # --- legacy / optional fields --------------------------------------------
    status: str = None
    n_qubits: int = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (round-trippable with `from_dict`)."""
        return {
            "name": self.name,
            # "graph_data": self.graph_data,
            "pending_jobs": self.pending_jobs,
            "status": self.status,
            "n_qubits": self.n_qubits,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SNUBackend":
        """Construct from API payload."""
        return cls(
            name=data["name"],
            #graph_data=data.get("graph_data", {}),
            pending_jobs=data.get("pending_jobs", 0),
            status=data.get("status"),             # not in new payload → None
            n_qubits=data.get("n_qubits"),         # not in new payload → None
            metadata=data.get("metadata", {}),
        )

@dataclass
class BlackholeJob:
    """Represents a quantum computing job."""
    
    id: int
    status: str
    circuit: QuantumCircuit
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
            "circuit_info": self.circuit.to_dict(),
            "backend": self.backend,
            "shots": self.shots,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "mitigation_params": self.mitigation_params.to_dict() if self.mitigation_params else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BlackholeJob':
        """Create a BlackholeJob instance from a dictionary."""
        return cls(
            id=data["id"],
            status=data["status"],
            circuit=data["circuit_info"],
            backend=data["backend"],
            shots=data["shots"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            error_message=data.get("error_message"),
            mitigation_params=MitigationParams.from_dict(data["mitigation_params"]) if data.get("mitigation_params") else None,
            metadata=data.get("metadata", {})
        )

'''
@dataclass
class BlackholeExperiment:
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
    def from_dict(cls, data: Dict) -> 'BlackholeExperiment':
        """Create a BlackholeExperiment instance from a dictionary."""
        return cls(
            id=data["id"],
            status=data["status"],
            pulse_schedule=data["pulse_schedule"],
            external_run_id=data["external_run_id"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {})
        )
'''

@dataclass
class BlackholeResult:
    """Represents the results of a quantum computing job."""
    id: int
    job_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed_results: Optional[Dict[str, Any]] = None
    mitigation_params: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id" : self.id,
            "job_id": self.job_id,
            "metadata": self.metadata,
            "processed_results": self.processed_results,
            "mitigation_params": self.mitigation_params,
        }

    # ---------- FIXED ----------
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlackholeResult":
        """
        Build a BlackholeResult from the API payload.

        The server may supply:
            • 'processed_results' -> {'counts': {...} or 'expval': ...}
            • The processed results will be either 'counts' or 'expval' depending on the job type
            • 'job_id'  or 'id'
        """
        
        return cls(
            id = data.get("id"),
            job_id=data.get("job_id"),
            metadata=data.get("metadata", {}),
            processed_results=data.get("processed_results"),
            mitigation_params=data.get("mitigation_params"),
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