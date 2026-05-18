from sqlmodel import SQLModel, Field

class Settings(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int
    
    save_deleted_messages: bool = Field(default=True)
    save_deleted_photos: bool = Field(default=True)
    save_deleted_videos: bool = Field(default=True)
    save_deleted_voices: bool = Field(default=True)
    save_deleted_video_notes: bool = Field(default=True)
    save_deleted_documents: bool = Field(default=True)
    save_edited_messages: bool = Field(default=True)
    
    save_auto_photos: bool = Field(default=True)
    save_auto_videos: bool = Field(default=True)
    save_auto_video_notes: bool = Field(default=True)
    save_auto_voices: bool = Field(default=True)
    save_auto_documents: bool = Field(default=True)