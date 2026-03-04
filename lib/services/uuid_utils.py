import uuid

from fastapi import HTTPException


def ensure_uuid(value: uuid.UUID | str, field_name: str) -> uuid.UUID:
    """Coerce *value* to ``uuid.UUID``, raising HTTP 400 on invalid formats."""

    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name} format: {value}"
        )
