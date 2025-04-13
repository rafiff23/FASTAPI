from fastapi import FastAPI, HTTPException, Query, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
from datetime import datetime
import os
import shutil
from typing import Optional
import pytz

# === Load Environment ===
load_dotenv()
DB_URL = os.getenv("DB_URL")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

# === Timezone Jakarta ===
JAKARTA = pytz.timezone("Asia/Jakarta")

# === FastAPI App ===
app = FastAPI()

# === CORS Middleware ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# === LOGIN ===
@app.post("/login")
def login(data: dict):
    db = SessionLocal()
    try:
        name = data.get("name")
        password = data.get("password")
        user = db.execute(
            text("SELECT id FROM users WHERE name = :name AND password = :password"),
            {"name": name, "password": password}
        ).fetchone()
        if user:
            return {"driver_id": user[0]}
        raise HTTPException(status_code=401, detail="Login gagal: Nama atau password salah")
    finally:
        db.close()

# === TRACKING ===
class TrackingData(BaseModel):
    driver_id: int
    latitude: float
    longitude: float

@app.post("/track")
def track(data: TrackingData):
    db = SessionLocal()
    try:
        db.execute(
            text("""
                INSERT INTO tracking_log (driver_id, latitude, longitude, timestamp)
                VALUES (:driver_id, :latitude, :longitude, :timestamp)
            """),
            {
                "driver_id": data.driver_id,
                "latitude": data.latitude,
                "longitude": data.longitude,
                "timestamp": datetime.now(JAKARTA)
            }
        )
        db.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# === STATUS DRIVER: Create ===
class StatusDriverData(BaseModel):
    driver_id: int
    perusahaan_id: int
    location: str
    ukuran_container_id: int
    ekspor_impor_id: int
    status_id: int
    menunggu_surat_jalan: bool

@app.post("/status-driver")
def create_status_driver(data: StatusDriverData):
    db = SessionLocal()
    try:
        now = datetime.now(JAKARTA)
        db.execute(
            text("""
                INSERT INTO status_driver (
                    driver_id, perusahaan_id, location, date, time,
                    ukuran_container_id, ekspor_impor_id,
                    status_id, status_color_id, menunggu_surat_jalan
                ) VALUES (
                    :driver_id, :perusahaan_id, :location, :date, :time,
                    :ukuran_container_id, :ekspor_impor_id,
                    :status_id,
                    (SELECT status_color_id FROM status_mapping WHERE ekspor_impor_id = :ekspor_impor_id AND status_id = :status_id),
                    :menunggu_surat_jalan
                )
            """),
            {
                "driver_id": data.driver_id,
                "perusahaan_id": data.perusahaan_id,
                "location": data.location,
                "date": now.date(),
                "time": now.time().replace(tzinfo=None),
                "ukuran_container_id": data.ukuran_container_id,
                "ekspor_impor_id": data.ekspor_impor_id,
                "status_id": data.status_id,
                "menunggu_surat_jalan": data.menunggu_surat_jalan
            }
        )
        db.commit()
        return {"message": "Status created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# === STATUS DRIVER: Upload with Files ===
@app.post("/status-driver-upload")
async def create_status_driver_upload(
    driver_id: int = Form(...),
    perusahaan_id: int = Form(...),
    location: str = Form(...),
    ukuran_container_id: int = Form(...),
    ekspor_impor_id: int = Form(...),
    status_id: int = Form(...),
    menunggu_surat_jalan: Optional[bool] = Form(None),
    foto_depan: UploadFile = File(None),
    foto_belakang: UploadFile = File(None),
    foto_kiri: UploadFile = File(None),
    foto_kanan: UploadFile = File(None),
    dokumen_seal: UploadFile = File(None),
):
    db = SessionLocal()
    try:
        def save_file(file: UploadFile):
            if file:
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                return file.filename
            return None

        now = datetime.now(JAKARTA)

        db.execute(
            text("""
                INSERT INTO status_driver (
                    driver_id, perusahaan_id, location, date, time,
                    ukuran_container_id, ekspor_impor_id,
                    status_id, status_color_id, menunggu_surat_jalan,
                    foto_depan, foto_belakang, foto_kiri, foto_kanan, dokumen_seal
                ) VALUES (
                    :driver_id, :perusahaan_id, :location, :date, :time,
                    :ukuran_container_id, :ekspor_impor_id,
                    :status_id,
                    (SELECT status_color_id FROM status_mapping WHERE ekspor_impor_id = :ekspor_impor_id AND status_id = :status_id),
                    :menunggu_surat_jalan,
                    :fd, :fb, :fk, :fr, :ds
                )
            """),
            {
                "driver_id": driver_id,
                "perusahaan_id": perusahaan_id,
                "location": location,
                "date": now.date(),
                "time": now.time().replace(tzinfo=None),
                "ukuran_container_id": ukuran_container_id,
                "ekspor_impor_id": ekspor_impor_id,
                "status_id": status_id,
                "menunggu_surat_jalan": menunggu_surat_jalan if menunggu_surat_jalan else False,
                "fd": save_file(foto_depan),
                "fb": save_file(foto_belakang),
                "fk": save_file(foto_kiri),
                "fr": save_file(foto_kanan),
                "ds": save_file(dokumen_seal)
            }
        )
        db.commit()
        return {"message": "Status + file created"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# === UPDATE STATUS ===
@app.post("/status-driver-update")
def update_status_driver(
    driver_id: int = Form(...),
    status_id: int = Form(...),
    menunggu_surat_jalan: bool = Form(...),
    location: str = Form(...),
):
    db = SessionLocal()
    try:
        now = datetime.now(JAKARTA)
        db.execute(
            text("""
                INSERT INTO status_driver (
                    driver_id, perusahaan_id, location, date, time,
                    ukuran_container_id, ekspor_impor_id,
                    status_id, status_color_id, menunggu_surat_jalan
                )
                SELECT
                    sd.driver_id, sd.perusahaan_id, :location, :date, :time,
                    sd.ukuran_container_id, sd.ekspor_impor_id,
                    :status_id,
                    (SELECT status_color_id FROM status_mapping WHERE ekspor_impor_id = sd.ekspor_impor_id AND status_id = :status_id),
                    :menunggu_surat_jalan
                FROM status_driver sd
                WHERE sd.driver_id = :driver_id
                ORDER BY date DESC, time DESC
                LIMIT 1
            """),
            {
                "driver_id": driver_id,
                "status_id": status_id,
                "location": location,
                "date": now.date(),
                "time": now.time().replace(tzinfo=None),
                "menunggu_surat_jalan": menunggu_surat_jalan,
            }
        )
        db.commit()
        return {"message": "Status updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
