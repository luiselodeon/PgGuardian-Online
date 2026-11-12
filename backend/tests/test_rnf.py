import asyncio
import time
import unittest
from unittest.mock import patch

from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from api.main import enforce_auth_rate_limit, spanish_validation_exception_handler
from security.rate_limit import SlidingWindowRateLimiter, auth_rate_limiter
from services.sql_validator import validate_sql_script


def _make_request(method: str, path: str, client_ip: str = "198.51.100.10") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "client": (client_ip, 54321),
    }
    return Request(scope)


class RnfSecurityAndQualityTests(unittest.TestCase):
    def setUp(self):
        auth_rate_limiter.reset()

    def tearDown(self):
        auth_rate_limiter.reset()

    def test_rnf02_rate_limiter_allows_10_per_minute_and_blocks_11th_per_ip(self):
        limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
        for idx in range(10):
            allowed, retry_after = limiter.check("/api/auth/login", "203.0.113.5")
            self.assertTrue(allowed, f"Petición {idx + 1} debería permitirse")
            self.assertEqual(retry_after, 0)

        allowed_11, retry_after_11 = limiter.check("/api/auth/login", "203.0.113.5")
        self.assertFalse(allowed_11)
        self.assertGreaterEqual(retry_after_11, 1)

        # Otra IP y otra ruta mantienen su propio cupo independiente
        self.assertTrue(limiter.check("/api/auth/login", "203.0.113.6")[0])
        self.assertTrue(limiter.check("/api/auth/register", "203.0.113.5")[0])

    def test_rnf02_middleware_returns_429_in_spanish_on_11th_auth_post(self):
        async def _ok_next(_req):
            from fastapi.responses import JSONResponse
            return JSONResponse({"ok": True}, status_code=200)

        async def _run():
            for _ in range(10):
                res = await enforce_auth_rate_limit(_make_request("POST", "/api/auth/register", "192.0.2.1"), _ok_next)
                self.assertEqual(res.status_code, 200)
            blocked = await enforce_auth_rate_limit(_make_request("POST", "/api/auth/register", "192.0.2.1"), _ok_next)
            self.assertEqual(blocked.status_code, 429)
            self.assertIn("Máximo 10 solicitudes por minuto", blocked.body.decode("utf-8"))
            self.assertIsNotNone(blocked.headers.get("Retry-After"))

        asyncio.run(_run())

    def test_rnf02_sliding_window_recovers_after_60_seconds(self):
        limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
        fake_now = [1000.0]
        with patch("security.rate_limit.time.monotonic", side_effect=lambda: fake_now[0]):
            for _ in range(10):
                self.assertTrue(limiter.check("/api/auth/login", "198.51.100.2")[0])
            self.assertFalse(limiter.check("/api/auth/login", "198.51.100.2")[0])
            fake_now[0] += 60.1
            self.assertTrue(limiter.check("/api/auth/login", "198.51.100.2")[0])

    def test_rnf03_incremental_ast_location_preserves_exact_lines_and_linear_speed(self):
        lines = [
            "-- comentario inicial",
            "CREATE TABLE t0 (id INT PRIMARY KEY);",
        ]
        for i in range(1, 500):
            lines.append(f"-- comentario {i}")
            lines.append(f"INSERT INTO t0 (id) VALUES ({i});")
        sql_text = "\n".join(lines) + "\n"

        t0 = time.perf_counter()
        stmts = validate_sql_script("bulk.sql", sql_text)
        elapsed = time.perf_counter() - t0

        self.assertEqual(len(stmts), 500)
        self.assertEqual(stmts[0].line, 2)
        self.assertEqual(stmts[1].line, 4)
        self.assertEqual(stmts[-1].line, 1000)
        self.assertLess(elapsed, 2.0)

    def test_rnf04_validation_exception_handler_translates_missing_field_to_spanish(self):
        exc = RequestValidationError(
            [{"type": "missing", "loc": ("body", "email"), "msg": "Field required"}]
        )
        res = asyncio.run(spanish_validation_exception_handler(_make_request("POST", "/api/auth/login"), exc))
        self.assertEqual(res.status_code, 422)
        body = res.body.decode("utf-8")
        self.assertIn("Este campo es obligatorio.", body)
        self.assertNotIn("Field required", body)

