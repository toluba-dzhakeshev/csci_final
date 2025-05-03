index.js
Purpose: This file makes the movie page interactive. It lets you add or remove favorites, send star ratings, show extra movie details, set up search filters and sliders, and load more movies without reloading the page.

styles.css
Purpose: Adds visual styling for the star-rating widget, the horizontal range sliders, form buttons, and the multi-select filters, with special tweaks for dark mode.

activity.html
Purpose: Renders a page that lists user activity logs in a table showing when each action occurred, which user performed it, the action name, and JSON-formatted details.

movie_form.html
Purpose: A page template that shows a form for adding a new movie or editing an existing one, with inputs for title, description, rating, duration, links, year, director, genres, studios, producers, cast members, embeddings, and buttons to save or cancel.

movies.html
Purpose: Shows an admin table of all movies with their title, year, and director, and provides buttons to add a new movie, edit or delete existing ones, plus a “More” link for pagination.

stats.html
Purpose: Displays two tables of usage metrics: the top 10 most-favorited movies and the top 10 movies ranked by recommendation model performance.

users.html
Purpose: Shows a table of every user with their email, join date, and whether they’re active, disabled, or an admin, and lets you disable or re-enable non-admin accounts.

favorites.html
Purpose: Shows the logged-in user’s favorite movies with details and lets them remove any movie from their list.

index.html
Purpose: Shows the main search form where users can enter a movie description and use filters (genres, studios, directors, producers, cast members, year, and rating) to find recommended movies.

layout.html
Purpose: Serves as the base page template, setting up the HTML head (styles, scripts, meta tags), the navigation bar (with login/logout and admin links), a dark/light theme toggle, and defining blocks for page-specific content and scripts.

login.html
Purpose: Provides a centered login form with email and password fields, displays any error messages, and offers a link to the sign-up page.

results.html
Purpose: Displays a list of recommended movies with their similarity scores and ratings, lets users rate the recommendation model, view more details, add or remove favorites, and load more results without reloading the page.

signup.html
Purpose: Shows a centered form for new users to create an account with email and password fields, displays any error messages, and links to the login page.

admin.py
Purpose: Sets up the admin section of the app—only accessible by administrators—so they can list and toggle user accounts, add/edit/delete movies, view usage statistics, and inspect recent activity logs.

app.py
Purpose: Creates and sets up the Flask application with CSRF protection, caching, database access, and user login, registers all route blueprints, and loads the SentenceTransformer model for converting movie descriptions into embeddings.

auth.py
Purpose: Handles user registration, login, and logout. It checks and hashes passwords, prevents duplicate accounts, and manages user sessions.

main.py
Purpose: Defines the user-facing routes for searching and filtering movies, handling AJAX lookups for filters, managing favorites, running recommendation logic (with or without free-text input), and logging user actions.

models.py
Purpose: Defines the database tables and relationships for users, movies, favorites, ratings, lookup lists (genres, studios, directors, producers, cast members, years), and logs user actions for analytics.

dataprepnote.ipynb
Purpose: Cleans raw movie data by dropping entries without descriptions, filtering for English text, and then merges the cleaned metadata with precomputed embeddings before exporting the combined dataset.

model_training.ipynb
Purpose: Loads cleaned movie data, cleans descriptions, generates sentence embeddings with multiple SBERT models, defines similarity metrics and a helper to get top recommendations for a query, tests example queries, and then saves the combined embeddings for future use.

next_gen_db.ipynb
Purpose: Connects to the PostgreSQL database, drops and recreates all tables from the ORM models, and reads the merged movie-plus-embeddings CSV. It then populates lookup tables, inserts each movie with its related genres, studios, producers, cast members, and ensures a default admin user exists.

parsenote.ipynbg
Purpose: Automates crawling and scraping movie details from Letterboxd using Selenium and BeautifulSoup, parses each film’s metadata (rating, description, cast, crew, etc.), periodically saves batches to CSV, then merges all partial files into one comprehensive dataset.

test_app.py
Purpose: Contains pytest-based unit and integration tests for the Flask application, covering database CRUD operations, embedding parsing, search and recommendation endpoints (including AJAX behavior), similarity calculations, helper utilities like _upsert_list, and admin access control.
