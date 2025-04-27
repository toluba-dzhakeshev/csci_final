from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Movie
import json
from sentence_transformers import SentenceTransformer

admin_bp = Blueprint('admin', __name__, template_folder='templates/admin')
model    = SentenceTransformer('all-MiniLM-L6-v2')

def admin_required(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args,**kwargs)
    return wrapper

@admin_bp.route('/users')
@login_required
@admin_required
def list_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/movies')
@login_required
@admin_required
def list_movies():
    movies = Movie.query.all()
    return render_template('admin/movies.html', movies=movies)

@admin_bp.route('/movies/new', methods=['GET','POST'])
@login_required
@admin_required
def add_movie():
    if request.method=='POST':
        data = {k: request.form[k] for k in ['Title','Description','AvgRating','Duration','Poster','PageURL']}
        emb = model.encode(data['Description']).tolist()
        m = Movie(
            title=data['Title'], description=data['Description'], avg_rating=float(data['AvgRating']),
            duration=int(data['Duration']), poster_url=data['Poster'], page_url=data['PageURL'],
            embeddings=json.dumps(emb)
        )
        db.session.add(m); db.session.commit()
        flash('Movie added')
        return redirect(url_for('admin.list_movies'))
    return render_template('admin/movie_form.html')
