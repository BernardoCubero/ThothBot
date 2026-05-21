import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


load_dotenv()

DB_USER = os.getenv("MARIADB_USER")
DB_PASS = os.getenv("MARIADB_PASSWORD")
DB_HOST = os.getenv("MARIADB_HOST")
DB_PORT = os.getenv("MARIADB_PORT")
DB_NAME = os.getenv("MARIADB_DB")


engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
