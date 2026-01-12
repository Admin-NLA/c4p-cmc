from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///c4p_cmc.db")

with engine.begin() as conn:
    print("🧹 Limpiando valores legacy...")

    conn.execute(text("""
        UPDATE profile
        SET cv_url = NULL
        WHERE cv_url LIKE '/uploads/%'
    """))

    conn.execute(text("""
        UPDATE proposal
        SET supporting_doc_url = NULL
        WHERE supporting_doc_url LIKE '/uploads/%'
    """))

    print("✅ Limpieza completada")