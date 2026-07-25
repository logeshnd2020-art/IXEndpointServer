from dotenv import load_dotenv
from sqlalchemy.engine import URL
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)

SECRET_KEY = os.getenv("SECRET_KEY")
API_VERSION = os.getenv("API_VERSION", "1.0.0")
