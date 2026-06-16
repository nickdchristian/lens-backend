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
        self, repository: str, limit: int = 100
    ) -> list[ActionEvent]:
        """Fetches events for a specific repository."""
        ...

    async def ping(self) -> bool:
        """Verify the database connection is healthy."""
        ...
