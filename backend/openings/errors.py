class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def missing(resource="Record"):
    raise DomainError(404, "not_found", f"{resource} was not found.")


def conflict(message="This record changed. Reload it before saving.", details=None):
    raise DomainError(409, "conflict", message, details)


def invalid(error):
    """A pydantic ValidationError as the 422 validation DomainError."""
    details = [
        {"field": list(item["loc"]), "message": item["msg"], "type": item["type"]}
        for item in error.errors(include_url=False, include_context=False)
    ]
    return DomainError(422, "validation", "Some fields need attention.", details)
