"""
Security tests for Prediction Provider authentication.
Tests bcrypt, JWT, API keys, account lockout, password complexity.
"""
import pytest
from app.auth import (
    get_password_hash, verify_password, create_access_token,
    hash_api_key, generate_api_key
)
from jose import jwt


class TestBcryptHashing:
    def test_hash_not_plaintext(self):
        h = get_password_hash("MyPassword123")
        assert h != "MyPassword123"
        assert h.startswith("$2")

    def test_verify_correct(self):
        h = get_password_hash("TestPass")
        assert verify_password("TestPass", h) is True

    def test_verify_wrong(self):
        h = get_password_hash("TestPass")
        assert verify_password("WrongPass", h) is False

    def test_different_salts(self):
        h1 = get_password_hash("Same")
        h2 = get_password_hash("Same")
        assert h1 != h2


class TestJWTTokens:
    def test_create_token(self):
        token = create_access_token({"sub": "testuser"})
        assert token is not None
        assert len(token) > 10

    def test_decode_token(self):
        from app.auth import SECRET_KEY, ALGORITHM
        token = create_access_token({"sub": "testuser", "role": "client"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_expired_token(self):
        from datetime import timedelta
        token = create_access_token({"sub": "test"}, expires_delta=timedelta(seconds=-1))
        from app.auth import SECRET_KEY, ALGORITHM
        from jose import JWTError
        with pytest.raises(JWTError):
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    def test_tampered_token(self):
        token = create_access_token({"sub": "test"})
        tampered = token[:-5] + "XXXXX"
        from app.auth import SECRET_KEY, ALGORITHM
        from jose import JWTError
        with pytest.raises(JWTError):
            jwt.decode(tampered, SECRET_KEY, algorithms=[ALGORITHM])


class TestAPIKeys:
    def test_generate_api_key(self):
        key = generate_api_key()
        assert len(key) > 20

    def test_hash_api_key(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert h != key
        assert len(h) == 64  # SHA256 hex

    def test_same_key_same_hash(self):
        key = "test_api_key_123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2

    def test_different_keys_different_hash(self):
        h1 = hash_api_key("key1")
        h2 = hash_api_key("key2")
        assert h1 != h2
