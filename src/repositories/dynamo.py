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

        if not item.get("id"):
            item["id"] = item["SK"]
            event.id = item["SK"]

        await self.table.put_item(Item=item)
        return event

    @override
    async def get_events_by_repository(
        self, repository: str, limit: int = 100
    ) -> list[ActionEvent]:
        response = await self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": f"REPO#{repository}",
                ":sk": "EVENT#",
            },
            ScanIndexForward=False,  # Sort descending
            Limit=limit,
        )
        items = response.get("Items", [])
        return [ActionEvent(**item) for item in items]

    @override
    async def ping(self) -> bool:
        try:
            async with self.table.meta.client as client:
                await client.describe_table(TableName=self.table.name)
            return True
        except Exception:
            return False
