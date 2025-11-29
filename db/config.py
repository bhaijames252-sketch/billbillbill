import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from pymongo import MongoClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "billingcloud")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "mysql123@james")
MYSQL_DB = os.getenv("MYSQL_DB", "billingcloud")

MYSQL_URI = f"mysql+pymysql://{MYSQL_USER}:{quote_plus(MYSQL_PASSWORD)}@{MYSQL_HOST}/{MYSQL_DB}"


def get_mongo_client():
    return MongoClient(MONGO_URI)


def get_mongo_db():
    client = get_mongo_client()
    return client[MONGO_DB_NAME]


engine = create_engine(MYSQL_URI, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_mysql_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
