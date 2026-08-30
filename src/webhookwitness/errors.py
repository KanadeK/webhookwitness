"""Expected user-facing errors."""


class WebhookWitnessError(Exception):
    """Base class for expected failures."""


class ScenarioError(WebhookWitnessError):
    """The scenario cannot be parsed or safely executed."""


class SetupError(WebhookWitnessError):
    """The declared local service or probe could not be executed."""
