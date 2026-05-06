import requests
import os

api_url = "https://test-konnekt-api-k8s.kariyer.net/api/v1/powerbi/upload"
file_path = os.path.join("temp_pbix", "FinalCheck (1).pbix")

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit(1)

print(f"Uploading {file_path}...")

with open(file_path, "rb") as f:
    files = {"file": ("_Satislar.pbix", f, "application/octet-stream")}
    try:
        response = requests.post(api_url, files=files, timeout=60)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Successfully parsed!")
            print(f"Tables: {len(data.get('tables', []))}")
            print(f"Measures: {len(data.get('measures', []))}")
            print(f"Relationships: {len(data.get('relationships', []))}")
            measures = data.get('measures', [])
            if measures:
                print("\nSample Measures:")
                for m in measures[:3]:
                    print(f"- {m.get('name')}: {m.get('expression')[:50]}...")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")
