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
        self, repository: str, skip: int = 0, limit: int = 25, search: str | None = None
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
            ScanIndexForward=False,
            Limit=skip + limit,
        )
        items = response.get("Items", [])
        
        if search:
            s = search.lower()
            items = [item for item in items if s in item.get("workflow_name", "").lower() or s in item.get("commit_sha", "").lower()]

        if skip > 0:
            items = items[skip:]
        return [ActionEvent(**item) for item in items]

    @override
    async def get_all_events(
        self,
        skip: int = 0,
        limit: int = 25,
        search: str | None = None,
        group_key: str | None = None,
        group_val: str | None = None,
    ) -> list[ActionEvent]:
        # For filtering, we might need more items than requested if we filter client-side.
        # But keeping it simple for the reference implementation:
        fetch_limit = skip + limit
        if search or (group_key and group_val):
            fetch_limit = 5000  # Fetch more to allow for client-side filtering

        response = await self.table.query(
            IndexName="GSI2",
            KeyConditionExpression="GSI2PK = :pk",
            ExpressionAttributeValues={
                ":pk": "EVENT",
            },
            ExpressionAttributeNames={"#ts": "timestamp"},
            ProjectionExpression=(
                "id, repository, commit_sha, workflow_name, artifact_version, #ts, tags, custom_data"
            ),
            ScanIndexForward=False,
            Limit=fetch_limit,
        )
        items: list[dict[str, Any]] = response.get("Items", [])
        
        if search:
            s = search.lower()
            items = [item for item in items if s in item.get("workflow_name", "").lower() or s in item.get("commit_sha", "").lower() or s in item.get("repository", "").lower()]

        if group_key and group_val:
            filtered_items = []
            for item in items:
                matches = False
                if item.get("tags", {}).get(group_key) == group_val:
                    matches = True
                elif item.get("custom_data", {}).get(group_key) == group_val:
                    matches = True
                elif item.get(group_key) == group_val:
                    matches = True
                if matches:
                    filtered_items.append(item)
            items = filtered_items

        if skip > 0:
            items = items[skip:]
            
        # Ensure we only return the limit requested
        items = items[:limit]

        return [ActionEvent(**item) for item in items]

    @override
    async def get_event_by_id(self, event_id: str) -> ActionEvent | None:
        # Scanning is not ideal for DynamoDB but works for this reference implementation
        response = await self.table.scan(
            FilterExpression="id = :id",
            ExpressionAttributeValues={":id": event_id},
            Limit=1
        )
        items = response.get("Items", [])
        if not items:
            return None
        return ActionEvent(**items[0])

    @override
    async def ping(self) -> bool:
        try:
            async with self.table.meta.client as client:
                await client.describe_table(TableName=self.table.name)
            return True
        except Exception:
            return False

    @override
    async def get_aggregated_metrics(
        self, repository: str, metric_key: str, time_period: str, is_sum: bool
    ) -> list[dict[str, float | int]]:
        from datetime import datetime, timezone, timedelta
        import datetime as dt_lib
        
        now = datetime.now(timezone.utc)
        if time_period == "day":
            cutoff = now - timedelta(days=1)
        elif time_period == "week":
            cutoff = now - timedelta(days=7)
        elif time_period == "month":
            cutoff = now - timedelta(days=30)
        else: # year
            cutoff = now - timedelta(days=365)
            
        cutoff_iso = cutoff.isoformat()
        
        response = await self.table.query(
            KeyConditionExpression="PK = :pk AND SK >= :sk_min",
            ExpressionAttributeValues={
                ":pk": f"REPO#{repository}",
                ":sk_min": f"EVENT#{cutoff_iso}",
            },
            ExpressionAttributeNames={"#ts": "timestamp", "#metrics": "metrics"},
            ProjectionExpression="#ts, #metrics",
            ScanIndexForward=False,
            Limit=5000,
        )
        
        items = response.get("Items", [])
        buckets: dict[str, dict[str, Any]] = {}
        
        for item in items:
            metrics = item.get("metrics", {})
            if metric_key not in metrics or metrics[metric_key] is None:
                continue
                
            val = metrics[metric_key]
            ts_str = item.get("timestamp")
            if not ts_str:
                continue
                
            try:
                dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except ValueError:
                continue
                
            if time_period == "day":
                b_key = f"{dt.year}-{dt.month:02d}-{dt.day:02d}-{dt.hour:02d}"
                b_dt = datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=timezone.utc)
            elif time_period in ["week", "month"]:
                b_key = f"{dt.year}-{dt.month:02d}-{dt.day:02d}"
                b_dt = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
            else: # year
                days_to_subtract = dt.weekday() + 1 if dt.weekday() != 6 else 0
                b_dt_temp = dt - dt_lib.timedelta(days=days_to_subtract)
                b_dt = datetime(b_dt_temp.year, b_dt_temp.month, b_dt_temp.day, tzinfo=timezone.utc)
                b_key = f"{b_dt.year}-{b_dt.month:02d}-{b_dt.day:02d}"

            if b_key not in buckets:
                buckets[b_key] = {"sum": 0.0, "count": 0, "date": b_dt}
                
            buckets[b_key]["sum"] += float(val)
            buckets[b_key]["count"] += 1
            
        data = []
        for b in buckets.values():
            y_val = b["sum"] if is_sum else (b["sum"] / b["count"])
            data.append({"x": int(b["date"].timestamp() * 1000), "y": y_val})
            
        data.sort(key=lambda i: i["x"])
        return data

    @override
    async def get_unique_repositories(self) -> list[str]:
        response = await self.table.scan(
            ProjectionExpression="repository",
            Limit=5000
        )
        repos = {item.get("repository") for item in response.get("Items", []) if item.get("repository")}
        return list(repos)

    @override
    async def get_available_metrics(self, repository: str | None = None) -> list[str]:
        if repository:
            response = await self.table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
                ExpressionAttributeValues={
                    ":pk": f"REPO#{repository}",
                    ":sk": "EVENT#",
                },
                ProjectionExpression="metrics",
                Limit=1000
            )
        else:
            response = await self.table.scan(
                ProjectionExpression="metrics",
                Limit=1000
            )
            
        metrics = set()
        for item in response.get("Items", []):
            m = item.get("metrics", {})
            for k, v in m.items():
                if isinstance(v, (int, float)):
                    metrics.add(k)
                    
        return list(metrics)
