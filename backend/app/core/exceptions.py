class DomainError(Exception):
    """Base class for errors raised by the service layer."""


class NotFoundError(DomainError):
    def __init__(self, resource: str, resource_id: int) -> None:
        super().__init__(f"{resource} {resource_id} not found")
        self.resource = resource
        self.resource_id = resource_id


class ValidationError(DomainError):
    pass
