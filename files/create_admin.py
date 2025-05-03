# Old file; Not in use now
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine, MetaData

DATABASE_URI = 'postgresql://tolubai:password@localhost:5432/movies_db'
engine = create_engine(DATABASE_URI)
metadata = MetaData()

admin_email = "admin@movieapp.com"
admin_pw    = "password"
admin_hash = generate_password_hash(admin_pw)

from sqlalchemy import text
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO users (email, password, is_admin)
        VALUES (:email, :pw, true)
        ON CONFLICT (email) DO NOTHING
    """), {"email": admin_email, "pw": admin_hash})

print("Default admin user seeded (email:", admin_email, ")")
