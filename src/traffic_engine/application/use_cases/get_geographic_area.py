"""Use case for retrieving one preprocessed geographic area."""

from __future__ import annotations

from ...domain.exceptions import GeographicAreaNotFoundError
from ...domain.models import GeographicArea
from ..ports import GeographicAreaRepository


class GetGeographicAreaUseCase:
    def __init__(self, repository: GeographicAreaRepository) -> None:
        self.repository = repository

    def execute(self, area_id: str) -> GeographicArea:
        area = self.repository.get(area_id)
        if area is None:
            raise GeographicAreaNotFoundError(
                f"Geographic area '{area_id}' is not available."
            )
        return area
