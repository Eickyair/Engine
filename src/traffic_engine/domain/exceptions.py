"""Domain exceptions for traffic engine business rules."""


class TrafficEngineError(Exception):
    """Base domain error."""


class GeographicAreaNotFoundError(TrafficEngineError):
    """Raised when a geographic area is not available."""


class SimulationNotFoundError(TrafficEngineError):
    """Raised when a simulation record does not exist."""


class SimulationNotReadyError(TrafficEngineError):
    """Raised when a simulation result is requested before it is available."""


class SimulationCancellationError(TrafficEngineError):
    """Raised when a simulation cannot be cancelled."""


class SimulationConfigurationError(TrafficEngineError):
    """Raised when a simulation model configuration is invalid."""


class RouteSelectionError(TrafficEngineError):
    """Raised when no valid topological route can be selected."""
