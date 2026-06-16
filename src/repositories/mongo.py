# pyright: reportAny=false, reportExplicitAny=false, reportUnannotatedClassAttribute=false
import uuid
from typing import Any, override

import pymongo

from src.models import ActionEvent
from src.repositories.protocol import EventRepositoryProtocol


class MongoRepository(EventRepositoryProtocol):
    def __init__(self, collection: Any):
        self.collection = collection

    @override
    async def setup(self) -> None:
        await self.collection.create_index(
            [("repository", pymongo.ASCENDING), ("timestamp", pymongo.DESCENDING)]
        )

    @override
    async def create_event(self, event: ActionEvent) -> ActionEvent:
        if not event.id:
            event.id = str(uuid.uuid4())

        doc = event.model_dump(mode="json")
        doc["_id"] = doc.pop("id")

        await self.collection.insert_one(doc)
        return event

    @override
    async def get_events_by_repository(
        self, repository: str, limit: int = 100
    ) -> list[ActionEvent]:
        cursor = (
            self.collection.find({"repository": repository})
            .sort("timestamp", -1)
            .limit(limit)
        )
        documents = await cursor.to_list(length=None)

        events: list[ActionEvent] = []
        for doc in documents:
            doc["id"] = doc.pop("_id")
            events.append(ActionEvent(**doc))

        return events
