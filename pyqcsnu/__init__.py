"""
PyQCSNU - Python Client for SNU Quantum Computing Services
"""

__version__ = "0.1.0"

from .client import SNUQ
from .models import (
    Circuit,
    BlackholeJob,
    BlackholeExperiment,
    BlackholeResult,
    SNUBackend,
    MitigationParams
)

Job = BlackholeJob
Result = BlackholeResult
Backend = SNUBackend
from .exceptions import (
    QuantumClientError,
    AuthenticationError,
    JobError,
    IonLossError,
    ExperimentError,
    BackendError
)

__all__ = [
    'SNUQ',
    'Circuit',
    'Job',
    'Result',
    'Backend',
    'BlackholeJob',
    'BlackholeExperiment',
    'BlackholeResult',
    'SNUBackend',
    'MitigationParams',
    'QuantumClientError',
    'AuthenticationError',
    'JobError',
    'IonLossError',
    'ExperimentError',
    'BackendError',
]
