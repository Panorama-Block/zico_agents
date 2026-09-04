import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException


class ChatAuthContractTest(unittest.TestCase):
    def _load_auth_module(self):
        try:
            from src.security.chat_auth import (
                ChatAuthError,
                ChatAuthUnavailableError,
                PanoramaPrincipal,
                validate_bearer_token,
            )
        except ImportError as exc:
            self.fail(
                "CP-06 authentication module does not exist yet: "
                f"{exc}"
            )

        return (
            ChatAuthError,
            ChatAuthUnavailableError,
            PanoramaPrincipal,
            validate_bearer_token,
        )

    def test_valid_token_returns_verified_address_as_principal(self):
        (
            _,
            _,
            PanoramaPrincipal,
            validate_bearer_token,
        ) = self._load_auth_module()

        client = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "isValid": True,
            "payload": {
                "address": "0xAbCdEf1234567890",
                "sub": "caller-controlled-value-must-not-win",
            },
        }
        client.post.return_value = response

        principal = validate_bearer_token(
            "signed-token",
            auth_service_url="http://auth.local",
            client=client,
        )

        self.assertIsInstance(principal, PanoramaPrincipal)
        self.assertEqual(
            principal.user_id,
            "0xabcdef1234567890",
        )

        client.post.assert_called_once_with(
            "http://auth.local/auth/validate",
            json={"token": "signed-token"},
        )

    def test_invalid_token_is_rejected(self):
        (
            ChatAuthError,
            _,
            _,
            validate_bearer_token,
        ) = self._load_auth_module()

        client = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "isValid": False,
        }
        client.post.return_value = response

        with self.assertRaises(ChatAuthError):
            validate_bearer_token(
                "invalid-token",
                auth_service_url="http://auth.local",
                client=client,
            )

    def test_valid_response_without_address_is_rejected(self):
        (
            ChatAuthError,
            _,
            _,
            validate_bearer_token,
        ) = self._load_auth_module()

        client = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "isValid": True,
            "payload": {
                "sub": "0xnot-used-as-authority",
            },
        }
        client.post.return_value = response

        with self.assertRaises(ChatAuthError):
            validate_bearer_token(
                "signed-token",
                auth_service_url="http://auth.local",
                client=client,
            )

    def test_auth_service_failure_is_not_treated_as_invalid_user(self):
        (
            _,
            ChatAuthUnavailableError,
            _,
            validate_bearer_token,
        ) = self._load_auth_module()

        client = MagicMock()
        client.post.side_effect = RuntimeError("auth service unavailable")

        with self.assertRaises(ChatAuthUnavailableError):
            validate_bearer_token(
                "signed-token",
                auth_service_url="http://auth.local",
                client=client,
            )


class ChatAuthHttpContractTest(unittest.TestCase):
    def _load_dependency(self):
        try:
            from src.security.chat_auth import require_chat_principal
        except ImportError as exc:
            self.fail(
                "CP-06 authentication dependency does not exist yet: "
                f"{exc}"
            )
        return require_chat_principal

    def test_missing_authorization_header_returns_401(self):
        require_chat_principal = self._load_dependency()

        with self.assertRaises(HTTPException) as ctx:
            require_chat_principal(authorization=None)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_bearer_authorization_header_returns_401(self):
        require_chat_principal = self._load_dependency()

        with self.assertRaises(HTTPException) as ctx:
            require_chat_principal(
                authorization="Basic abc123"
            )

        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
