from app import create_app, db
import app.models  # Register all models on db metadata

def init_database():
    app = create_app()
    with app.app_context():
        db.create_all()
        print(f"All tables created successfully ({app.config['SQLALCHEMY_DATABASE_URI']}).")

if __name__ == '__main__':
    init_database()
