from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_type: Literal["dynamodb", "mongodb", "mock"] = Field(
        description="The backend database to use (dynamodb, mongodb, or mock)"
    )

    # DynamoDB Settings
    dynamo_table_name: str | None = Field(
        default=None, description="DynamoDB table name"
    )
    aws_region: str | None = Field(default=None, description="AWS Region for DynamoDB")

    # MongoDB Settings
    mongo_uri: str | None = Field(default=None, description="MongoDB connection URI")
    mongo_db_name: str | None = Field(default=None, description="MongoDB database name")

    # Rate Limiting
    rate_limit_events: str = Field(
        default="100/minute", description="Rate limit for event endpoints"
    )
    rate_limit_api: str = Field(
        default="50/minute", description="Rate limit for general API endpoints"
    )

    # CORS
    cors_origins: list[str] = Field(
        default_factory=list, description="Allowed CORS origins"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")  # pyright: ignore[reportUnannotatedClassAttribute]


settings = Settings()  # pyright: ignore[reportCallIssue]
