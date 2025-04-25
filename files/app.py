import os
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
import numpy as np

# ─── App & DB setup ───────────────────────────────────────────────────────────
app = Flask(__name__, template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URI',
    'postgresql://tolubai:password@localhost:5432/movies_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ─── Load your embedding model once ───────────────────────────────────────────
model = SentenceTransformer('all-MiniLM-L6-v2')

# ─── ORM Models & Relationships ──────────────────────────────────────────────
# Association table for Movie ↔ Genre
movie_genres = db.Table(
    'movie_genres', db.metadata,
    db.Column('movie_id', db.Integer, db.ForeignKey('movies.movie_id'), primary_key=True),
    db.Column('genre_id', db.Integer, db.ForeignKey('genres.genre_id'), primary_key=True),
)

class Movie(db.Model):
    __tablename__ = 'movies'
    movie_id    = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String)
    description = db.Column(db.Text)
    avg_rating  = db.Column(db.Numeric)
    duration    = db.Column(db.Integer)
    poster_url  = db.Column(db.Text)
    page_url    = db.Column(db.Text)
    year_id     = db.Column(db.Integer, db.ForeignKey('years.year_id'))
    director_id = db.Column(db.Integer, db.ForeignKey('directors.director_id'))
    embeddings  = db.Column(db.Text)

    # link to genres
    genres = db.relationship(
        'Genre',
        secondary=movie_genres,
        backref='movies'
    )

class Genre(db.Model):
    __tablename__ = 'genres'
    genre_id   = db.Column(db.Integer, primary_key=True)
    genre_name = db.Column(db.String, unique=True)

# (You can add similar association tables & models for studios, producers, cast, etc.)

# ─── Homepage: render search form ─────────────────────────────────────────────
@app.route('/', methods=['GET'])
def index():
    # raw execute → list of Row objects, each like (genre_name,)
    genre_rows = db.session.execute(text("SELECT genre_name FROM genres")).all()
    genres     = [row[0] for row in genre_rows]

    year_rows  = db.session.execute(text("SELECT year_value FROM years")).all()
    years      = [row[0] for row in year_rows]

    ratings = [5,6,7,8,9,10]
    return render_template('index.html', genres=genres, years=years, ratings=ratings)

# ─── Recommendations endpoint ─────────────────────────────────────────────────
@app.route('/recommend', methods=['POST'])
def recommend():
    desc   = request.form.get('description', '').strip()
    genre  = request.form.get('genre')
    year   = request.form.get('year',    type=int)
    rating = request.form.get('rating',  type=float)

    # 1) Metadata filtering in SQL
    q = Movie.query
    if genre:
        q = q.filter(Movie.genres.any(Genre.genre_name == genre))
    if year:
        q = q.filter(Movie.year_id == year)
    if rating:
        q = q.filter(Movie.avg_rating >= rating)

    # 2) Fetch candidates with their embeddings
    candidates = q.with_entities(
        Movie.movie_id,
        Movie.title,
        Movie.embeddings,
        Movie.poster_url,
        Movie.avg_rating
    ).all()

    # 3) Encode user query
    query_emb = model.encode(desc, convert_to_numpy=True)

    # 4) Compute cosine similarities
    scored = []
    for mid, title, emb_text, poster, avg in candidates:
        # parse "[0.01 -0.02 ...]" → array
        arr = np.fromstring(emb_text.strip('[]'), sep=' ')
        sim = np.dot(query_emb, arr) / (np.linalg.norm(query_emb) * np.linalg.norm(arr))
        avg_val = float(avg) if avg is not None else None
        scored.append((sim, mid, title, poster, avg_val))

    # 5) Sort & pick top 10
    top10 = sorted(scored, key=lambda x: x[0], reverse=True)[:10]

    # 6) Prepare for template
    movies = [
        {
            'movie_id': mid,
            'title': title,
            'poster_url': poster,
            'avg_rating': avg,
            'score':  sim
        }
        for sim, mid, title, poster, avg in top10
    ]

    return render_template(
        'results.html',
        description=desc,
        filters={'genre':genre, 'year':year, 'rating':rating},
        movies=movies
    )

if __name__ == '__main__':
    app.run(debug=True, port=5002)
