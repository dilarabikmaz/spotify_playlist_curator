import os

from flask import Flask, request, redirect, session, url_for, render_template

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import FlaskSessionCacheHandler
from tenacity import retry, wait_exponential, stop_after_attempt
from spotipy.client import SpotifyException


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(64)

client_id = 'f334da4c95b9476fb858777b40a31316'
client_secret = '3fe138f0e26541279abbc51f200adebd'
redirect_uri = 'http://localhost:5000/callback'
scope = 'user-library-read playlist-modify-public playlist-modify-private'

cache_handler = FlaskSessionCacheHandler(session)
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=scope,
    cache_handler=cache_handler,
    show_dialog=True # for debugging puposes
)
# create an instance of Spotify Client
sp = Spotify(auth_manager=sp_oauth, requests_timeout=30)

@app.route('/')
def home():
    # if the user is visiting the home page but they are not logged in yet, take them to the log in with Spotify page
    token = cache_handler.get_cached_token()
    if not sp_oauth.validate_token(token):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    # all_liked_songs = get_liked_songs(token)
    return redirect(url_for('main'))

def filter_songs_by_keywords(liked_songs, keywords):
    """
    filtered_songs = []
    for song in liked_songs:
        print(f"Processing song: {song}")  # Debugging statement
        song_name = song['track']['name'].lower()
        song_artists = [artist['name'].lower() for artist in song['track']['artists']]
        song_album = song['track']['album']['name'].lower()
        
        if any(keyword in song_name for keyword in keywords) or \
        any(keyword in artist for keyword in keywords for artist in song_artists) or \
        any(keyword in song_album for keyword in keywords):
            filtered_songs.append(song)
        
        if len(filtered_songs) >= 20:
            break
    
    return filtered_songs
    """
    filtered_songs = []
    keywords = [keyword.lower() for keyword in keywords]  # Convert all keywords to lowercase for case-insensitive comparison
    
    for song in liked_songs:
        print(f"Processing song: {song['track']['name']}")  # Debugging statement
        song_name = song['track']['name'].lower()
        song_artists = [artist['name'].lower() for artist in song['track']['artists']]
        song_album = song['track']['album']['name'].lower()
        
        if any(keyword in song_name for keyword in keywords) or \
           any(keyword in artist for keyword in keywords for artist in song_artists) or \
           any(keyword in song_album for keyword in keywords):
            filtered_songs.append(song)
        
        if len(filtered_songs) >= 20:  # Limit the results to the first 20 matches
            break
    
    return filtered_songs

def create_playlist(token, user_id, name, description, playlist_public):
    sp = Spotify(auth=token)
    if playlist_public == "Yes":
        playlist = sp.user_playlist_create(user_id, name, description=description)
    else:
        playlist = sp.user_playlist_create(user_id, name, description=description, public=False)
    return playlist

def add_songs_to_playlist(token, playlist_id, track_uris):
    sp = Spotify(auth=token)
    sp.user_playlist_add_tracks(user=sp.current_user()['id'], playlist_id=playlist_id, tracks=track_uris)

@app.route('/main', methods=['GET', 'POST'])
def main():
    # prompt user for keywords
    token_info = cache_handler.get_cached_token()
    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    
    filtered_songs = []

    token = token_info['access_token']
    user_id = Spotify(auth=token).current_user()['id']

    if request.method == 'POST':
        keywords = request.form['keywords'].split(',')
        keywords = [keyword.strip().lower() for keyword in keywords]
        playlist_public = request.form['public']

        return redirect(url_for('loading', keywords=','.join(keywords), public=playlist_public))
    
    return render_template('main.html')

@app.route('/loading')
def loading():
    try:
        keywords = request.args.get('keywords').split(',')
        playlist_public = request.args.get('public')

        token_info = cache_handler.get_cached_token()
        if not token_info:
            auth_url = sp_oauth.get_authorize_url()
            return redirect(auth_url)
        
        filtered_songs = []

        token = token_info['access_token']
        user_id = Spotify(auth=token).current_user()['id']

        all_liked_songs = get_liked_songs()
        print(f"Liked songs: {all_liked_songs}")  # Debugging statement
        filtered_songs = filter_songs_by_keywords(all_liked_songs, keywords)
        
        if filtered_songs:
            playlist_name = "Filtered Songs Playlist"
            playlist_description = "A playlist created from your liked songs based on your keywords."
            playlist = create_playlist(token, user_id, playlist_name, playlist_description, playlist_public)
            playlist_id = playlist['id']

            track_uris = [song['track']['uri'] for song in filtered_songs]
            add_songs_to_playlist(token, playlist_id, track_uris)

            # Get playlist cover image URL
            playlist_details = sp.playlist(playlist_id)
            cover_image_url = playlist_details['images'][0]['url'] if playlist_details['images'] else None

            return render_template('playlist_preview.html', playlist_name=playlist_name, songs=filtered_songs, cover_image_url=cover_image_url)
        else:
            return render_template('error.html')
    except SpotifyException as e:
        return f"An error occurred: {e}"

@app.route('/callback')
def callback():
    sp_oauth.get_access_token(request.args['code'])
    return redirect(url_for('main'))

def get_liked_songs():
    if not sp_oauth.validate_token(cache_handler.get_cached_token()):
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)

    liked_songs = []
    results = sp.current_user_saved_tracks(limit=50)
    liked_songs.extend(results['items'])
    while results['next']:
        results = sp.next(results)
        liked_songs.extend(results['items'])
    
    return liked_songs

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)