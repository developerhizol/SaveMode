from sqlmodel import SQLModel, Field
from datetime import datetime

class BotStats(SQLModel, table=True):
    __tablename__ = "bot_stats"
    
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(unique=True, index=True)
    username: str | None = Field(default=None)
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)
    is_connected: bool = Field(default=False)