class BitrixAPIError(Exception):
    """Bitrix24 REST API returned an error or invalid response."""


class EmployeeNotFoundError(Exception):
    """Requested employee does not exist."""


class KnowledgeNotFoundError(Exception):
    """Knowledge base entry was not found."""
