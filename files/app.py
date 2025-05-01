from flask import Flask
from files.models import db, User
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from sentence_transformers import SentenceTransformer
from flask_caching import Cache
from files.admin import admin_bp
import os
from dotenv import load_dotenv

csrf = CSRFProtect()

cache = Cache(config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

login_manager = LoginManager()
login_manager.login_view = 'auth.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app(test_config: dict | None = None):
    app = Flask(__name__)
    
    csrf.init_app(app)

    cache.init_app(app)
    
    app.config.from_mapping(
        SECRET_KEY='ec1cdd0ea5f383a54dbc41dd6c4371a3b29fe1b9e2f5386a0dd6fb4c5490746a',        
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SERVER_NAME='localhost', 
    )
    
    if test_config is not None:
        app.config.update(test_config)
    
    if app.config.get('TESTING'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    else:
        # app.config['SQLALCHEMY_DATABASE_URI'] = (
        #     'postgresql://tolubai:password@localhost:5432/movies_db'
        # )
        app.config['SQLALCHEMY_DATABASE_URI'] = (
            "postgresql://doadmin:AVNS_UnBm0Ppb2AFhY6g8nGI"
            "@db-postgresql-nyc3-03675-do-user-21639042-0.m.db.ondigitalocean.com"
            ":25060/movies_db"
            "?sslmode=require"
            "&sslrootcert=./do_ca.crt"
        )

    db.init_app(app)
    login_manager.init_app(app)

    from files.auth import auth_bp
    from files.main import main_bp
    from files.admin import admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app

model = SentenceTransformer('all-MiniLM-L6-v2')

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5005)
    