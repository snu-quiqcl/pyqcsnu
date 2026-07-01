"""
PyQCSNU - Python Client for SNU Quantum Computing Services
"""

__version__ = "1.0.0"

from .client import SNUQ
from .backend import SNUQBackend, SNUQJob
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
Backend = SNUQBackend
from .exceptions import (
    QuantumClientError,
    AuthenticationError,
    JobError,
    IonLossError,
    ModeInterruptedError,
    ExperimentError,
    BackendError
)

__all__ = [
    'SNUQ',
    'SNUQBackend',
    'SNUQJob',
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
    'ModeInterruptedError',
    'ExperimentError',
    'BackendError',
]
