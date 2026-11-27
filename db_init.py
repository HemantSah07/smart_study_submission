import pymysql
import os
from dotenv import load_dotenv
from app import create_app, db
from app.models import *

def init_db():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
