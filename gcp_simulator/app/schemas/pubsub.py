from pydantic import BaseModel


class TopicCreate(BaseModel):
    labels: dict[str, str] = {}


class SubscriptionCreate(BaseModel):
    topic: str
    pushConfig: dict | None = None
    ackDeadlineSeconds: int = 10
    labels: dict[str, str] = {}


class PublishRequest(BaseModel):
    messages: list[dict]


class PullRequest(BaseModel):
    maxMessages: int = 10
    returnImmediately: bool = False


class AcknowledgeRequest(BaseModel):
    ackIds: list[str]


class ModifyAckDeadlineRequest(BaseModel):
    ackIds: list[str]
    ackDeadlineSeconds: int
