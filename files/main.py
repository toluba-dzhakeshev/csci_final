from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from files.models import db, Movie, Favorite, Rating, Genre, Year, Studio, Director, Producer, CastMember, ActivityLog
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import func
from files.app import model, cache
import json
import re
#TESTING RECOMMENDATION USING FAISS
import faiss 
from flask import current_app

# Blueprint for main user-facing routes
main_bp = Blueprint('main', __name__, template_folder='templates')

@cache.cached(timeout=300)
@main_bp.route('/', methods=['GET'])
def index():
    """
    Render the home page with filter options:
    - genres, studios, directors for dropdowns
    - min/max bounds for year and rating sliders
    """
    genres    = Genre.query.order_by(Genre.genre_name).all()
    studios   = Studio.query.order_by(Studio.studio_name).all()
    directors = Director.query.order_by(Director.director_name).all()

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

# AJAX endpoints for live search in Select2 widgets
@cache.cached(timeout=60, query_string=True)
@main_bp.route('/genre_search')
def genre_search():
    # Return JSON list of {id, text} matching the q parameter for genres.
    q = request.args.get('q','')
    matches = (Genre.query
               .filter(Genre.genre_name.ilike(f'%{q}%'))
               .order_by(Genre.genre_name)
               .limit(20)
               .all())
    return jsonify([{"id": g.genre_id, "text": g.genre_name} for g in matches])

@cache.cached(timeout=60, query_string=True)
@main_bp.route('/studio_search')
def studio_search():
    # Return JSON list of {id, text} matching the q parameter for studios.
    q = request.args.get('q','')
    matches = (Studio.query
               .filter(Studio.studio_name.ilike(f'%{q}%'))
               .order_by(Studio.studio_name)
               .limit(20)
               .all())
    return jsonify([{"id": s.studio_id, "text": s.studio_name} for s in matches])

@cache.cached(timeout=60, query_string=True)
@main_bp.route('/director_search')
def director_search():
    # Return JSON list of {id, text} matching the q parameter for directors.
    q = request.args.get('q','')
    matches = (Director.query
               .filter(Director.director_name.ilike(f'%{q}%'))
               .order_by(Director.director_name)
               .limit(20)
               .all())
    return jsonify([{"id": d.director_id, "text": d.director_name} for d in matches])

@cache.cached(timeout=60, query_string=True)
@main_bp.route('/producer_search')
def producer_search():
    # Return JSON list of {id, text} matching the q parameter for producers.
    q = request.args.get('q','')
    choices = Producer.query.filter(Producer.producer_name.ilike(f'%{q}%')) \
                            .order_by(Producer.producer_name) \
                            .limit(20).all()
    return jsonify([{"id": p.producer_id, "text": p.producer_name} for p in choices])

@cache.cached(timeout=60, query_string=True)
@main_bp.route('/cast_search')
def cast_search():
    # Return JSON list of {id, text} matching the q parameter for cast members.
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
    # Show the logged-in user’s favorite movies.
    favs = current_user.favorites
    return render_template('favorites.html', movies=favs)

@main_bp.route('/favorite/<int:mid>', methods=['POST'])
@login_required
def toggle_fav(mid):
    """
    Toggle favorite status for a given movie:
    - AJAX: return 204 No Content.
    - Form post: flash a message and redirect back.
    """
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

    log_activity(
        current_user.user_id,
        'toggle_fav',
        detail={'movie_id': mid, 'faved': now_fav}
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return ('', 204)

    next_page = request.form.get('next') or request.referrer or url_for('main.index')
    return redirect(next_page)

@main_bp.route('/recommend', methods=['GET','POST'])
def recommend():
    """
    Handle movie recommendation flow:
    - POST: validate English-only description, build query params, redirect to GET.
    - GET:  apply filters, then:
        If no description: simple title-ordered list + pagination.
        Else: encode description, compute cosine similarity, sort + paginate.
    Responds with JSON on AJAX “More” calls, HTML otherwise.
    """
    uid = current_user.user_id if current_user.is_authenticated else None

    if request.method == 'POST':
        
        # English-only check
        desc = request.form.get('description','').strip()
        if desc and not re.match(r'^[\x00-\x7F]+$', desc):
            flash('Please enter only English text in the description.', 'error')
            return redirect(request.url)
        
        # Redirect with all filter params
        params = {
            'description': request.form['description'],
            'genre':       request.form.get('genres',''),
            'studio':      request.form.get('studios',''),
            'director':    request.form.get('directors',''),
            'producer':    request.form.get('producers',''),
            'cast_member': request.form.get('cast_member',''),
            'year_from':   request.form.get('year_from',''),
            'year_to':     request.form.get('year_to',''),
            'rating_from': request.form.get('rating_from',''),
            'rating_to':   request.form.get('rating_to',''),
            'offset':      0,
            'limit':       5
        }
        return redirect(url_for('main.recommend', **params))

    # Parse GET args
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

    # Log the search (if logged in)
    if uid is not None:
        log_activity(
            uid,
            'search',
            detail={
                'description': desc,
                'genre': genre,
                'studio': studio,
                'director': director,
                'producer': producer,
                'cast_member': cast,
                'year_from': yf,
                'year_to': yt,
                'rating_from': rf,
                'rating_to': rt
            }
        )

    # Build base query with all filters
    q = Movie.query
    if genre:    q = q.join(Movie.genres).filter(Genre.genre_id   == int(genre))
    if studio:   q = q.join(Movie.studios).filter(Studio.studio_id  == int(studio))
    if director: q = q.filter(Movie.director_id     == int(director))
    if producer: q = q.join(Movie.producers).filter(Producer.producer_id == int(producer))
    if cast:     q = q.join(Movie.cast_members).filter(CastMember.cast_id == int(cast))
    if yf:       q = q.join(Movie.year).filter(Year.year_value       >= int(yf))
    if yt:       q = q.join(Movie.year).filter(Year.year_value       <= int(yt))
    if rf:       q = q.filter(Movie.avg_rating         >= float(rf))
    if rt:       q = q.filter(Movie.avg_rating         <= float(rt))
    candidates = q.all()
    # ——— FAISS SETUP ———
    has_filters = any([genre, studio, director, producer, cast, yf, yt, rf, rt])
    # ———  END FAISS SETUP  ———

    # Case: no description - simple paginate by title
    if not desc:
        all_movies = q.order_by(Movie.title).all()
        page       = all_movies[offset:offset+limit]
        has_more   = len(all_movies) > offset+limit

        payload = [{
            'sim':         0.0,
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
            'faved':       Favorite.query.get((uid, m.movie_id)) is not None,
            'avg_rating':  m.avg_rating,
        } for m in page]

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'movies':      payload,
                'next_offset': offset + limit,
                'has_more':    has_more
            })

        return render_template('results.html',
            recommendations=[(0.0, m) for m in page],
            next_offset=offset+limit,
            has_more=has_more
        )

    # Case: with description - compute embeddings + cosine similarity
    # emb_q = model.encode(desc)
    # if getattr(emb_q, "ndim", None) == 2:
    #     emb_q = emb_q.squeeze(0)

    # results = []
    # for m in candidates:
    #     if not Favorite.query.get((uid, m.movie_id)):
    #         try:
    #             vals = json.loads(m.embeddings)
    #         except json.JSONDecodeError:
    #             txt = m.embeddings.strip('[]').strip()
    #             vals = [float(x) for x in txt.split() if x]
    #         arr = np.array(vals, dtype=float)

    #         sim = arr.dot(emb_q) / (np.linalg.norm(arr) * np.linalg.norm(emb_q))
    #         results.append((sim, m))

    # # Sort by similarity and paginate
    # results.sort(key=lambda x: x[0], reverse=True)
    # page     = results[offset:offset+limit]
    # has_more = len(results) > offset + limit

    # if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    #     payload = [{
    #         'sim':         round(sim,2),
    #         'movie_id':    m.movie_id,
    #         'title':       m.title,
    #         'poster_url':  m.poster_url,
    #         'description': m.description,
    #         'year':        m.year.year_value,
    #         'genres':      [g.genre_name for g in m.genres],
    #         'studios':     [s.studio_name for s in m.studios],
    #         'director':    m.director.director_name,
    #         'producers':   [p.producer_name for p in m.producers],
    #         'cast':        [c.cast_name for c in m.cast_members],
    #         'duration':    m.duration,
    #         'page_url':    m.page_url,
    #         'faved':       Favorite.query.get((uid, m.movie_id)) is not None,
    #         'avg_rating':  m.avg_rating,
    #     } for sim,m in page]
    #     return jsonify({
    #         'movies':      payload,
    #         'next_offset': offset + limit,
    #         'has_more':    has_more
    #     })

    # return render_template(
    #     'results.html',
    #     recommendations=page,
    #     next_offset=offset + limit,
    #     has_more=has_more
    # )
    
    # ——— FAISS SETUP ———
    if desc and not has_filters:
        # embed & normalize
        emb = model.encode(desc).astype('float32').reshape(1, -1)
        faiss.normalize_L2(emb)

        # search full IVF index for top (offset+limit)
        D, I = current_app.faiss_index.search(emb, offset + limit)
        hits = [current_app.idx_to_id[i] for i in I[0] if i != -1]
        page_ids = hits[offset:offset+limit]
        has_more = len(hits) > offset+limit

        # load & order movies
        movies = Movie.query.filter(Movie.movie_id.in_(page_ids)).all()
        movies.sort(key=lambda m: page_ids.index(m.movie_id))

        payload = []
        for rank, m in enumerate(movies):
            payload.append({
                'sim':         float(D[0][offset+rank]),
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
                'faved':       Favorite.query.get((current_user.user_id, m.movie_id)) is not None,
                'avg_rating':  m.avg_rating
            })

        if request.headers.get('X-Requested-With'):
            return jsonify(movies=payload, next_offset=offset+limit, has_more=has_more)
        return render_template('results.html',
                               recommendations=list(zip([p['sim'] for p in payload], movies)),
                               next_offset=offset+limit,
                               has_more=has_more)

    # --- CASE 3: description + filters → FAISS + SQL restriction ---
    # embed & normalize
    emb = model.encode(desc).astype('float32').reshape(1, -1)
    faiss.normalize_L2(emb)

    # search all
    D, I = current_app.faiss_index.search(emb, current_app.faiss_index.ntotal)
    candidate_ids = {m.movie_id for m in candidates}

    # filter FAISS results down to our SQL candidates
    ranked = []
    for pos, idx in enumerate(I[0]):
        mid = current_app.idx_to_id[idx]
        if mid in candidate_ids:
            ranked.append((float(D[0][pos]), mid))

    # paginate
    page_ranked = ranked[offset:offset+limit]
    has_more    = len(ranked) > offset+limit
    mids        = [mid for _, mid in page_ranked]

    movies = Movie.query.filter(Movie.movie_id.in_(mids)).all()
    movies.sort(key=lambda m: mids.index(m.movie_id))

    payload = []
    for sim, mid in page_ranked:
        m = next(m for m in movies if m.movie_id == mid)
        payload.append({
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
            'faved':       Favorite.query.get((current_user.user_id, m.movie_id)) is not None,
            'avg_rating':  m.avg_rating
        })

    if request.headers.get('X-Requested-With'):
        return jsonify(movies=payload, next_offset=offset+limit, has_more=has_more)
    return render_template('results.html',
                           recommendations=[(p['sim'], Movie.query.get(p['movie_id'])) for p in payload],
                           next_offset=offset+limit,
                           has_more=has_more)
    # ———  END FAISS SETUP  ———

@main_bp.route('/results')
@login_required
def results():
    # Legacy /results route: filters, computes similarity, and renders same template.
    query     = request.args.get('query','')
    genre     = request.args.get('genre','')
    ymn, ymx  = request.args.get('year_from'), request.args.get('year_to')
    rmn, rmx  = request.args.get('rating_from'), request.args.get('rating_to')

    q = Movie.query
    if genre:
        q = q.join(Movie.genres).filter(Genre.genre_name==genre)

    if ymn: q = q.join(Movie.year).filter(Year.year_value>=int(ymn))
    if ymx: q = q.join(Movie.year).filter(Year.year_value<=int(ymx))
    
    if rmn: q = q.filter(Movie.avg_rating>=float(rmn))
    if rmx: q = q.filter(Movie.avg_rating<=float(rmx))
    
    q_emb = model.encode(query)
    scored = []
    for m in q.all():
        arr = np.fromstring(m.embeddings.strip('[]'), sep=' ')
        sim = np.dot(q_emb,arr)/(np.linalg.norm(q_emb)*np.linalg.norm(arr))
        
        if not Favorite.query.get((current_user.user_id,m.movie_id)):
            scored.append((sim,m))
    scored.sort(key=lambda x:-x[0])
    return render_template('results.html', results=scored)

@main_bp.route('/rate_model', methods=['POST'])
@login_required
def rate_model():
    # Upsert user’s rating of the recommendation model.
    movie_id = int(request.form['movie_id'])
    score    = int(request.form['model_rating'])

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

    log_activity(
    current_user.user_id,
        'rate_model',
        detail={'movie_id': movie_id, 'score': score}
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return ('', 204)
    
    flash(f'You rated the model {score}/10 on "{Movie.query.get(movie_id).title}"')
    return redirect(request.referrer or url_for('main.recommend'))

def log_activity(user_id, action, detail=None):
    # Record a user action in the ActivityLog table.
    entry = ActivityLog(user_id=user_id, action=action, detail=detail)
    db.session.add(entry)
    db.session.commit()
    