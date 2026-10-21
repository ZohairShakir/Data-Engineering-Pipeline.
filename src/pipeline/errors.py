"""Pipeline-specific exception hierarchy."""


class PipelineError(RuntimeError):
    """Base class for expected pipeline failures."""


class ExtractionError(PipelineError):
    """Raised when source files cannot be discovered or parsed safely."""


class TransformationError(PipelineError):
    """Raised when source data cannot produce a usable analytical dataset."""


class LoadError(PipelineError):
    """Raised when transformed data cannot be committed to the warehouse."""
