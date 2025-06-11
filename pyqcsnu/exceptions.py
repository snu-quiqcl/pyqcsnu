"""
Custom exceptions for the quantum computing client.
"""

class QuantumClientError(Exception):
    """Base exception for all quantum client errors."""
    pass

class AuthenticationError(QuantumClientError):
    """Raised when authentication fails or is missing."""
    pass

class APIError(QuantumClientError):
    """Raised when an API request fails."""
    pass

class JobError(QuantumClientError):
    """Raised when a job operation fails."""
    pass

class BackendError(QuantumClientError):
    """Raised when a backend operation fails."""
    pass

class CircuitError(QuantumClientError):
    """Raised when there's an error with circuit operations."""
    pass

class ResultError(QuantumClientError):
    """Raised when there's an error processing results."""
    pass

class TimeoutError(QuantumClientError):
    """Raised when an operation times out."""
    pass

class ValidationError(QuantumClientError):
    """Raised when input validation fails."""
    pass 