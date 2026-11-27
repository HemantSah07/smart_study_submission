import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    debug_flag = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(debug=debug_flag, port=5000)