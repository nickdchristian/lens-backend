# pyright: reportAny=false, reportExplicitAny=false, reportUnannotatedClassAttribute=false
import uuid
from typing import Any, override

import pymongo

from src.models import ActionEvent
from src.repositories.protocol import EventRepositoryProtocol


class MongoRepository(EventRepositoryProtocol):
    def __init__(self, collection: Any):
        """Initialize the MongoDB repository with a motor Collection instance."""
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
        self, repository: str, skip: int = 0, limit: int = 25
    ) -> list[ActionEvent]:
        cursor = (
            self.collection.find({"repository": repository})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )
        documents = await cursor.to_list(length=None)

        events: list[ActionEvent] = []
        for doc in documents:
            doc["id"] = doc.pop("_id")
            events.append(ActionEvent(**doc))

        return events

    @override
    async def get_all_events(self, skip: int = 0, limit: int = 25) -> list[ActionEvent]:
        cursor = self.collection.find({}).sort("timestamp", -1).skip(skip).limit(limit)
        documents = await cursor.to_list(length=None)

        events: list[ActionEvent] = []
        for doc in documents:
            doc["id"] = doc.pop("_id")
            events.append(ActionEvent(**doc))

        return events

    @override
    async def ping(self) -> bool:
        try:
            await self.collection.database.client.admin.command("ping")
            return True
        except Exception:
            return False

    @override
    async def get_aggregated_metrics(
        self, repository: str, metric_key: str, time_period: str, is_sum: bool
    ) -> list[dict[str, float | int]]:
        unit = "hour"
        if time_period in ["week", "month"]:
            unit = "day"
        elif time_period == "year":
            unit = "week"
            
        group_op = {"$sum": f"$metrics.{metric_key}"} if is_sum else {"$avg": f"$metrics.{metric_key}"}

        pipeline = [
            {"$match": {
                "repository": repository,
                f"metrics.{metric_key}": {"$ne": None}
            }},
            {"$addFields": {"parsed_date": {"$toDate": "$timestamp"}}},
            {"$group": {
                "_id": {
                    "$dateTrunc": {
                        "date": "$parsed_date",
                        "unit": unit
                    }
                },
                "value": group_op
            }},
            {"$sort": {"_id": 1}}
        ]
        
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        data = []
        for r in results:
            dt = r["_id"]
            if dt:
                data.append({"x": int(dt.timestamp() * 1000), "y": r["value"]})
                
        return data
