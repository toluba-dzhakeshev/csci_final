import streamlit as st
import pandas as pd
import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util

# Cache data (e.g., CSV data, embeddings) using st.cache_data
@st.cache_data
def load_data():
    data = pd.read_csv("./datasets/demo_movies.csv", sep=',')
    return data

@st.cache_data
def load_embeddings():
    embeddings = np.load("./models/film_embedded.npy")
    return embeddings

# Cache the model as a resource using st.cache_resource
@st.cache_resource
def load_model():
    model = SentenceTransformer('distilbert-base-nli-stsb-mean-tokens')
    return model

# Load data, embeddings, and model
data = load_data()
film_embeddings = load_embeddings()
model = load_model()


def get_top_10_recommendations(query, top_k=10):
    query_embedding = model.encode(query, convert_to_tensor=True)
    film_embeddings_tensor = torch.tensor(film_embeddings).to(query_embedding.device)
    
    similarities = util.pytorch_cos_sim(query_embedding, film_embeddings_tensor)[0]
    top_results = torch.argsort(similarities, descending=True)[:top_k]
    
    top_movies = data.iloc[top_results.cpu().numpy()].copy()
    similarity_scores = similarities[top_results].cpu().numpy()
    top_movies['similarity_score'] = similarity_scores
    
    top_movies['clickable_url'] = top_movies['title url'].apply(lambda x: f'<a href="{x}" target="_blank">Visit Page</a>')
    return top_movies

st.title("Movie Recommendation Demo")
st.write("Enter a description of the movie you are interested in:")

query = st.text_input("Movie Query", "A fast-paced sci-fi adventure")
if st.button("Get Recommendations"):
    with st.spinner("Generating recommendations..."):
        recommendations = get_top_10_recommendations(query)
        st.write("Top Recommendations:")
        html_table = recommendations[['title', 'year', 'genres', 'clickable_url', 'similarity_score']].to_html(escape=False, index=False)
        st.markdown(html_table, unsafe_allow_html=True)
