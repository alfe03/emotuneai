import requests

base_url = "http://127.0.0.1:8000"

def test_api():
    print("Testing API...")
    
    # 1. Test register
    try:
        res = requests.post(f"{base_url}/api/auth/register", json={
            "email": "testuser@example.com",
            "username": "testuser",
            "password": "password123"
        })
        print("Register:", res.status_code, res.json())
    except Exception as e:
        print("Register failed:", e)

    # 2. Test login
    try:
        res = requests.post(f"{base_url}/api/auth/login", json={
            "email": "testuser@example.com",
            "password": "password123"
        })
        print("Login:", res.status_code, res.json())
        token = res.json().get("access_token")
    except Exception as e:
        print("Login failed:", e)
        token = None

    if token:
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Test me
        try:
            res = requests.get(f"{base_url}/api/auth/me", headers=headers)
            print("Me:", res.status_code, res.json())
        except Exception as e:
            print("Me failed:", e)
            
        # 4. Test mood manual
        try:
            res = requests.post(f"{base_url}/api/mood/manual", json={
                "mood": "happy",
                "language": "tr",
                "content_type": "track"
            }, headers=headers)
            print("Mood Manual:", res.status_code, str(res.json())[:100] + "...")
        except Exception as e:
            print("Mood Manual failed:", e)

if __name__ == "__main__":
    test_api()
