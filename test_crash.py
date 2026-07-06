import sys
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

print("=== Sending Request 1 ===")
res1 = client.post("/api/complaint", json={
    "complaint": "subah se light nhi aari hai bc",
    "location": "shah faisal",
    "user_id": "test-user-123"
})
print("Status 1:", res1.status_code)
if res1.status_code != 200:
    print(res1.text)

print("\n=== Sending Request 2 ===")
res2 = client.post("/api/complaint", json={
    "complaint": "3 din se paani nhi aara bc",
    "location": "shah faisal",
    "user_id": "test-user-123"
})
print("Status 2:", res2.status_code)
if res2.status_code != 200:
    print(res2.text)
