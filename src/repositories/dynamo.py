# pyright: reportAny=false, reportExplicitAny=false, reportUnannotatedClassAttribute=false
from typing import Any, override

from src.models import ActionEvent
from src.repositories.protocol import EventRepositoryProtocol


class DynamoDBRepository(EventRepositoryProtocol):
    def __init__(self, table: Any):
        """Initialize the DynamoDB repository with a boto3 Table instance."""
        self.table = table

    @override
    async def setup(self) -> None:
        pass

    @override
    async def create_event(self, event: ActionEvent) -> ActionEvent:
        item = event.model_dump(mode="json")
        item["PK"] = f"REPO#{event.repository}"
        item["SK"] = f"EVENT#{event.timestamp.isoformat()}#{event.commit_sha}"
        item["GSI1PK"] = f"WORKFLOW#{event.workflow_name}"
        item["GSI1SK"] = item["SK"]
        item["GSI2PK"] = "EVENT"
        item["GSI2SK"] = item["SK"]

        if not item.get("id"):
            item["id"] = item["SK"]
            event.id = item["SK"]

        await self.table.put_item(Item=item)
        return event

    @override
    async def get_events_by_repository(
        self, repository: str, skip: int = 0, limit: int = 25
    ) -> list[ActionEvent]:
        # DynamoDB doesn't natively support skip/offset efficiently without a full scan
        # For simplicity in this dummy impl, we just limit the query.
        response = await self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": f"REPO#{repository}",
                ":sk": "EVENT#",
            },
            ExpressionAttributeNames={"#ts": "timestamp"},
            ProjectionExpression=(
                "id, repository, commit_sha, workflow_name, artifact_version, #ts, tags"
            ),
            ScanIndexForward=False,  # Sort descending
            Limit=skip + limit,
        )
        items = response.get("Items", [])
        if skip > 0:
            items = items[skip:]
        return [ActionEvent(**item) for item in items]

    @override
    async def get_all_events(self, skip: int = 0, limit: int = 25) -> list[ActionEvent]:
        # Use GSI2 to fetch all events sorted by timestamp
        response = await self.table.query(
            IndexName="GSI2",
            KeyConditionExpression="GSI2PK = :pk",
            ExpressionAttributeValues={
                ":pk": "EVENT",
            },
            ExpressionAttributeNames={"#ts": "timestamp"},
            ProjectionExpression=(
                "id, repository, commit_sha, workflow_name, artifact_version, #ts, tags"
            ),
            ScanIndexForward=False,  # Sort descending
            Limit=skip + limit,
        )
        items: list[dict[str, Any]] = response.get("Items", [])
        if skip > 0:
            items = items[skip:]

        return [ActionEvent(**item) for item in items]

    @override
    async def ping(self) -> bool:
        try:
            async with self.table.meta.client as client:
                await client.describe_table(TableName=self.table.name)
            return True
        except Exception:
            return False
