from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import func, Boolean, text
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import JSON

db = SQLAlchemy()

# Association tables for many-to-many relationships
movie_genres = db.Table(
    'movie_genres', db.Model.metadata,
    db.Column('movie_id',  db.Integer, db.ForeignKey('movies.movie_id'),  primary_key=True),
    db.Column('genre_id',  db.Integer, db.ForeignKey('genres.genre_id'),  primary_key=True),
)

movie_studios = db.Table(
    'movie_studios', db.Model.metadata,
    db.Column('movie_id',  db.Integer, db.ForeignKey('movies.movie_id'),  primary_key=True),
    db.Column('studio_id', db.Integer, db.ForeignKey('studios.studio_id'), primary_key=True),
)

movie_producers = db.Table(
    'movie_producers', db.Model.metadata,
    db.Column('movie_id', db.Integer, db.ForeignKey('movies.movie_id'),  primary_key=True),
    db.Column('producer_id', db.Integer, db.ForeignKey('producers.producer_id'), primary_key=True),
)

movie_cast = db.Table(
    'movie_cast', db.Model.metadata,
    db.Column('movie_id', db.Integer, db.ForeignKey('movies.movie_id'),  primary_key=True),
    db.Column('cast_id', db.Integer, db.ForeignKey('cast_members.cast_id'), primary_key=True),
)

class User(UserMixin, db.Model):
    """
    Represents an app user.
    - email/password for auth
    - is_admin flag
    - active flag for disabling accounts
    - favorites & ratings relationships
    """
    __tablename__ = 'users'
    user_id    = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.Text, nullable=False)
    is_admin   = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    
    active     = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=text('TRUE')
    )

    # Relationships
    favorites = db.relationship('Movie', secondary='favorites', back_populates='favorited_by')
    ratings   = db.relationship('Rating', back_populates='user')
    
    def get_id(self):
        return str(self.user_id)
    
    @property
    def is_active(self):
        # Override to use our 'active' column
        return self.active
    
    def set_password(self, pw):
        # Hash and store the password
        self.password = generate_password_hash(pw)

    def check_password(self, pw):
        # Verify a plaintext password
        return check_password_hash(self.password, pw)

class Movie(db.Model):
    """
    Represents a movie entry.
    - Stores metadata and an embedding vector as JSON text
    - Links to Year and Director (one-to-many)
    - Many-to-many with Genre, Studio, Producer, CastMember
    """
    __tablename__ = 'movies'
    movie_id     = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.Text, nullable=False)
    description  = db.Column(db.Text)
    avg_rating   = db.Column(db.Float)
    duration     = db.Column(db.Integer)
    poster_url   = db.Column(db.Text)
    page_url     = db.Column(db.Text)
    year_id      = db.Column(db.Integer, db.ForeignKey('years.year_id'))
    director_id  = db.Column(db.Integer, db.ForeignKey('directors.director_id'))
    embeddings   = db.Column(db.Text)
    
    # Relationships
    year           = relationship('Year', back_populates='movies')
    genres         = relationship('Genre', secondary=movie_genres, back_populates='movies')
    studios        = relationship('Studio', secondary=movie_studios, back_populates='movies')
    producers      = relationship('Producer', secondary=movie_producers, back_populates='movies')
    cast_members   = relationship('CastMember', secondary=movie_cast, back_populates='movies')
    director       = relationship('Director')

    favorited_by = db.relationship('User', secondary='favorites', back_populates='favorites')
    ratings      = db.relationship('Rating', back_populates='movie')

class Favorite(db.Model):
    # Junction table for User–Movie favorites.
    __tablename__ = 'favorites'
    user_id   = db.Column(db.Integer, db.ForeignKey('users.user_id'), primary_key=True)
    movie_id  = db.Column(db.Integer, db.ForeignKey('movies.movie_id'), primary_key=True)
    added_at  = db.Column(db.DateTime, server_default=func.now())

class Rating(db.Model):
    # Junction table for User–Movie model ratings.
    __tablename__ = 'ratings'
    user_id  = db.Column(db.Integer, db.ForeignKey('users.user_id'), primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.movie_id'), primary_key=True)
    rating   = db.Column(db.SmallInteger, nullable=False)
    rated_at = db.Column(db.DateTime, server_default=func.now())

    user    = db.relationship('User', back_populates='ratings')
    movie   = db.relationship('Movie', back_populates='ratings')

class Year(db.Model):
    # Year lookup table.
    __tablename__  = 'years'
    year_id        = db.Column(db.Integer, primary_key=True)
    year_value     = db.Column(db.Integer, nullable=False)
    movies         = relationship('Movie', back_populates='year')

class Genre(db.Model):
    # Genre lookup table.
    __tablename__  = 'genres'
    genre_id       = db.Column(db.Integer, primary_key=True)
    genre_name     = db.Column(db.String, unique=True, nullable=False)
    movies         = relationship('Movie', secondary='movie_genres', back_populates='genres')
    
class Studio(db.Model):
    # Studio lookup table.
    __tablename__ = 'studios'
    studio_id   = db.Column(db.Integer, primary_key=True)
    studio_name = db.Column(db.String, unique=True, nullable=False)
    movies      = relationship('Movie', secondary='movie_studios', back_populates='studios')

class Director(db.Model):
    # Director lookup table.
    __tablename__     = 'directors'
    director_id       = db.Column(db.Integer, primary_key=True)
    director_name     = db.Column(db.String, unique=True, nullable=False)
    movies            = relationship('Movie', back_populates='director')

class Producer(db.Model):
    # Producer lookup table.
    __tablename__    = 'producers'
    producer_id     = db.Column(db.Integer, primary_key=True)
    producer_name   = db.Column(db.String, unique=True, nullable=False)
    movies          = relationship('Movie', secondary='movie_producers', back_populates='producers')

class CastMember(db.Model):
    # Cast member lookup table.
    __tablename__    = 'cast_members'
    cast_id         = db.Column(db.Integer, primary_key=True)
    cast_name       = db.Column(db.String, unique=True, nullable=False)
    movies          = relationship('Movie', secondary='movie_cast', back_populates='cast_members')
    
class ActivityLog(db.Model):
    # Records user actions for analytics and auditing.
    __tablename__ = 'activity_log'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    action     = db.Column(db.String(50),    nullable=False)
    detail     = db.Column(JSON, nullable=True)
    created_at = db.Column(db.DateTime,      nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('activity_logs', lazy='dynamic'))
