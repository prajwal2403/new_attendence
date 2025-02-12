from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from jose import JWTError, jwt
import qrcode
import cv2
from io import BytesIO
from database import init_db
from models import Teacher, Student, Lecture, Attendance
from schemas import TeacherCreate, StudentCreate, LectureCreate, AttendanceMark, QRCodeGenerate
from collections import defaultdict
from typing import List
import time
from functools import wraps
from bson import ObjectId

# Initialize database
init_db()

# Configuration
SECRET_KEY = "your_secret_key"  # Keep this secure and use environment variables in production
ALGORITHM = "HS256"  # Algorithm for JWT

# FastAPI App
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory rate limiting
rate_limit_data = defaultdict(list)

def rate_limiter(max_requests: int, time_window: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            client_ip = "global"  # You can extract real IP from request if needed
            current_time = time.time()
            
            # Get the requests for this client
            requests = rate_limit_data[client_ip]
            
            # Remove expired requests
            requests = [req for req in requests if current_time - req <= time_window]
            rate_limit_data[client_ip] = requests
            
            if len(requests) >= max_requests:
                raise HTTPException(status_code=429, detail="Too many requests")
            
            rate_limit_data[client_ip].append(current_time)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_token(user_id: str, role: str) -> str:
    payload = {"user_id": user_id, "role": role, "exp": datetime.utcnow() + timedelta(minutes=30)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# Endpoints
@app.post("/register/teacher")
@rate_limiter(max_requests=5, time_window=60)
async def register_teacher(teacher: TeacherCreate):
    if Teacher.objects(username=teacher.username).first():
        raise HTTPException(status_code=400, detail="Teacher already exists")
    new_teacher = Teacher(username=teacher.username)
    new_teacher.set_password(teacher.password)
    new_teacher.save()
    return {"message": "Teacher registered successfully"}

@app.post("/register/student")
@rate_limiter(max_requests=5, time_window=60)
async def register_student(student: StudentCreate):
    if Student.objects(roll_number=student.roll_number).first():
        raise HTTPException(status_code=400, detail="Student already exists")
    new_student = Student(name=student.name, roll_number=student.roll_number)
    new_student.set_password(student.password)
    new_student.save()
    return {"message": "Student registered successfully"}

@app.post("/login/teacher")
@rate_limiter(max_requests=5, time_window=60)
async def login_teacher(form_data: OAuth2PasswordRequestForm = Depends()):
    teacher = Teacher.objects(username=form_data.username).first()
    if not teacher or not teacher.check_password(form_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_token(str(teacher.id), "teacher"), "token_type": "bearer"}

@app.post("/login/student")
@rate_limiter(max_requests=5, time_window=60)
async def login_student(form_data: OAuth2PasswordRequestForm = Depends()):
    student = Student.objects(roll_number=form_data.username).first()
    if not student or not student.check_password(form_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_token(str(student.id), "student"), "token_type": "bearer"}

@app.post("/lecture/create")
@rate_limiter(max_requests=5, time_window=60)
async def create_lecture(lecture: LectureCreate, token: str = Depends(oauth2_scheme)):
    # Decode the token to get the teacher_id
    payload = decode_token(token)
    teacher_id = payload["user_id"]

    # Query the teacher
    teacher = Teacher.objects(id=teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    # Create the lecture
    new_lecture = Lecture(
        teacher=teacher,
        subject=lecture.subject,
        date=lecture.date,
        start_time=lecture.start_time,
        end_time=lecture.end_time
    )
    new_lecture.save()

    return {"message": "Lecture created successfully", "lecture_id": str(new_lecture.id)}

@app.post("/qr/generate")
@rate_limiter(max_requests=5, time_window=60)
async def generate_qr(qr_data: QRCodeGenerate, token: str = Depends(oauth2_scheme)):
    try:
        lecture_id = ObjectId(qr_data.lecture_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid lecture_id")

    lecture = Lecture.objects(id=lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")

    qr_img = qrcode.make(f"lecture_id:{qr_data.lecture_id}")
    qr_path = f"static/qrcodes/{qr_data.lecture_id}.png"
    qr_img.save(qr_path)

    return {"qr_code": qr_path}

@app.post("/qr/scan")
@rate_limiter(max_requests=5, time_window=60)
async def scan_qr(file: UploadFile = File(...)):
    try:
        image_path = f"static/qrcodes/{file.filename}"
        with open(image_path, "wb") as f:
            f.write(file.file.read())
        img = cv2.imread(image_path)
        decoded_objects = decode(img)
        if not decoded_objects:
            raise HTTPException(status_code=400, detail="Invalid QR code")
        qr_data = decoded_objects[0].data.decode()
        lecture_id = qr_data.split(":")[1]
        return {"lecture_id": lecture_id}
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/attendance/mark")
@rate_limiter(max_requests=5, time_window=60)
async def mark_attendance(attendance: AttendanceMark, token: str = Depends(oauth2_scheme)):
    try:
        lecture_id = ObjectId(attendance.lecture_id)
        student_id = ObjectId(attendance.student_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid lecture_id or student_id")

    lecture = Lecture.objects(id=lecture_id).first()
    student = Student.objects(id=student_id).first()

    if not lecture or not student:
        raise HTTPException(status_code=404, detail="Lecture or student not found")

    if Attendance.objects(lecture=lecture, student=student).first():
        raise HTTPException(status_code=400, detail="Attendance already marked")

    attendance_record = Attendance(
        lecture=lecture,
        student=student,
        scan_time=datetime.utcnow(),
        status="present"
    )
    attendance_record.save()

    await manager.broadcast(f"Attendance marked for student {student.name} in lecture {lecture.subject}")
    return {"message": "Attendance marked successfully"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
async def home():
    return {"message": "QR Attendance System with FastAPI"}