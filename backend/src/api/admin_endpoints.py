from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import shutil
import tempfile
from pathlib import Path

from .dependencies import verify_admin_secret

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_secret)],
)

# Путь к Volume в Railway
VOLUME_PATH = "/app/data"
DATABASE_FILE = "experts.db"

@router.post("/upload-database")
async def upload_database(file: UploadFile = File(...)):
    """
    Загружает SQLite базу данных на Railway Volume

    Эндпоинт для одноразовой загрузки БД при деплое
    """
    try:
        # Проверяем что файл имеет правильное расширение
        if not file.filename.endswith('.db'):
            raise HTTPException(status_code=400, detail="Only .db files are allowed")

        # Убеждаемся что директория data существует
        os.makedirs(VOLUME_PATH, exist_ok=True)

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
            # Читаем и записываем файл
            shutil.copyfileobj(file.file, temp_file)
            temp_file.flush()

            # Проверяем что это валидная SQLite база
            import sqlite3
            try:
                conn = sqlite3.connect(temp_file.name)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                conn.close()

                if not tables:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid SQLite database: no tables found"
                    )

            except sqlite3.Error as e:
                os.unlink(temp_file.name)
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid SQLite database: {str(e)}"
                )

        # Копируем в Volume
        volume_db_path = os.path.join(VOLUME_PATH, DATABASE_FILE)
        shutil.copy2(temp_file.name, volume_db_path)

        # Удаляем временный файл
        os.unlink(temp_file.name)

        # Проверяем размер файла
        file_size = os.path.getsize(volume_db_path)

        return JSONResponse(content={
            "success": True,
            "message": "Database uploaded successfully to Railway Volume",
            "details": {
                "filename": file.filename,
                "size_bytes": file_size,
                "volume_path": volume_db_path,
                "tables_found": len(tables)
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/volume-status")
async def check_volume_status():
    """
    Проверяет статус Volume и базы данных
    """
    try:
        volume_exists = os.path.exists(VOLUME_PATH)
        db_path = os.path.join(VOLUME_PATH, DATABASE_FILE)
        db_exists = os.path.exists(db_path)

        details = {
            "volume_path": VOLUME_PATH,
            "volume_exists": volume_exists,
            "database_path": db_path,
            "database_exists": db_exists
        }

        if db_exists:
            # Проверяем базу данных
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Получаем информацию о таблицах
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
            table_count = cursor.fetchone()[0]

            # Получаем размер файла
            file_size = os.path.getsize(db_path)

            # Получаем количество записей в основных таблицах
            tables_info = {}
            for table in ['posts', 'comments', 'links', 'comment_group_drift']:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE 1;")
                try:
                    count = cursor.fetchone()[0]
                    tables_info[table] = count
                except sqlite3.OperationalError:
                    tables_info[table] = 0

            conn.close()

            details.update({
                "database_size_bytes": file_size,
                "table_count": table_count,
                "tables_info": tables_info
            })

        return JSONResponse(content={
            "success": True,
            "details": details
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")
