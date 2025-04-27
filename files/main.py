from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Movie, Favorite, Rating, Genre, Year, Studio, Director, Producer, CastMember
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import func
from app import model, cache

main_bp = Blueprint('main', __name__, template_folder='templates')

@cache.cached(timeout=300)                  # cache for 5 minutes
@main_bp.route('/', methods=['GET'])
def index():
    # only fetch the three small filter lists
    genres    = Genre.query.order_by(Genre.genre_name).all()
    studios   = Studio.query.order_by(Studio.studio_name).all()
    directors = Director.query.order_by(Director.director_name).all()

    # slider bounds
    min_year   = db.session.query(func.min(Year.year_value)).scalar() or 1900
    max_year   = db.session.query(func.max(Year.year_value)).scalar() or 2025
    min_rating = db.session.query(func.min(Movie.avg_rating)).scalar() or 0.0
    max_rating = db.session.query(func.max(Movie.avg_rating)).scalar() or 10.0

    return render_template('index.html',
        genres=genres,
        studios=studios,
        directors=directors,
        min_year=min_year,
        max_year=max_year,
        min_rating=min_rating,
        max_rating=max_rating
    )
    
@cache.cached(timeout=60, query_string=True)  # cache each search term for 1 minute
@main_bp.route('/producer_search')
@login_required
def producer_search():
    q = request.args.get('q','')
    choices = Producer.query.filter(Producer.producer_name.ilike(f'%{q}%')) \
                            .order_by(Producer.producer_name) \
                            .limit(20).all()
    return jsonify([{"id": p.producer_id, "text": p.producer_name} for p in choices])

@cache.cached(timeout=60, query_string=True)
@main_bp.route('/cast_search')
@login_required
def cast_search():
    q = request.args.get('q', '')
    matches = (CastMember.query
               .filter(CastMember.cast_name.ilike(f'%{q}%'))
               .order_by(CastMember.cast_name)
               .limit(20)
               .all())
    return jsonify([{"id": c.cast_id, "text": c.cast_name} for c in matches])

@main_bp.route('/favorites')
@login_required
def favorites():
    favs = current_user.favorites
    return render_template('favorites.html', movies=favs)

@main_bp.route('/favorite/<int:mid>', methods=['POST'])
@login_required
def toggle_fav(mid):
    fav = Favorite.query.get((current_user.user_id, mid))
    if fav:
        db.session.delete(fav)
        flash('Removed from favorites')
        now_fav = False
    else:
        db.session.add(Favorite(user_id=current_user.user_id, movie_id=mid))
        flash('Added to favorites')
        now_fav = True
    db.session.commit()

    # If this was called via fetch()/AJAX, send 204
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return ('', 204)

    # otherwise (normal form submit), redirect as before
    next_page = request.form.get('next') or request.referrer or url_for('main.index')
    return redirect(next_page)

@main_bp.route('/recommend', methods=['GET','POST'])
@login_required
def recommend():
    # 1) Handle the form submit
    if request.method == 'POST':
        params = {
            'description': request.form['description'],
            'genre':       request.form.get('genre',''),
            'studio':      request.form.get('studio',''),
            'director':    request.form.get('director',''),
            'producer':    request.form.get('producer',''),
            'cast_member': request.form.get('cast_member',''),
            'year_from':   request.form.get('year_from',''),
            'year_to':     request.form.get('year_to',''),
            'rating_from': request.form.get('rating_from',''),
            'rating_to':   request.form.get('rating_to',''),
            'offset':      0,
            'limit':       5
        }
        return redirect(url_for('main.recommend', **params))

    # 2) Build the full list on GET
    desc     = request.args.get('description','')
    genre    = request.args.get('genre') or None
    studio   = request.args.get('studio') or None
    director = request.args.get('director') or None
    producer = request.args.get('producer') or None
    cast     = request.args.get('cast_member') or None
    yf       = request.args.get('year_from') or None
    yt       = request.args.get('year_to') or None
    rf       = request.args.get('rating_from') or None
    rt       = request.args.get('rating_to') or None
    offset   = int(request.args.get('offset', 0))
    limit    = int(request.args.get('limit', 5))

    # 3) Filter + score + sort exactly as before…
    q = Movie.query
    if genre:    q = q.join(Movie.genres).filter(Genre.genre_id   == int(genre))
    if studio:   q = q.join(Movie.studios).filter(Studio.studio_id  == int(studio))
    if director: q = q.filter(Movie.director_id     == int(director))
    if producer: q = q.join(Movie.producers).filter(Producer.producer_id == int(producer))
    if cast:     q = q.join(Movie.cast_members).filter(CastMember.cast_id    == int(cast))
    if yf:       q = q.join(Movie.year).filter(Year.year_value       >= int(yf))
    if yt:       q = q.join(Movie.year).filter(Year.year_value       <= int(yt))
    if rf:       q = q.filter(Movie.avg_rating         >= float(rf))
    if rt:       q = q.filter(Movie.avg_rating         <= float(rt))
    candidates = q.all()

    emb_q   = model.encode(desc)
    results = []
    for m in candidates:
        if not Favorite.query.get((current_user.user_id, m.movie_id)):
            arr = np.fromstring(m.embeddings.strip('[]'), sep=' ')
            sim = (arr @ emb_q) / (np.linalg.norm(arr) * np.linalg.norm(emb_q))
            results.append((sim, m))
    results.sort(key=lambda x: x[0], reverse=True)

    # 4) Slice out just this page
    page     = results[offset:offset+limit]
    has_more = len(results) > offset + limit

    # 5) If it’s an AJAX “More” call, return JSON *inside* this block*
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        payload = [{
            'sim':         round(sim,2),
            'movie_id':    m.movie_id,
            'title':       m.title,
            'poster_url':  m.poster_url,
            'description': m.description,
            'year':        m.year.year_value,
            'genres':      [g.genre_name for g in m.genres],
            'studios':     [s.studio_name for s in m.studios],
            'director':    m.director.director_name,
            'producers':   [p.producer_name for p in m.producers],
            'cast':        [c.cast_name for c in m.cast_members],
            'duration':    m.duration,
            'page_url':    m.page_url,
            'faved':      Favorite.query.get((current_user.user_id, m.movie_id)) is not None,
            'avg_rating':  m.avg_rating,
        } for sim,m in page]
        return jsonify({
            'movies':      payload,
            'next_offset': offset + limit,
            'has_more':    has_more
        })

    # 6) Otherwise (initial page load), render the HTML template
    return render_template('results.html',
        recommendations=page,
        next_offset=offset + limit,
        has_more=has_more
    )

@main_bp.route('/results')
@login_required
def results():
    # parse args
    query     = request.args.get('query','')
    genre     = request.args.get('genre','')
    ymn, ymx  = request.args.get('year_from'), request.args.get('year_to')
    rmn, rmx  = request.args.get('rating_from'), request.args.get('rating_to')
    # 1) build base query
    q = Movie.query
    if genre:
        q = q.join(Movie.genres).filter(Genre.genre_name==genre)
    # 2) year filter
    if ymn: q = q.join(Movie.year).filter(Year.year_value>=int(ymn))
    if ymx: q = q.join(Movie.year).filter(Year.year_value<=int(ymx))
    # 3) rating filter
    if rmn: q = q.filter(Movie.avg_rating>=float(rmn))
    if rmx: q = q.filter(Movie.avg_rating<=float(rmx))
    # 4) similarity scoring
    q_emb = model.encode(query)
    scored = []
    for m in q.all():
        arr = np.fromstring(m.embeddings.strip('[]'), sep=' ')
        sim = np.dot(q_emb,arr)/(np.linalg.norm(q_emb)*np.linalg.norm(arr))
        # skip favorites
        if not Favorite.query.get((current_user.user_id,m.movie_id)):
            scored.append((sim,m))
    scored.sort(key=lambda x:-x[0])
    return render_template('results.html', results=scored)

@main_bp.route('/rate_model', methods=['POST'])
@login_required
def rate_model():
    movie_id = int(request.form['movie_id'])
    score    = int(request.form['model_rating'])

    # upsert into your existing ratings table
    rec = Rating.query.get((current_user.user_id, movie_id))
    if rec:
        rec.rating = score
    else:
        rec = Rating(
            user_id  = current_user.user_id,
            movie_id = movie_id,
            rating   = score
        )
        db.session.add(rec)

    db.session.commit()
    flash(f'You rated the model {score}/10 on "{Movie.query.get(movie_id).title}"')
    return redirect(request.referrer or url_for('main.recommend'))

