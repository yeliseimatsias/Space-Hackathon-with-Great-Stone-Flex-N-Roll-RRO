from pydantic import BaseModel, ConfigDict


class Chat(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int


class Contact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    phone_number: str


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message_id: int
    chat: Chat
    text: str | None = None
    contact: Contact | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update_id: int
    message: Message | None = None
