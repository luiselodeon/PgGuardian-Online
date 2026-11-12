import base64
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from argon2 import Type
from fastapi import HTTPException, Response
import psycopg2
from pydantic import ValidationError

from api.auth import get_current_user
from api.main import app
from api.routers.auth import (
    change_password,
    login_user,
    logout_user,
    register_user,
)
from api.schemas import PasswordChangeRequest, UserLoginRequest, UserRegisterRequest
from security.hashing import PASSWORD_HASHER, hash_password, verify_password
from security.password_policy import (
    MIN_COMMON_PASSWORD_ENTRIES,
    is_common_password,
    load_common_passwords,
)
from security.sessions import SESSION_COOKIE_NAME
from services.user_store import EmailAlreadyExistsError


def _b64_unpadded_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.b64decode(segment + padding)


class Argon2HashingTests(unittest.TestCase):
    def test_argon2id_owasp_parameters(self):
        self.assertEqual(PASSWORD_HASHER.type, Type.ID)
        self.assertEqual(PASSWORD_HASHER.time_cost, 2)
        self.assertEqual(PASSWORD_HASHER.memory_cost, 19456)
        self.assertEqual(PASSWORD_HASHER.parallelism, 1)
        self.assertEqual(PASSWORD_HASHER.salt_len, 16)

    def test_hash_format_random_salt_and_ca04_no_plaintext(self):
        secret = "GuardiaPostgres#2026!"
        hashed_a = hash_password(secret)
        hashed_b = hash_password(secret)

        self.assertTrue(hashed_a.startswith("$argon2id$v=19$m=19456,t=2,p=1$"))
        self.assertNotEqual(hashed_a, hashed_b)
        self.assertNotIn(secret, hashed_a)
        self.assertNotIn("GuardiaPostgres", hashed_a)

        parts = hashed_a.split("$")
        # ['', 'argon2id', 'v=19', 'm=19456,t=2,p=1', '<salt>', '<digest>']
        self.assertEqual(len(parts), 6)
        self.assertEqual(len(_b64_unpadded_decode(parts[4])), 16)

    def test_verify_password_accepts_valid_and_rejects_invalid_or_fast_hashes(self):
        secret = "ClaveSeguraPgGuardian!99"
        hashed = hash_password(secret)

        self.assertTrue(verify_password(secret, hashed))
        self.assertFalse(verify_password("ClaveIncorrecta!99", hashed))
        self.assertFalse(verify_password(secret, "$2b$12$invalidbcryptformat"))
        self.assertFalse(verify_password(secret, "e10adc3949ba59abbe56e057f20f883e"))
        self.assertFalse(verify_password("", hashed))


class PasswordPolicyTests(unittest.TestCase):
    def test_common_password_dataset_has_at_least_10k_entries(self):
        common = load_common_passwords()
        self.assertGreaterEqual(len(common), MIN_COMMON_PASSWORD_ENTRIES)
        self.assertTrue(is_common_password("123456789012"))
        self.assertTrue(is_common_password("Password1234"))
        self.assertTrue(is_common_password("QWERTY123456"))

    def test_rejects_short_or_overlong_passwords(self):
        with self.assertRaises(ValidationError) as short_ctx:
            UserRegisterRequest(
                name="Ana",
                email="ana@ejemplo.mx",
                password="Corto123456",
                password_confirm="Corto123456",
            )
        self.assertIn("entre 12 y 128", str(short_ctx.exception))

        too_long = "X" * 129
        with self.assertRaises(ValidationError) as long_ctx:
            UserRegisterRequest(
                name="Ana",
                email="ana@ejemplo.mx",
                password=too_long,
                password_confirm=too_long,
            )
        self.assertIn("entre 12 y 128", str(long_ctx.exception))

    def test_rejects_mismatch_and_whitespace_only(self):
        with self.assertRaises(ValidationError) as mismatch_ctx:
            UserRegisterRequest(
                name="Ana",
                email="ana@ejemplo.mx",
                password="MiClaveSegura#2026",
                password_confirm="OtraClaveSegura#2026",
            )
        self.assertIn("no coinciden", str(mismatch_ctx.exception))

        with self.assertRaises(ValidationError):
            UserRegisterRequest(
                name="Ana",
                email="ana@ejemplo.mx",
                password="            ",
                password_confirm="            ",
            )

    def test_rejects_email_or_local_part_case_insensitive(self):
        with self.assertRaises(ValidationError) as local_ctx:
            UserRegisterRequest(
                name="Luis",
                email="Luis.Arias@Ejemplo.MX",
                password="SuperLUIS.ARIAS#2026",
                password_confirm="SuperLUIS.ARIAS#2026",
            )
        self.assertIn("correo electrónico", str(local_ctx.exception))

    def test_rejects_common_password_of_valid_length(self):
        with self.assertRaises(ValidationError) as common_ctx:
            UserRegisterRequest(
                name="Luis",
                email="luis@ejemplo.mx",
                password="Password1234",
                password_confirm="Password1234",
            )
        self.assertIn("común", str(common_ctx.exception))


class RegisterEndpointTests(unittest.TestCase):
    def test_register_success_normalizes_email_and_stores_argon2id(self):
        payload = UserRegisterRequest(
            name="  María Pérez  ",
            email="  Maria.Perez@Empresa.COM ",
            password="Tr0pical!Sunset#2026",
            password_confirm="Tr0pical!Sunset#2026",
        )
        created_at = datetime.now(timezone.utc)
        uid = str(uuid4())
        captured = {}

        def _fake_create_user(*, name, email, password_hash):
            captured["name"] = name
            captured["email"] = email
            captured["password_hash"] = password_hash
            return {
                "id": uid,
                "name": name,
                "email": email,
                "created_at": created_at,
                "updated_at": created_at,
            }

        sid = str(uuid4())
        response = Response()
        with (
            patch("api.routers.auth.get_user_by_email", return_value=None) as mock_lookup,
            patch("api.routers.auth.create_user", side_effect=_fake_create_user),
            patch(
                "api.routers.auth.create_session",
                return_value={"id": sid, "user_id": uid, "expires_at": created_at},
            ),
        ):
            res = register_user(payload, response=response)

        mock_lookup.assert_called_once_with("maria.perez@empresa.com")
        self.assertEqual(captured["name"], "María Pérez")
        self.assertEqual(captured["email"], "maria.perez@empresa.com")
        self.assertTrue(captured["password_hash"].startswith("$argon2id$"))
        self.assertNotIn("Tr0pical!Sunset#2026", captured["password_hash"])
        self.assertTrue(verify_password("Tr0pical!Sunset#2026", captured["password_hash"]))

        self.assertEqual(res.id, uid)
        self.assertEqual(res.email, "maria.perez@empresa.com")
        self.assertFalse(hasattr(res, "password_hash"))
        set_cookie_header = response.headers.get("set-cookie", "")
        self.assertIn(f"{SESSION_COOKIE_NAME}=", set_cookie_header)
        self.assertIn("HttpOnly", set_cookie_header)

    def test_register_rejects_duplicate_email_with_409(self):
        payload = UserRegisterRequest(
            name="María",
            email="maria@ejemplo.mx",
            password="Tr0pical!Sunset#2026",
            password_confirm="Tr0pical!Sunset#2026",
        )
        with (
            patch("api.routers.auth.get_user_by_email", return_value={"id": "123"}),
            patch("api.routers.auth.hash_password") as mock_hash,
        ):
            with self.assertRaises(HTTPException) as ctx:
                register_user(payload, response=Response())
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("registrado", ctx.exception.detail)
        mock_hash.assert_not_called()

    def test_register_handles_race_condition_unique_violation_with_409(self):
        payload = UserRegisterRequest(
            name="María",
            email="maria@ejemplo.mx",
            password="Tr0pical!Sunset#2026",
            password_confirm="Tr0pical!Sunset#2026",
        )
        with (
            patch("api.routers.auth.get_user_by_email", return_value=None),
            patch(
                "api.routers.auth.create_user",
                side_effect=EmailAlreadyExistsError("Este correo electrónico ya está registrado."),
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                register_user(payload, response=Response())
        self.assertEqual(ctx.exception.status_code, 409)

    def test_register_returns_503_on_database_error(self):
        payload = UserRegisterRequest(
            name="María",
            email="maria@ejemplo.mx",
            password="Tr0pical!Sunset#2026",
            password_confirm="Tr0pical!Sunset#2026",
        )
        with patch(
            "api.routers.auth.get_user_by_email",
            side_effect=psycopg2.OperationalError("connection refused"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                register_user(payload, response=Response())
        self.assertEqual(ctx.exception.status_code, 503)


class LoginLogoutLockoutAndProtectionTests(unittest.TestCase):
    def test_login_generic_error_and_sixth_attempt_locked_15_min(self):
        uid = str(uuid4())
        valid_hash = hash_password("ClaveUnica!PgGuardian#99")
        attempts_state = {"count": 0, "locked_until": None}

        def _fake_get_user(_email):
            return {
                "id": uid,
                "name": "Luis",
                "email": "luis@ejemplo.mx",
                "password_hash": valid_hash,
                "failed_login_attempts": attempts_state["count"],
                "locked_until": attempts_state["locked_until"],
            }

        def _fake_record_fail(_uid, max_attempts=5, lock_minutes=15):
            attempts_state["count"] += 1
            if attempts_state["count"] >= max_attempts:
                attempts_state["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
            return attempts_state["count"], attempts_state["locked_until"]

        bad_payload = UserLoginRequest(email="luis@ejemplo.mx", password="ClaveIncorrecta#1234")
        with (
            patch("api.routers.auth.get_user_by_email", side_effect=_fake_get_user),
            patch("api.routers.auth.record_failed_login", side_effect=_fake_record_fail),
        ):
            for _ in range(5):
                with self.assertRaises(HTTPException) as err_ctx:
                    login_user(bad_payload, response=Response())
                self.assertEqual(err_ctx.exception.status_code, 401)
                self.assertEqual(err_ctx.exception.detail, "Credenciales inválidas.")

            # CA-05: 6to intento bloqueado 15 min
            with self.assertRaises(HTTPException) as locked_ctx:
                login_user(bad_payload, response=Response())
            self.assertEqual(locked_ctx.exception.status_code, 429)
            self.assertIn("bloqueada", locked_ctx.exception.detail.lower())
            self.assertIsNotNone(locked_ctx.exception.headers.get("Retry-After"))

        # Correo inexistente devuelve el mismo error genérico 401
        with patch("api.routers.auth.get_user_by_email", return_value=None):
            with self.assertRaises(HTTPException) as unknown_ctx:
                login_user(bad_payload, response=Response())
            self.assertEqual(unknown_ctx.exception.status_code, 401)
            self.assertEqual(unknown_ctx.exception.detail, "Credenciales inválidas.")

    def test_login_success_resets_failures_and_sets_session_cookie(self):
        uid = str(uuid4())
        sid = str(uuid4())
        valid_hash = hash_password("ClaveUnica!PgGuardian#99")
        user_row = {
            "id": uid,
            "name": "Luis",
            "email": "luis@ejemplo.mx",
            "password_hash": valid_hash,
            "failed_login_attempts": 3,
            "locked_until": None,
        }
        response = Response()
        payload = UserLoginRequest(email="LUIS@ejemplo.mx", password="ClaveUnica!PgGuardian#99")

        with (
            patch("api.routers.auth.get_user_by_email", return_value=user_row),
            patch("api.routers.auth.reset_failed_logins") as mock_reset,
            patch(
                "api.routers.auth.create_session",
                return_value={"id": sid, "user_id": uid, "expires_at": datetime.now(timezone.utc)},
            ),
        ):
            res = login_user(payload, response=response)

        mock_reset.assert_called_once_with(uid)
        self.assertEqual(res.user.email, "luis@ejemplo.mx")
        self.assertIn(f"{SESSION_COOKIE_NAME}=", response.headers.get("set-cookie", ""))

    def test_logout_revokes_session_and_clears_cookie(self):
        sid = str(uuid4())
        response = Response()
        with patch("api.routers.auth.revoke_session") as mock_revoke:
            res = logout_user(
                response=response,
                current_user={"id": str(uuid4()), "name": "Luis", "email": "luis@ejemplo.mx", "session_id": sid},
            )
        mock_revoke.assert_called_once_with(sid)
        self.assertIn("Max-Age=0", response.headers.get("set-cookie", ""))
        self.assertIn("cerrada", res.message.lower())

    def test_change_password_verifies_current_hashes_argon2id_and_revokes_other_sessions(self):
        uid = str(uuid4())
        sid = str(uuid4())
        old_hash = hash_password("ClaveAnterior!Pg2026")
        current_user = {"id": uid, "name": "Luis", "email": "luis@ejemplo.mx", "session_id": sid}
        captured = {}

        def _fake_update(user_id, new_hash):
            captured["user_id"] = user_id
            captured["new_hash"] = new_hash

        with patch(
            "api.routers.auth.get_user_with_hash_by_id",
            return_value={"id": uid, "name": "Luis", "email": "luis@ejemplo.mx", "password_hash": old_hash},
        ):
            with self.assertRaises(HTTPException) as bad_ctx:
                change_password(
                    PasswordChangeRequest(
                        current_password="Incorrecta#Password",
                        new_password="NuevaClaveSegura!2026",
                        new_password_confirm="NuevaClaveSegura!2026",
                    ),
                    current_user=current_user,
                )
            self.assertEqual(bad_ctx.exception.status_code, 401)

            with (
                patch("api.routers.auth.update_user_password", side_effect=_fake_update),
                patch("api.routers.auth.revoke_other_sessions", return_value=2) as mock_revoke_others,
            ):
                res = change_password(
                    PasswordChangeRequest(
                        current_password="ClaveAnterior!Pg2026",
                        new_password="NuevaClaveSegura!2026",
                        new_password_confirm="NuevaClaveSegura!2026",
                    ),
                    current_user=current_user,
                )

        self.assertTrue(captured["new_hash"].startswith("$argon2id$"))
        self.assertTrue(verify_password("NuevaClaveSegura!2026", captured["new_hash"]))
        mock_revoke_others.assert_called_once_with(uid, sid)
        self.assertEqual(res.revoked_sessions, 2)

    def test_api_routes_enforce_session_except_register_login_and_health_check(self):
        def _collect_dependant_calls(dependant):
            calls = set()
            if dependant is None:
                return calls
            for sub in getattr(dependant, "dependencies", []):
                if getattr(sub, "call", None) is not None:
                    calls.add(sub.call)
                calls.update(_collect_dependant_calls(sub))
            return calls

        public_paths = {"/api/auth/register", "/api/auth/login", "/api/health-check"}
        protected_paths_checked = 0
        for route in app.routes:
            path = getattr(route, "path", "")
            if not path.startswith("/api/"):
                continue
            dep_calls = {d.dependency for d in getattr(route, "dependencies", []) if getattr(d, "dependency", None)}
            dep_calls.update(_collect_dependant_calls(getattr(route, "dependant", None)))
            if path in public_paths:
                self.assertNotIn(get_current_user, dep_calls, f"{path} debe ser público")
            else:
                protected_paths_checked += 1
                self.assertIn(get_current_user, dep_calls, f"{path} debe exigir sesión activa (RF-02.5 / CA-06)")
        self.assertGreater(protected_paths_checked, 10)

