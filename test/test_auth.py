def test_signup_successful(client):
    user_data = {
        "name": "TestUser",
        "login": "testlogin1",
        "password": "secretP"
    }
    response = client.post("/auth/signup", json=user_data)
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["login"] == user_data["login"]


def test_login_successful(client):
    user_data = {
        "name": "TestUser",
        "login": "testlogin",
        "password": "secretP"
    }
    client.post("/auth/signup", json=user_data)
    login_data = {"username": "testlogin", "password": "secretP"}
    response = client.post("/auth/login", data=login_data)
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_refresh_token_successful(client):
    user_data = {
        "name": "TestUser",
        "login": "testlogin",
        "password": "secretP"
    }
    client.post("/auth/signup", json=user_data)
    login_data = {"username": "testlogin", "password": "secretP"}
    login_resp = client.post("/auth/login", data=login_data)
    token_data = login_resp.json()
    refresh_token = token_data["refresh_token"]

    response = client.get(
        "/auth/refresh_token", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert response.status_code == 200
    new_token_data = response.json()
    assert "access_token" in new_token_data
    assert "refresh_token" in new_token_data
    assert new_token_data["token_type"] == "bearer"
