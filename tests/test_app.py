import json
import pytest
from flask import url_for
from files.app import create_app, db
from files.admin import _upsert_list
from files.models import (
    Movie, Genre, Year, Director, Producer, CastMember, Favorite, User
)
import numpy as np

@pytest.fixture
def app():
    test_cfg = {
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
    }

    app = create_app(test_cfg)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

#Unit tests for models CRUD and embedding parsing
def test_movie_crud_and_embedding(app):
    y = Year(year_value=2020)
    d = Director(director_name='DirTest')
    db.session.add_all([y, d])
    db.session.commit()

    emb = [0.1, 0.2, 0.3]
    m = Movie(
        title='TestMovie',
        description='Desc',
        avg_rating=7.5,
        duration=120,
        poster_url='http://x',
        page_url='http://y',
        year=y,
        director=d,
        embeddings=json.dumps(emb)
    )
    db.session.add(m)
    db.session.commit()

    fetched = Movie.query.filter_by(title='TestMovie').first()
    assert fetched is not None
    assert fetched.avg_rating == 7.5

    parsed = json.loads(fetched.embeddings)
    assert parsed == emb

    fetched.title = 'NewTitle'
    db.session.commit()
    assert Movie.query.filter_by(title='NewTitle').one() is not None

    db.session.delete(fetched)
    db.session.commit()
    assert Movie.query.count() == 0

#Integration tests for endpoints
def test_index_page(client):
    rv = client.get(url_for('main.index'))
    assert rv.status_code == 200
    assert b'Find Your Next Movie' in rv.data

def test_genre_search_endpoint(client, app):

    with app.app_context():
        g = Genre(genre_name='Comedy')
        db.session.add(g)
        db.session.commit()
    rv = client.get(url_for('main.genre_search', q='Com'))
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)
    assert data and data[0]['text'] == 'Comedy'

def test_recommend_empty_description(client, app):
    with app.app_context():
        y = Year(year_value=2021)
        d = Director(director_name='DirA')
        emb = [0.0]*384
        m = Movie(
            title='EmptyDescMovie',
            description='',
            avg_rating=4.0,
            duration=90,
            poster_url='',
            page_url='',
            year=y,
            director=d,
            embeddings=json.dumps(emb)
        )
        db.session.add_all([y, d, m])
        db.session.commit()

    rv = client.post(
        url_for('main.recommend'),
        data={'description': '', 'offset': 0, 'limit': 5},
        follow_redirects=True
    )
    assert rv.status_code == 200
    assert b'EmptyDescMovie' in rv.data

@pytest.mark.parametrize("ajax,expected_json", [
    (True, True),
    (False, False)
])
def test_recommend_ajax_more(client, app, ajax, expected_json):
    with app.app_context():
        y = Year(year_value=2022)
        d = Director(director_name='D2')
        emb = [0.0]*384
        m1 = Movie(title='M1', description='', avg_rating=5.0, duration=80,
                   poster_url='', page_url='', year=y, director=d, embeddings=json.dumps(emb))
        m2 = Movie(title='M2', description='', avg_rating=6.0, duration=95,
                   poster_url='', page_url='', year=y, director=d, embeddings=json.dumps(emb))
        db.session.add_all([y, d, m1, m2])
        db.session.commit()

    query = 'description=&offset=0&limit=1'
    headers = {'X-Requested-With': 'XMLHttpRequest'} if ajax else {}
    rv = client.get(f"/recommend?{query}", headers=headers)
    if ajax:
        assert rv.is_json
        payload = rv.get_json()
        assert 'movies' in payload and len(payload['movies']) == 1
    else:
        assert b'M1' in rv.data

#Unit test for cosine‐sim step, including 1.0 identity
def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def test_similarity_identity_and_difference():
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([1.0, 0.0, 0.0])
    v3 = np.array([0.0, 1.0, 0.0])

    assert pytest.approx(cosine(v1, v2), rel=1e-6) == 1.0
    assert cosine(v1, v3) == pytest.approx(0.0, abs=1e-6)
    
#Unit test for the upsert‐list helper
class DummyObj:
    pass

def test_upsert_list_creates_and_assigns(app):
    with app.app_context():
        Genre.query.delete()
        db.session.commit()

    class Dummy: pass

    with app.test_request_context('/', method='POST', data={}):
        dummy = Dummy()
        _upsert_list('genres', Genre, 'genres', dummy)
        assert getattr(dummy, 'genres', []) == []

    with app.test_request_context(
        '/', method='POST', data={'genres':'A, B, C'}
    ):
        dummy2 = Dummy()
        _upsert_list('genres', Genre, 'genres', dummy2)

        names = [g.genre_name for g in dummy2.genres]
        assert names == ['A','B','C']
        assert Genre.query.filter_by(genre_name='B').one()

#Integration tests for admin endpoints
def login(client, email, password):
    return client.post(
        url_for("auth.login"),
        data={"email": email, "password": password},
        follow_redirects=True,
    )

@pytest.fixture
def admin_user(app):
    u = User(email="ad@test.com", is_admin=True)
    u.set_password("pw")
    db.session.add(u)
    db.session.commit()
    return u

def test_admin_users_requires_admin(client, app):
    with app.app_context():
        u = User(email="u@test.com")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()
    login(client, "u@test.com", "pw")
    rv = client.get("/admin/users")
    assert rv.status_code == 403

def test_toggle_user_flip_state(client, admin_user):
    login(client, admin_user.email, "pw")
    rv = client.post(url_for("admin.toggle_user", uid=admin_user.user_id), follow_redirects=True)
    from files.models import User as U
    assert not U.query.get(admin_user.user_id).active

#Integration tests around favorite AJAX vs form‐post
@pytest.fixture
def movie_and_user(app):
    y = Year(year_value=2023)
    d = Director(director_name="X")
    m = Movie(
        title="FavTest", description="", avg_rating=1.0, duration=10,
        poster_url="", page_url="", year=y, director=d,
        embeddings=json.dumps([0]*384)
    )
    u = User(email="fav@test.com")
    u.set_password("pw")
    db.session.add_all([y, d, m, u])
    db.session.commit()
    return u, m
