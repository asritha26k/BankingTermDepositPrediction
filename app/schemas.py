# app/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, Optional


class InputData(BaseModel):
    age: int = Field(..., example=35, description="Age of the client")
    job: Literal[
        'admin.', 'blue-collar', 'entrepreneur', 'housemaid', 'management',
        'retired', 'self-employed', 'services', 'student', 'technician',
        'unemployed', 'unknown'
    ] = Field(..., example="management", description="Type of job")
    marital: Literal[
        'divorced', 'married', 'single', 'unknown'
    ] = Field(..., example="married", description="Marital status")
    education: Literal[
        'basic.4y', 'basic.6y', 'basic.9y', 'high.school',
        'illiterate', 'professional.course', 'university.degree', 'unknown'
    ] = Field(..., example="university.degree", description="Education level")
    default: Literal[
        'no', 'yes', 'unknown'
    ] = Field(..., example="no", description="Has credit in default?")
    balance: int = Field(..., example=1200, description="Average yearly balance, in euros")
    housing: Literal[
        'no', 'yes', 'unknown'
    ] = Field(..., example="yes", description="Has housing loan?")
    loan: Literal[
        'no', 'yes', 'unknown'
    ] = Field(..., example="no", description="Has personal loan?")
    contact: Literal[
        'cellular', 'telephone'
    ] = Field(..., example="cellular", description="Contact communication type")
    day: int = Field(..., ge=1, le=31, example=5, description="Last contact day of month")
    month: Literal[
        'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    ] = Field(..., example="may", description="Last contact month of year")
    duration: int = Field(..., ge=0, example=120, description="Last contact duration in seconds")
    campaign: int = Field(..., ge=1, example=2, description="Number of contacts performed during this campaign")
    pdays: int = Field(..., example=999, description="Number of days passed after last contact from previous campaign (999 means not previously contacted)")
    previous: int = Field(..., ge=0, example=0, description="Number of contacts performed before this campaign")
    poutcome: Literal[
        'failure', 'nonexistent', 'other', 'success'
    ] = Field(..., example="nonexistent", description="Outcome of the previous marketing campaign")

    class Config:
        schema_extra = {
            "example": {
                "age": 35,
                "job": "management",
                "marital": "married",
                "education": "university.degree",
                "default": "no",
                "balance": 1200,
                "housing": "yes",
                "loan": "no",
                "contact": "cellular",
                "day": 5,
                "month": "may",
                "duration": 120,
                "campaign": 2,
                "pdays": 999,
                "previous": 0,
                "poutcome": "nonexistent"
            }
        }

class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., description="Unique ID of the asynchronous task")
    status: str = Field(..., description="Current status of the task (e.g., PENDING, SUCCESS, FAILURE, PROGRESS)")
    message: str = Field(..., description="A human-readable message about the task's current state")
    results_download_url: Optional[str] = Field(None, description="URL to download the results file, if the task is successful")

