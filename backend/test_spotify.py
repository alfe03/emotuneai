import spotipy
import sys
import os

token = "BQAk2rUCiT79QWmqL0sORrTCd64KCpiRB1D4UKDKr7trCjcWw8s0v5cpNAxTTSYISQAhh0aGwNO3X86iMRqPYkGNL9_-savcY5mNfzjEPpttvubPQ1onAuHAKzuphv-_pRvrOnGGLLHHQybxxwZ7CQwCSsm7T2wDfHRjcMh5QVF3hqcHzT-NKok-1PDc-jOSLCIfAAw8Dc-Zm0GjcMRt-56ND2RSBW36BQ_JoVWKtWfFASUjBDVIpkvYGwmPgLlz4PXFNaWC6crTW1384N1OmK--Mq8UzOnilKPHN0SttKGdzXrDTdSV2l7GZzuO9tY"

try:
    sp = spotipy.Spotify(auth=token)
    user = sp.current_user()
    user_id = user['id']
    print("User ID:", user_id)
    print("Email:", user.get("email"))
    
    # Check if we can create a playlist
    playlist = sp.user_playlist_create(
        user=user_id,
        name="Test Playlist EmoTuneAI",
        public=False,
        description="Just a test"
    )
    print("Successfully created playlist!")
    print("Playlist ID:", playlist['id'])
except Exception as e:
    print("Failed to create playlist!")
    print("Error:", e)
    
    # Try fetching public profile
    try:
        prof = sp.user(user_id)
        print("Public profile fetched successfully")
    except Exception as e2:
        print("Failed to fetch public profile:", e2)
