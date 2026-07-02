from typing import Protocol

from src.models import ActionEvent


class EventRepositoryProtocol(Protocol):
    async def setup(self) -> None:
        """Runs initialization logic (e.g. creating indexes)."""
        ...

    async def create_event(self, event: ActionEvent) -> ActionEvent:
        """Saves a new action event to the database."""
        ...

    async def get_events_by_repository(
        self, repository: str, skip: int = 0, limit: int = 25, search: str | None = None
    ) -> list[ActionEvent]:
        """Fetches events for a specific repository."""
        ...

    async def get_all_events(
        self,
        skip: int = 0,
        limit: int = 25,
        search: str | None = None,
        group_key: str | None = None,
        group_val: str | None = None,
    ) -> list[ActionEvent]:
        """Fetches all events across all repositories."""
        ...

    async def get_event_by_id(self, event_id: str) -> ActionEvent | None:
        """Fetches a specific event by its unique ID."""
        ...

    async def ping(self) -> bool:
        """Verify the database connection is healthy."""
        ...

    async def get_aggregated_metrics(
        self, repository: str, metric_key: str, time_period: str, is_sum: bool
    ) -> list[dict[str, float | int]]:
        """Fetch aggregated metrics bucketed by time period."""
        ...

    async def get_unique_repositories(self) -> list[str]:
        """Fetch a list of all unique repositories."""
        ...

    async def get_available_metrics(self, repository: str | None = None) -> list[str]:
        """Fetch a list of all numeric metric keys available, optionally filtered by repository."""
        ...
