from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from functools   import wraps
from files.models      import db, User, Movie, ActivityLog, Genre, Studio, Director, Producer, CastMember, Year, Favorite
import json
from sqlalchemy import func, cast, Integer

# Blueprint setup for admin routes, all URLs prefixed with /admin
admin_bp = Blueprint(
    'admin', __name__,
    template_folder='templates/admin',
    url_prefix='/admin'
)

def admin_required(f):
    # Decorator to ensure that the current user is both authenticated and an admin. Returns 403 Forbidden if not.
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not (current_user.is_authenticated and current_user.is_admin):
            abort(403)
        return f(*args, **kwargs)
    return wrapper

@admin_bp.route('/users')
@login_required
@admin_required
def list_users():
    # Display a table of all users.
    users = User.query.order_by(User.user_id).all()
    return render_template('users.html', users=users)

@admin_bp.route('/users/<int:uid>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(uid):
    # Enable or disable a user account. Flips the `active` flag and flashes a status message.
    u = User.query.get_or_404(uid)

    u.active = not u.active
    db.session.commit()
    flash(
      'Re-enabled' if u.active else 'Disabled'
      f' account for {u.email}', 'success'
    )
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/movies')
@login_required
@admin_required
def list_movies():
    # Paginated list of movies for the admin to browse/edit/delete.
    page     = request.args.get('page', 1, type=int)
    per_page = 10

    total    = Movie.query.count()

    movies = (
      Movie.query
           .order_by(Movie.title)
           .offset((page - 1) * per_page)
           .limit(per_page)
           .all()
    )

    more = page * per_page < total

    return render_template(
      'movies.html',
      movies=movies,
      page=page,
      more=more
    )

def _upsert_list(field_name, cls, rel, parent_obj):
    # Generic helper to read a comma-separated list of names from form,
    # find or create each instance of `cls` by its *_name column,
    # and assign them to `parent_obj.<rel>`, handling many-to-many.
    raw   = request.form.get(field_name, '')
    names = [n.strip() for n in raw.split(',') if n.strip()]

    # Identify the `<tablename>_name` column on the class
    name_cols = [c.name for c in cls.__table__.columns if c.name.endswith('_name')]
    if not name_cols:
        raise RuntimeError(f"No '*_name' column on {cls.__name__}")
    name_col = name_cols[0]

    objs = []
    for name in names:
        # Try to find existing, else create new
        obj = cls.query.filter(getattr(cls, name_col) == name).first()
        if not obj:
            obj = cls(**{name_col: name})
            db.session.add(obj)
            db.session.flush()
        objs.append(obj)

    setattr(parent_obj, rel, objs)

@admin_bp.route('/movies/new', methods=['GET', 'POST'])
@login_required
@admin_required
def add_movie():
    # Form to add a new movie. On POST, validates and upserts related fields, then commits the new Movie record.
    
    # Preload select options
    all_years     = Year.query.order_by(Year.year_value).all()
    all_directors = Director.query.order_by(Director.director_name).all()
    all_genres    = Genre.query.order_by(Genre.genre_name).all()
    all_studios   = Studio.query.order_by(Studio.studio_name).all()
    all_producers = Producer.query.order_by(Producer.producer_name).all()
    all_cast      = CastMember.query.order_by(CastMember.cast_name).all()

    if request.method == 'POST':
        from app import model # sentence-transformer instance

        # Required text fields
        title       = request.form.get('title','').strip()
        description = request.form.get('description','').strip()
        
        # Numeric fields with fallback
        try:
            avg_rating = float(request.form.get('avg_rating','') or 0)
        except ValueError:
            avg_rating = 0.0
        try:
            duration = int(request.form.get('duration','') or 0)
        except ValueError:
            duration = 0
            
        # Optional URLs with defaults
        poster_url = request.form.get('poster_url','').strip() or \
            'https://as1.ftcdn.net/jpg/02/57/42/72/1000_F_257427286_Lp7c9XdPnvN46TyFKqUaZpPADJ77ZzUk.jpg'
        page_url   = request.form.get('page_url','').strip() or None

        # Upsert Year
        year_val = request.form.get('year_value','').strip()
        year = None
        if year_val.isdigit():
            year_val = int(year_val)
            year = Year.query.filter_by(year_value=year_val).first()
            if not year:
                year = Year(year_value=year_val)
                db.session.add(year)
                db.session.flush()

        # Upsert Director
        director_name = request.form.get('director','').strip()
        director = None
        if director_name:
            director = Director.query.filter_by(director_name=director_name).first()
            if not director:
                director = Director(director_name=director_name)
                db.session.add(director)
                db.session.flush()

        # Encode description to embeddings
        emb = model.encode(description).tolist()

        # Build Movie object
        m = Movie(
            title=title,
            description=description,
            avg_rating=avg_rating,
            duration=duration,
            poster_url=poster_url,
            page_url=page_url,
            year=year,
            director=director,
            embeddings=json.dumps(emb)
        )

        # Upsert M2M lists
        _upsert_list('genres',       Genre,      'genres',       m)
        _upsert_list('studios',      Studio,     'studios',      m)
        _upsert_list('producers',    Producer,   'producers',    m)
        _upsert_list('cast_members', CastMember, 'cast_members', m)

        # Commit and redirect
        db.session.add(m)
        db.session.commit()
        flash('Movie added', 'success')
        return redirect(url_for('admin.list_movies'))

    # GET → render empty form
    return render_template(
        'movie_form.html',
        movie=None,
        all_years=all_years,
        all_directors=all_directors,
        all_genres=all_genres,
        all_studios=all_studios,
        all_producers=all_producers,
        all_cast=all_cast
    )

@admin_bp.route('/movies/<int:mid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_movie(mid):
    # Edit an existing movie. Mirrors add_movie but updates an existing instance.
    m = Movie.query.get_or_404(mid)
    # Preload select options as above
    all_years     = Year.query.order_by(Year.year_value).all()
    all_directors = Director.query.order_by(Director.director_name).all()
    all_genres    = Genre.query.order_by(Genre.genre_name).all()
    all_studios   = Studio.query.order_by(Studio.studio_name).all()
    all_producers = Producer.query.order_by(Producer.producer_name).all()
    all_cast      = CastMember.query.order_by(CastMember.cast_name).all()

    if request.method == 'POST':
        from app import model

        # Update scalar fields
        m.title       = request.form['title']
        m.description = request.form['description']
        m.avg_rating  = float(request.form['avg_rating'])
        m.duration    = int(request.form['duration'])
        m.poster_url  = request.form['poster_url']
        m.page_url    = request.form['page_url']

        # Upsert Year
        year_val = int(request.form['year_value'])
        year = Year.query.filter_by(year_value=year_val).first()
        if not year:
            year = Year(year_value=year_val)
            db.session.add(year)
            db.session.flush()
        m.year = year

        # Upsert Director
        director_name = request.form['director']
        director = Director.query.filter_by(director_name=director_name).first()
        if not director:
            director = Director(director_name=director_name)
            db.session.add(director)
            db.session.flush()
        m.director = director

        # Recompute embeddings if description changed
        m.embeddings = json.dumps(model.encode(m.description).tolist())

        # Refresh M2M lists
        _upsert_list('genres',       Genre,      'genres',       m)
        _upsert_list('studios',      Studio,     'studios',      m)
        _upsert_list('producers',    Producer,   'producers',    m)
        _upsert_list('cast_members', CastMember, 'cast_members', m)

        db.session.commit()
        flash('Movie updated', 'success')
        return redirect(url_for('admin.list_movies'))

    # GET → render form with existing data
    return render_template(
        'movie_form.html',
        movie=m,
        all_years=all_years,
        all_directors=all_directors,
        all_genres=all_genres,
        all_studios=all_studios,
        all_producers=all_producers,
        all_cast=all_cast
    )

@admin_bp.route('/stats')
@login_required
@admin_required
def stats():
    # Show admin statistics: top favorited movies and average model‐rating.
    fav_counts = (
      db.session.query(Movie.title, func.count().label('cnt'))
                .join(Favorite)
                .group_by(Movie.title)
                .order_by(func.count().desc())
                .limit(10)
                .all()
    )

    # Use cast on JSON detail field since PostgreSQL
    avg_model = (
      db.session.query(
          Movie.title,
          func.avg(cast(ActivityLog.detail['score'], Integer))
              .label('avg_score')
      )
      .join(ActivityLog, cast(ActivityLog.detail['movie_id'], Integer) == Movie.movie_id)
      .filter(ActivityLog.action=='rate_model')
      .group_by(Movie.title)
      .order_by(func.avg(cast(ActivityLog.detail['score'], Integer)).desc())
      .limit(10)
      .all()
    )

    return render_template('stats.html',
                           fav_counts=fav_counts,
                           avg_model=avg_model)
    
@admin_bp.route('/activity')
@login_required
@admin_required
def view_activity():
    # Display the latest 200 activity log entries.
    logs = ActivityLog.query.join(ActivityLog.user) \
                             .order_by(ActivityLog.created_at.desc()) \
                             .limit(200).all()
    return render_template('activity.html', logs=logs)

@admin_bp.route('/movies/<int:mid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_movie(mid):
    # Permanently delete a movie record.
    m = Movie.query.get_or_404(mid)
    db.session.delete(m)
    db.session.commit()
    flash(f'"{m.title}" has been deleted.', 'success')
    return redirect(url_for('admin.list_movies'))
