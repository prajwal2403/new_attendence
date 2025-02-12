# models.py
from mongoengine import Document, StringField, ReferenceField, DateTimeField, BooleanField, signals
from datetime import datetime, timedelta
import bcrypt

class Teacher(Document):
    meta = {
        'collection': 'teachers',
        'indexes': [
            {'fields': ['username'], 'unique': True, 'sparse': True},
            {'fields': ['created_at']}
        ]
    }
    username = StringField(required=True, unique=True)
    password_hash = StringField(required=True)
    active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)

    def set_password(self, password: str):
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

class Student(Document):
    meta = {
        'collection': 'students',
        'indexes': [
            {'fields': ['roll_number'], 'unique': True, 'sparse': True},
            {'fields': ['created_at']}
        ]
    }
    name = StringField(required=True)
    roll_number = StringField(required=True, unique=True)
    password_hash = StringField(required=True)
    active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)

    def set_password(self, password: str):
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

class Lecture(Document):
    meta = {
        'collection': 'lectures',
        'indexes': [
            {'fields': ['teacher', 'date']},
            {'fields': ['created_at']},
            {'fields': ['qr_expiry']}
        ]
    }
    teacher = ReferenceField('Teacher', required=True)  # Ensure this is a ReferenceField
    subject = StringField(required=True)
    date = DateTimeField(required=True)
    start_time = StringField(required=True)
    end_time = StringField(required=True)
    qr_code = StringField()
    qr_expiry = DateTimeField()
    active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)

    def clean(self):
        # Validate time format
        try:
            datetime.strptime(self.start_time, '%H:%M:%S')
            datetime.strptime(self.end_time, '%H:%M:%S')
        except ValueError:
            raise ValueError("Time must be in HH:MM:SS format")

        # Validate end time is after start time
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")

    def save(self, *args, **kwargs):
        if not self.qr_expiry:
            self.qr_expiry = datetime.utcnow() + timedelta(minutes=5)
        self.clean()
        super(Lecture, self).save(*args, **kwargs)

    def is_qr_valid(self) -> bool:
        return datetime.utcnow() <= self.qr_expiry
class Attendance(Document):
    meta = {
        'collection': 'attendance',
        'indexes': [
            {'fields': ['lecture', 'student'], 'unique': True},
            {'fields': ['scan_time']},
            {'fields': ['created_at']}
        ]
    }
    lecture = ReferenceField('Lecture', required=True)
    student = ReferenceField('Student', required=True)
    scan_time = DateTimeField(required=True)
    status = StringField(default="present", choices=['present', 'absent'])
    location = StringField()
    device_info = StringField()
    created_at = DateTimeField(default=datetime.utcnow)

    def clean(self):
        if not self.is_valid_attendance():
            raise ValueError("Attendance can only be marked during lecture hours")

    def is_valid_attendance(self) -> bool:
        lecture = self.lecture
        attendance_date = self.scan_time.date()
        lecture_date = lecture.date.date()
        
        if attendance_date != lecture_date:
            return False
            
        current_time = self.scan_time.strftime('%H:%M:%S')
        return lecture.start_time <= current_time <= lecture.end_time

    def save(self, *args, **kwargs):
        self.clean()
        super(Attendance, self).save(*args, **kwargs)