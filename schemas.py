
from pydantic import BaseModel, validator, ValidationError
from typing import Optional
from datetime import datetime
from fastapi import UploadFile, File
from bson import ObjectId

class TeacherCreate(BaseModel):
    username: str
    password: str

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class StudentCreate(BaseModel):
    name: str
    roll_number: str
    password: str

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class LectureCreate(BaseModel):
    teacher_id: str
    subject: str
    date: str  # Format: YYYY-MM-DD
    start_time: str  # Format: HH:MM:SS
    end_time: str    # Format: HH:MM:SS

    @validator('teacher_id')
    def validate_teacher_id(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid teacher_id. Must be a valid ObjectId.")
        return v

    @validator('date')
    def validate_date(cls, v):
        try:
            return datetime.strptime(v, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError('Invalid date format. Use YYYY-MM-DD')

    @validator('start_time', 'end_time')
    def validate_time(cls, v):
        try:
            datetime.strptime(v, '%H:%M:%S')
            return v
        except ValueError:
            raise ValueError('Invalid time format. Use HH:MM:SS')

    @validator('end_time')
    def validate_time_range(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v
class AttendanceMark(BaseModel):
    lecture_id: str
    student_id: str
    location: Optional[str] = None
    device_info: Optional[str] = None

    @validator('lecture_id', 'student_id')
    def validate_object_ids(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError(f"Invalid ObjectId: {v}")
        return v

class QRCodeGenerate(BaseModel):
    lecture_id: str

    @validator('lecture_id')
    def validate_lecture_id(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid lecture_id. Must be a valid ObjectId.")
        return v
class QRCodeResponse(BaseModel):
    qr_code: str
    expiry: datetime
    name: str
    roll_number: str
    password: str

class LectureCreate(BaseModel):
    teacher_id: str
    subject: str
    date: str
    start_time: str
    end_time: str

class AttendanceMark(BaseModel):
    lecture_id: str
    student_id: str

class QRCodeGenerate(BaseModel):
    lecture_id: str

class QRCodeScan(BaseModel):
    file: UploadFile