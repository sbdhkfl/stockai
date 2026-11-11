"""Typed errors for the fairvalue engine. Missing/invalid data must be explicit,
never silently defaulted."""


class FairValueError(ValueError):
    """Base class for all financial-engine input/domain errors."""


class NotMeaningfulError(FairValueError):
    """The metric/model is not meaningful for these inputs (e.g. negative EPS P/E)."""


class NotSuitableError(FairValueError):
    """The model is unsuitable for this company type (e.g. DCF for a bank)."""


class DataQualityError(FairValueError):
    """Input failed a hard data-quality rule (currency mismatch, negative shares...)."""
