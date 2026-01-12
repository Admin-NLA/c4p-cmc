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

def upload_file(local_path, folder):
    if not local_path or not os.path.exists(local_path):
        return None

    result = cloudinary.uploader.upload(
        local_path,
        folder=folder,
        resource_type="auto",
        use_filename=True,
        unique_filename=True,
        overwrite=False
    )
    return result.get("secure_url")

# =========================
# MIGRAR CVs Y FOTOS
# =========================

def migrate_profiles():
    print("🔁 Migrando CVs y fotos...")

    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT id, cv_file, photo_file
            FROM profile
            WHERE
                (cv_file IS NOT NULL AND cv_file != '')
                OR (photo_file IS NOT NULL AND photo_file != '')
        """)).fetchall()

        for row in rows:
            profile_id = row.id

            # ---- CV ----
            if row.cv_file and row.cv_file.startswith("uploads/"):
                cv_path = os.path.join(BASE_DIR, row.cv_file)
                cv_url = upload_file(cv_path, "c4p/migration/cv")

                if cv_url:
                    conn.execute(
                        text("UPDATE profile SET cv_file = :url WHERE id = :id"),
                        {"url": cv_url, "id": profile_id}
                    )
                    print(f"✅ CV migrado (profile {profile_id})")

            # ---- FOTO ----
            if row.photo_file and row.photo_file.startswith("uploads/"):
                photo_path = os.path.join(BASE_DIR, row.photo_file)
                photo_url = upload_file(photo_path, "c4p/migration/photos")

                if photo_url:
                    conn.execute(
                        text("UPDATE profile SET photo_file = :url WHERE id = :id"),
                        {"url": photo_url, "id": profile_id}
                    )
                    print(f"✅ Foto migrada (profile {profile_id})")

# =========================
# MIGRAR PROPUESTAS
# =========================

def migrate_proposals():
    print("🔁 Migrando propuestas...")

    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT id, supporting_doc_url
            FROM proposals
            WHERE supporting_doc_url LIKE 'uploads/%'
        """)).fetchall()

        for row in rows:
            proposal_id = row.id
            doc_path = os.path.join(BASE_DIR, row.supporting_doc_url)

            cloud_url = upload_file(doc_path, "c4p/migration/proposals")

            if cloud_url:
                conn.execute(
                    text("""
                        UPDATE proposals
                        SET supporting_doc_url = :url
                        WHERE id = :id
                    """),
                    {"url": cloud_url, "id": proposal_id}
                )
                print(f"✅ Propuesta migrada (id {proposal_id})")

# =========================
# RUN
# =========================

if __name__ == "__main__":
    migrate_profiles()
    migrate_proposals()
    print("🎉 Migración finalizada correctamente")