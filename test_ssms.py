import pyodbc
from dotenv import load_dotenv
import os

load_dotenv()
server = os.getenv('DB_SERVER', 'localhost')
print(f"Available drivers: {pyodbc.drivers()}")

# Find best driver
driver = 'SQL Server'
for d in pyodbc.drivers():
    if 'SQL Server' in d:
        driver = d
        if '17' in d or '18' in d:
            break

conn_str = f"DRIVER={{{driver}}};SERVER={server};Trusted_Connection=yes;"
print(f"Connecting with: {conn_str}")
try:
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()
    cursor.execute(f"IF NOT EXISTS (SELECT name FROM master.dbo.sysdatabases WHERE name = N'smart_study') CREATE DATABASE smart_study")
    print("Database ensured in SQL Server.")
    conn.close()
except Exception as e:
    print(f"Failed: {e}")
