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

# === File Upload Folder ===
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
                "date": datetime.now(JAKARTA).date(),
                "time": datetime.now(JAKARTA).time().replace(tzinfo=None),
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

        fd = save_file(foto_depan)
        fb = save_file(foto_belakang)
        fk = save_file(foto_kiri)
        fr = save_file(foto_kanan)
        ds = save_file(dokumen_seal)

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
                "date": datetime.now(JAKARTA).date(),
                "time": datetime.now(JAKARTA).time().replace(tzinfo=None),
                "ukuran_container_id": ukuran_container_id,
                "ekspor_impor_id": ekspor_impor_id,
                "status_id": status_id,
                "menunggu_surat_jalan": menunggu_surat_jalan if menunggu_surat_jalan else False,
                "fd": fd, "fb": fb, "fk": fk, "fr": fr, "ds": ds
            }
        )
        db.commit()
        return {"message": "Status + file created"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# === STATUS DRIVER: Latest ===
@app.get("/status-driver/latest")
def get_latest_status(driver_id: int):
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT sd.status_id, sp.status
                FROM status_driver sd
                JOIN status_perjalanan sp ON sd.status_id = sp.id
                WHERE sd.driver_id = :driver_id
                ORDER BY sd.date DESC, sd.time DESC
                LIMIT 1
            """),
            {"driver_id": driver_id}
        ).fetchone()
        return {"status_id": result[0] if result else None,
                "status_name": result[1] if result else None}
    finally:
        db.close()

# === STATUS DRIVER: History ===
@app.get("/status-driver/history")
def get_status_history(driver_id: int):
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                SELECT 
                    sd.date, 
                    p.nama_perusahaan, 
                    sp.status,
                    sd.location
                FROM status_driver sd
                JOIN perusahaan p ON sd.perusahaan_id = p.id
                JOIN status_perjalanan sp ON sd.status_id = sp.id
                WHERE sd.driver_id = :driver_id
                ORDER BY sd.date DESC, sd.time DESC
            """),
            {"driver_id": driver_id}
        ).fetchall()
        return [
            {
                "tanggal": getattr(row[0], "strftime", lambda fmt: row[0])("%Y-%m-%d"),
                "nama_perusahaan": row[1],
                "status": row[2],
                "location": row[3]
            }
            for row in result
        ]
    finally:
        db.close()

# === DROPDOWNS ===
@app.get("/ekspor-impor")
def get_ekspor_impor():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, tipe AS nama FROM ekspor_impor_type")).fetchall()
        return [{"id": r[0], "nama": r[1]} for r in rows]
    finally:
        db.close()

@app.get("/ukuran-container")
def get_ukuran():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, ukuran FROM ukuran_container")).fetchall()
        return [{"id": r[0], "ukuran": r[1]} for r in rows]
    finally:
        db.close()

@app.get("/perusahaan")
def get_perusahaan():
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT id, nama_perusahaan FROM perusahaan")).fetchall()
        return [{"id": r[0], "nama_perusahaan": r[1]} for r in rows]
    finally:
        db.close()

@app.get("/status")
def get_status(id: int = Query(...)):
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT sp.id, sp.status
            FROM status_mapping sm
            JOIN status_perjalanan sp ON sm.status_id = sp.id
            WHERE sm.ekspor_impor_id = :id
        """), {"id": id}).fetchall()
        return [{"id": r[0], "status": r[1]} for r in rows]
    finally:
        db.close()

# === DEBUG USERS ===
@app.get("/debug-users")
def debug_users():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT id, name, password FROM users")).fetchall()
        return [{"id": r[0], "name": r[1], "password": r[2]} for r in result]
    except Exception as e:
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
                "date": datetime.now(JAKARTA).date(),      
                "time": datetime.now(JAKARTA).time().replace(tzinfo=None),
                "menunggu_surat_jalan": menunggu_surat_jalan,
            }
        )
        db.commit()
        return {"message": "Status updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# === Run locally ===
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
