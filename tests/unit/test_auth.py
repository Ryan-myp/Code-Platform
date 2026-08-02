#!/usr/bin/env python3
"""小团智能平台 — 认证模块测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        from common.auth import hash_password
        hashed = hash_password("test_password_123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        from common.auth import hash_password, verify_password
        password = "my_secure_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        from common.auth import hash_password, verify_password
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_passwords_produce_different_hashes(self):
        from common.auth import hash_password
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")
        assert hash1 != hash2


class TestTokenGeneration:
    def test_create_access_token_returns_string(self):
        from common.auth import create_access_token
        token = create_access_token("test_user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token_returns_payload(self):
        from common.auth import create_access_token, decode_access_token
        token = create_access_token("test_subject")
        payload = decode_access_token(token)
        assert payload["sub"] == "test_subject"

    def test_decode_invalid_token_raises(self):
        from common.auth import decode_access_token
        try:
            decode_access_token("invalid.token.here")
            assert False, "Should have raised HTTPException"
        except Exception:
            pass


class TestUserCRUD:
    def test_create_user(self, setup_test_db):
        from common.auth import create_user
        user = create_user("testuser", "testpass123")
        assert user["username"] == "testuser"
        assert user["role"] == "user"
        assert "id" in user

    def test_create_duplicate_user_raises(self, setup_test_db):
        from common.auth import create_user
        create_user("unique_user", "password")
        try:
            create_user("unique_user", "another_password")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_authenticate_user_success(self, setup_test_db):
        from common.auth import create_user, authenticate_user
        create_user("auth_test_user", "correct_pass")
        token = authenticate_user("auth_test_user", "correct_pass")
        assert token is not None

    def test_authenticate_user_wrong_password(self, setup_test_db):
        from common.auth import create_user, authenticate_user
        create_user("auth_test_user2", "correct_pass")
        token = authenticate_user("auth_test_user2", "wrong_pass")
        assert token is None

    def test_login_user_success(self, setup_test_db):
        from common.auth import create_user, login_user
        create_user("login_test_user", "login_pass")
        result = login_user("login_test_user", "login_pass")
        assert "access_token" in result
        assert result["token_type"] == "bearer"

    def test_login_user_wrong_credentials(self, setup_test_db):
        from common.auth import login_user
        try:
            login_user("nonexistent", "wrong")
            assert False, "Should have raised HTTPException"
        except Exception:
            pass

    def test_register_user(self, setup_test_db):
        from common.auth import register_user
        result = register_user("new_user", "new_pass")
        # register_user 返回 login_user 结果：{access_token, token_type, user}
        assert "access_token" in result
        assert result["token_type"] == "bearer"
        assert result["user"]["username"] == "new_user"
