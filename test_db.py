import pymysql
from dotenv import load_dotenv
import os

load_dotenv()
pwd = os.getenv('DB_PASSWORD')
print(f"Testing password: {pwd}")
try:
    conn = pymysql.connect(host='localhost', user='root', password=pwd)
    print("SUCCESS!")
except Exception as e:
    print(f"FAILED: {e}")
