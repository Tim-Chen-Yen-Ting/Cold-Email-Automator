from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class Contact(BaseModel):
    name: str
    email: str
    company: str
    role: Optional[str] = ""
    website: Optional[str] = ""
    linkedin: Optional[str] = ""
    source_url: Optional[str] = ""
    notes: Optional[str] = Field(default="", description="1-2 sentence personalization hook")


class ContactList(BaseModel):
    contacts: list[Contact]


class EmailDraft(BaseModel):
    subject: str
    body: str
    appeal_angle: str = Field(description="Short phrase describing the hook used, e.g. 'recent product launch'")
