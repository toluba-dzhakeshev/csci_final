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
#TESTING RECOMMENDATION USING FAISS
import numpy as np
import faiss
faiss.omp_set_num_threads(1) 
from files.models import Movie
import json

# Protect against CSRF attacks on form submissions
csrf = CSRFProtect()

# Simple in-memory cache for improving performance
cache = Cache(config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# Flask-Login manager setup
login_manager = LoginManager()
login_manager.login_view = 'auth.login' # Redirect here if not authenticated

@login_manager.user_loader
def load_user(user_id):
    # Given a user ID, return the corresponding User object. Required by Flask-Login.
    return User.query.get(int(user_id))

def create_app(test_config: dict | None = None):
    # Application factory: sets up Flask app, configures extensions, and registers blueprints.
    app = Flask(__name__)
    
    # Initialize CSRF protection and caching
    csrf.init_app(app)
    cache.init_app(app)
    
    # Base configuration
    app.config.from_mapping(
        SECRET_KEY='ec1cdd0ea5f383a54dbc41dd6c4371a3b29fe1b9e2f5386a0dd6fb4c5490746a',        
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SERVER_NAME='localhost', # Required for url_for in tests
    )
    
    # Override configuration during testing if provided
    if test_config is not None:
        app.config.update(test_config)
    
    # Select database URI: in-memory for tests, otherwise PostgreSQL
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

    # Initialize database and login manager with the app
    db.init_app(app)
    login_manager.init_app(app)

    # Register application blueprints
    from files.auth import auth_bp
    from files.main import main_bp
    from files.admin import admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # ——— START FAISS SETUP ———
    with app.app_context():
        films = Movie.query.order_by(Movie.movie_id).all()
        embs_list = []
        for m in films:
            raw = m.embeddings
            try:
                vals = json.loads(raw)
            except json.JSONDecodeError:
                txt = raw.strip('[]').strip()
                vals = [float(x) for x in txt.split() if x]
            embs_list.append(vals)

        embs = np.array(embs_list, dtype='float32')
        faiss.normalize_L2(embs)
        # build an IVF index with 100 coarse clusters
        dim    = embs.shape[1]
        nlist  = 100
        quant = faiss.IndexFlatL2(dim)
        ivf   = faiss.IndexIVFFlat(quant, dim, nlist, faiss.METRIC_INNER_PRODUCT)
        ivf.train(embs)
        ivf.add(embs)

        app.faiss_index = ivf
        app.idx_to_id   = [m.movie_id for m in films]
        # build reverse lookup so we can go from movie_id → row in IVF
        app.id_to_idx   = {mid: i for i, mid in enumerate(app.idx_to_id)}
    # ———  END FAISS SETUP  ———

    return app

# Load the sentence-transformer model once for reuse
model = SentenceTransformer('all-MiniLM-L6-v2')

if __name__ == '__main__':
    # When run directly, create the app and start the dev server
    app = create_app()
    app.run(debug=True, port=5005)
    