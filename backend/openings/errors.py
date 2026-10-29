class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def missing(resource="Record"):
    raise DomainError(404, "not_found", f"{resource} was not found.")


def conflict(message="This record changed. Reload it before saving."):
    raise DomainError(409, "conflict", message)
