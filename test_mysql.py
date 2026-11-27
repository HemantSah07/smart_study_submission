import pymysql

passwords = ["", "root", "root1234", "password", "123456", "admin", "12345678", "SmartStudy@APU2025#NP069826"]
for pwd in passwords:
    try:
        conn = pymysql.connect(host='localhost', user='root', password=pwd)
        print(f"SUCCESS with password: '{pwd}'")
        break
    except Exception as e:
        print(f"FAILED '{pwd}': {e}")
