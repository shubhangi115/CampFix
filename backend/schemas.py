"""Request models and the allowed complaint categories and statuses."""

from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

Category = Literal[
    "Wi-Fi and Internet", "Classroom Infrastructure", "Water and Sanitation",
    "Electrical Issues", "Hostel Issues", "Library Issues", "Cleanliness", "Other",
]
Status = Literal["Pending", "In Progress", "Resolved"]
Email = Annotated[EmailStr, Field(max_length=150)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Roll = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class Login(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128, repr=False)


class Registration(Login):
    full_name: Name
    roll_number: Roll
    department: Name
    password: str = Field(min_length=8, max_length=128, repr=False)
    confirm_password: str = Field(max_length=128, repr=False)

    @model_validator(mode="after")
    def check_password(self):
        if not self.password.strip() or self.password != self.confirm_password:
            raise ValueError("Enter a valid password and make sure both passwords match.")
        return self


class ComplaintInput(BaseModel):
    title: ShortText
    category: Category
    description: Description
    location: ShortText


class StatusUpdate(BaseModel):
    status: Literal["In Progress", "Resolved"]
    resolution_note: Note | None = None
