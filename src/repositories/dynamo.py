# pyright: reportAny=false, reportExplicitAny=false, reportUnannotatedClassAttribute=false
from typing import Any, override

from src.models import ActionEvent
from src.repositories.protocol import EventRepositoryProtocol


class DynamoDBRepository(EventRepositoryProtocol):
    def __init__(self, table: Any):
        self.table = table

    @override
    async def setup(self) -> None:
        # DynamoDB tables are typically provisioned via IaC (Terraform/CloudFormation)
        pass

    @override
    async def create_event(self, event: ActionEvent) -> ActionEvent:
        # Single-Table Design mapping
        item = event.model_dump(mode="json")
        item["PK"] = f"REPO#{event.repository}"
        item["SK"] = f"EVENT#{event.timestamp.isoformat()}#{event.commit_sha}"
        item["GSI1PK"] = f"WORKFLOW#{event.workflow_name}"
        item["GSI1SK"] = item["SK"]

        # DynamoDB uses strings for ID, let's use the SK as a unique ID if none provided
        if not item.get("id"):
            item["id"] = item["SK"]
            event.id = item["SK"]

        await self.table.put_item(Item=item)
        return event

    @override
    async def get_events_by_repository(self, repository: str) -> list[ActionEvent]:
        response = await self.table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
            ExpressionAttributeValues={
                ":pk": f"REPO#{repository}",
                ":sk": "EVENT#",
            },
            ScanIndexForward=False,  # Sort descending
        )
        items = response.get("Items", [])
        return [ActionEvent(**item) for item in items]
