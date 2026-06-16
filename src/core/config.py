# pyright: reportAny=false, reportExplicitAny=false
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors(v: Any) -> list[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    return v  # pyright: ignore[reportReturnType]


class Settings(BaseSettings):
    database_type: Literal["dynamodb", "mongodb", "mock"] = Field(
        description="The backend database to use (dynamodb, mongodb, or mock)"
    )

    dynamo_table_name: str | None = Field(
        default=None, description="DynamoDB table name"
    )
    aws_region: str | None = Field(default=None, description="AWS Region for DynamoDB")

    mongo_uri: str | None = Field(default=None, description="MongoDB connection URI")
    mongo_db_name: str | None = Field(default=None, description="MongoDB database name")

    redis_url: str | None = Field(default=None, description="Redis connection URI")

    rate_limit_events: str = Field(
        default="100/minute", description="Rate limit for event endpoints"
    )
    rate_limit_api: str = Field(
        default="50/minute", description="Rate limit for general API endpoints"
    )

    cors_origins: Annotated[list[str], BeforeValidator(parse_cors)] = Field(
        default_factory=list, description="Allowed CORS origins"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")  # pyright: ignore[reportUnannotatedClassAttribute]


settings = Settings()  # pyright: ignore[reportCallIssue]
