import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models.user import User
from app.auth.security import hash_password

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Add test users
    admin = User(username="testadmin", password_hash=hash_password("Admin@123"), role="ADMIN")
    operator = User(username="testoperator", password_hash=hash_password("Operator@123"), role="OPERATOR")
    
    db.add(admin)
    db.add(operator)
    db.commit()
    db.close()
    
    yield
    
    Base.metadata.drop_all(bind=engine)

def test_login_success():
    response = client.post("/api/auth/login", json={"username": "testadmin", "password": "Admin@123"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_failure():
    response = client.post("/api/auth/login", json={"username": "testadmin", "password": "wrongpassword"})
    assert response.status_code == 401

def test_no_token_access():
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_admin_access():
    # Login as admin
    login_res = client.post("/api/auth/login", json={"username": "testadmin", "password": "Admin@123"})
    token = login_res.json()["access_token"]
    
    # Try accessing admin-only route (e.g. watchlist POST)
    # Note: testing watchlist requires more payload, let's test a GET if admin-only, 
    # but the PDF says Add/update/delete cameras or manage watchlist are admin only.
    # We can just test a GET or POST.
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/cameras", json={
        "name": "TestCam", 
        "department": "Police",
        "camera_type": "Fixed",
        "owner": "Test",
        "latitude": 0.0,
        "longitude": 0.0
    }, headers=headers)
    
    assert response.status_code in [200, 201] # Since it's authorized. Might be 201 if created.

def test_operator_forbidden_access():
    # Login as operator
    login_res = client.post("/api/auth/login", json={"username": "testoperator", "password": "Operator@123"})
    token = login_res.json()["access_token"]
    
    # Try accessing admin-only route
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/cameras", json={
        "name": "TestCam2", 
        "department": "Police",
        "camera_type": "Fixed",
        "owner": "Test",
        "latitude": 0.0,
        "longitude": 0.0
    }, headers=headers)
    
    assert response.status_code == 403

def test_operator_allowed_access():
    # Login as operator
    login_res = client.post("/api/auth/login", json={"username": "testoperator", "password": "Operator@123"})
    token = login_res.json()["access_token"]
    
    # Try accessing public/operator route
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/cameras", headers=headers)
    assert response.status_code == 200
