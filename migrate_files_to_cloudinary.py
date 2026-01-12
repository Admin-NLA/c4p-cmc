import os
import cloudinary
import cloudinary.uploader
from sqlalchemy import create_engine, text

# =========================
# CONFIG
# =========================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "c4p_cmc.db")

UPLOADS_BASE = os.path.join(BASE_DIR, "uploads")

engine = create_engine(f"sqlite:///{DB_PATH}")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# =========================
# HELPERS
# =========================

def upload_file(path, folder):
    if not os.path.exists(path):
        return None

    result = cloudinary.uploader.upload(
        path,
        folder=folder,
        resource_type="auto",
        use_filename=True,
        unique_filename=True,
        overwrite=False
    )
    return result.get("secure_url")

# =========================
# MIGRAR CVs
# =========================

def migrate_cvs():
    print("🔁 Migrando CVs...")
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, cv_url FROM profile WHERE cv_url LIKE '/uploads/%'")
        ).fetchall()

        for row in rows:
            local_path = os.path.join(BASE_DIR, row.cv_url.lstrip("/"))
            cloud_url = upload_file(local_path, "c4p/migration/cv")

            if cloud_url:
                conn.execute(
                    text("UPDATE profile SET cv_url = :url WHERE id = :id"),
                    {"url": cloud_url, "id": row.id}
                )
                print(f"✅ CV migrado (profile {row.id})")

# =========================
# MIGRAR PROPUESTAS
# =========================

def migrate_proposals():
    print("🔁 Migrando propuestas...")
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT id, supporting_doc_url
                FROM proposal
                WHERE supporting_doc_url LIKE '/uploads/%'
            """)
        ).fetchall()

        for row in rows:
            local_path = os.path.join(BASE_DIR, row.supporting_doc_url.lstrip("/"))
            cloud_url = upload_file(local_path, "c4p/migration/proposals")

            if cloud_url:
                conn.execute(
                    text("""
                        UPDATE proposal
                        SET supporting_doc_url = :url
                        WHERE id = :id
                    """),
                    {"url": cloud_url, "id": row.id}
                )
                print(f"✅ Propuesta migrada (id {row.id})")

# =========================
# RUN
# =========================

if __name__ == "__main__":
    migrate_cvs()
    migrate_proposals()
    print("🎉 Migración finalizada")