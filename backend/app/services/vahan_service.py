"""
services/vahan_service.py

Mock VAHAN/SARTHI (central government vehicle registry) lookup. Stands in
for the real government API so the platform can demonstrate cross-referencing
a detected plate against vehicle ownership/status/theft records without any
external network dependency.
"""
from typing import Any, Dict

_MOCK_VAHAN_DB: Dict[str, Dict[str, Any]] = {
    "DL01AB1234": {"owner": "John Doe", "status": "ACTIVE", "stolen": False},
    "UP32XYZ999": {"owner": "Jane Smith", "status": "EXPIRED", "stolen": True},
    "MH12CD5678": {"owner": "Amit Kumar", "status": "ACTIVE", "stolen": False},
    "KA05EF4321": {"owner": "Priya Nair", "status": "ACTIVE", "stolen": True},
}

_NOT_FOUND: Dict[str, Any] = {"owner": None, "status": "NOT_FOUND", "stolen": False}


async def lookup_vehicle(plate: str) -> Dict[str, Any]:
    """Look up a normalised plate in the mock VAHAN registry.

    Returns the mock record, or a NOT_FOUND default if the plate isn't
    registered. Async signature mirrors a real HTTP call to a government API.
    """
    return _MOCK_VAHAN_DB.get(plate, dict(_NOT_FOUND))
