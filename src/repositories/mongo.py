# pyright: reportAny=false, reportExplicitAny=false, reportUnannotatedClassAttribute=false
import uuid
from datetime import UTC
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
        self, repository: str, skip: int = 0, limit: int = 25, search: str | None = None
    ) -> list[ActionEvent]:
        query: dict[str, Any] = {"repository": repository}
        if search:
            query["$or"] = [
                {"workflow_name": {"$regex": search, "$options": "i"}},
                {"commit_sha": {"$regex": search, "$options": "i"}},
            ]

        cursor = (
            self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        )
        documents = await cursor.to_list(length=None)

        events: list[ActionEvent] = []
        for doc in documents:
            doc["id"] = doc.pop("_id")
            events.append(ActionEvent(**doc))

        return events

    @override
    async def get_event_by_id(self, event_id: str) -> ActionEvent | None:
        doc = await self.collection.find_one({"_id": event_id})
        if not doc:
            return None
        doc["id"] = doc.pop("_id")
        return ActionEvent(**doc)

    @override
    async def get_all_events(
        self,
        skip: int = 0,
        limit: int = 25,
        search: str | None = None,
        group_key: str | None = None,
        group_val: str | None = None,
    ) -> list[ActionEvent]:
        query: dict[str, Any] = {}

        and_clauses: list[dict[str, Any]] = []

        if search:
            and_clauses.append(
                {
                    "$or": [
                        {"workflow_name": {"$regex": search, "$options": "i"}},
                        {"commit_sha": {"$regex": search, "$options": "i"}},
                        {"repository": {"$regex": search, "$options": "i"}},
                    ]
                }
            )

        if group_key and group_val:
            and_clauses.append(
                {
                    "$or": [
                        {f"tags.{group_key}": group_val},
                        {f"custom_data.{group_key}": group_val},
                        {group_key: group_val},
                    ]
                }
            )

        if and_clauses:
            query["$and"] = and_clauses

        cursor = (
            self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        )
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
        self,
        repository: str,
        metric_key: str,
        time_period: str,
        is_sum: bool,
        artifact_name: str | None = None,
    ) -> list[dict[str, float | int]]:
        from datetime import datetime, timedelta

        now = datetime.now(UTC)
        if time_period == "day":
            cutoff = now - timedelta(days=1)
        elif time_period == "week":
            cutoff = now - timedelta(days=7)
        elif time_period == "month":
            cutoff = now - timedelta(days=30)
        else:  # year
            cutoff = now - timedelta(days=365)

        unit = "hour"
        if time_period in ["week", "month"]:
            unit = "day"
        elif time_period == "year":
            unit = "week"

        group_op = (
            {"$sum": f"$metrics.{metric_key}"}
            if is_sum
            else {"$avg": f"$metrics.{metric_key}"}
        )

        match_stage = {
            "repository": repository,
            f"metrics.{metric_key}": {"$ne": None},
            "timestamp": {"$gte": cutoff.isoformat()},
        }
        if artifact_name:
            match_stage["artifact.name"] = artifact_name

        pipeline = [
            {"$match": match_stage},
            {"$addFields": {"parsed_date": {"$toDate": "$timestamp"}}},
            {
                "$group": {
                    "_id": {"$dateTrunc": {"date": "$parsed_date", "unit": unit}},
                    "value": group_op,
                }
            },
            {"$sort": {"_id": 1}},
        ]

        cursor = self.collection.aggregate(pipeline)
        docs = await cursor.to_list(length=None)

        return [
            {"x": int(d["_id"].timestamp() * 1000), "y": d["value"]}
            for d in docs
            if d["_id"] is not None
        ]

    @override
    async def get_unique_repositories(self) -> list[str]:
        return await self.collection.distinct("repository")

    @override
    async def get_available_metrics(self, repository: str | None = None) -> list[str]:
        # To get unique metric keys, we can use an aggregation pipeline.
        # We need to project the object keys of `metrics` and unwind them.
        match_stage: dict[str, Any] = {"metrics": {"$type": "object"}}
        if repository:
            match_stage["repository"] = repository

        pipeline = [
            {"$match": match_stage},
            {"$project": {"keys": {"$objectToArray": "$metrics"}}},
            {"$unwind": "$keys"},
            {"$match": {"keys.v": {"$type": "number"}}},  # Only numeric metrics
            {"$group": {"_id": "$keys.k"}},
        ]

        cursor = self.collection.aggregate(pipeline)
        docs = await cursor.to_list(length=None)
        return [doc["_id"] for doc in docs]
