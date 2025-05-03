# Draft file is created to test and check code
from files.app import create_app
from files.models import db, Movie

app = create_app()
with app.app_context():
    m = Movie.query.filter_by(title='Love Today').first()
    print("Studios:",      [s.studio_name  for s in m.studios])
    print("Director:",     m.director.director_name if m.director else None)
    print("Producers:",    [p.producer_name for p in m.producers])
    print("Cast:",         [c.cast_name     for c in m.cast_members])
    print("Year:",         m.year.year_value if m.year else None)