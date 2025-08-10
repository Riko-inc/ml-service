# chat_app/core_app/database/session.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv

load_dotenv()

def get_database_url():
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "mydatabase")
    db_user = os.getenv("DB_USER", "myuser")
    db_pass = os.getenv("DB_PASSWORD", "secret")

    return f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

engine = create_engine(get_database_url())

Base = declarative_base()

Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()