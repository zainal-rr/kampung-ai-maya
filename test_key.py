import requests
from config import get_env

key = get_env("KIMI_API_KEY")
urls = ["https://api.moonshot.cn/v1/models", "https://api.moonshot.ai/v1/models"]

if not key:
    raise ValueError("KIMI_API_KEY environment variable not set.")

for url in urls:
    print(f"Testing {url}...")
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=15,
        )
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
