from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

from api.auth import get_current_user, get_current_user_id
from api.routers.analyses import (
    delete_analysis,
    get_analysis_detail,
    list_analyses,
)
from security.sessions import create_access_token
from services.analysis_store import (
    _SCHEMA_DDL,
    delete_analysis_for_user,
    get_analysis_for_user,
    list_analyses_for_user,
)
from services.sandbox_cleanup import cleanup_expired_sandboxes


class AnalysesLifecycleAndIsolationTests(unittest.IsolatedAsyncioTestCase):
    def test_auth_dependency_requires_valid_user_id(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(session_cookie=None, authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(session_cookie="token-invalido", authorization=None)
        self.assertEqual(ctx.exception.status_code, 401)

        uid = str(uuid4())
        sid = str(uuid4())
        token = create_access_token(
            user_id=uid,
            session_id=sid,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with patch("api.auth.get_active_session_user", return_value=None):
            with self.assertRaises(HTTPException) as revoked_ctx:
                get_current_user(session_cookie=token, authorization=None)
            self.assertEqual(revoked_ctx.exception.status_code, 401)

        user_row = {"id": uid, "name": "Ana", "email": "ana@ejemplo.mx", "session_id": sid}
        with patch("api.auth.get_active_session_user", return_value=user_row):
            self.assertEqual(get_current_user(session_cookie=token, authorization=None), user_row)
            self.assertEqual(get_current_user(session_cookie=None, authorization=f"Bearer {token}"), user_row)
            self.assertEqual(get_current_user_id(current_user=user_row), uid)

    async def test_list_analyses_filters_by_current_user(self):
        now = datetime.now(timezone.utc)
        sample_row = {
            "id": str(uuid4()),
            "user_id": "usuario_a",
            "name": "Esquema tienda",
            "status": "completado",
            "file_count": 1,
            "total_size_bytes": 120,
            "sandbox_db_name": "sandbox_abc",
            "sandbox_status": "destroyed",
            "sandbox_expires_at": now - timedelta(hours=1),
            "sandbox_destroyed_at": now,
            "executed_statements": 2,
            "execution_time_ms": 15,
            "health_score": 88,
            "total_findings": 2,
            "created_at": now - timedelta(hours=25),
        }
        with patch("api.routers.analyses.list_analyses_for_user", return_value=[sample_row]) as mock_list:
            res = await list_analyses(user_id="usuario_a")
        mock_list.assert_called_once_with("usuario_a")
        self.assertEqual(res.total, 1)
        self.assertEqual(res.items[0].sandbox_status, "destroyed")
        self.assertEqual(res.items[0].health_score, 88)

    async def test_get_analysis_returns_404_for_non_owner_and_preserves_destroyed_report(self):
        aid = str(uuid4())
        now = datetime.now(timezone.utc)
        destroyed_record = {
            "id": aid,
            "user_id": "usuario_a",
            "name": "Esquema histórico",
            "status": "completado",
            "message": "ok",
            "file_count": 1,
            "total_size_bytes": 100,
            "files": [
                {"order": 1, "filename": "s.sql", "size_bytes": 100, "encoding": "utf-8", "line_count": 4}
            ],
            "sandbox_db_name": "sandbox_gone",
            "sandbox_status": "destroyed",
            "sandbox_expires_at": now - timedelta(hours=2),
            "sandbox_destroyed_at": now - timedelta(hours=1),
            "executed_statements": 3,
            "execution_time_ms": 20,
            "scan": {
                "health_score": 90,
                "total_findings": 1,
                "categories": {},
                "executed_at": now.isoformat(),
                "is_sandbox": True,
                "evaluated_detectors": 13,
                "not_applicable_detectors": 9,
            },
            "created_at": now - timedelta(hours=26),
        }

        with patch(
            "api.routers.analyses.get_analysis_for_user",
            side_effect=lambda req_id, uid: destroyed_record if uid == "usuario_a" else None,
        ):
            # Dueño sigue consultando el reporte tras destruirse el sandbox
            detail = await get_analysis_detail(aid, user_id="usuario_a")
            self.assertEqual(detail.sandbox_status, "destroyed")
            self.assertEqual(detail.scan.health_score, 90)

            # CA-03: Usuario B recibe 404 al consultar análisis de Usuario A
            with self.assertRaises(HTTPException) as ctx:
                await get_analysis_detail(aid, user_id="usuario_b")
            self.assertEqual(ctx.exception.status_code, 404)

    async def test_delete_analysis_returns_404_for_non_owner_and_drops_active_sandbox(self):
        aid = str(uuid4())
        with (
            patch(
                "api.routers.analyses.delete_analysis_for_user",
                side_effect=lambda req_id, uid: (
                    {"id": req_id, "sandbox_db_name": "sandbox_active_1", "sandbox_status": "active"}
                    if uid == "usuario_a"
                    else None
                ),
            ),
            patch("api.routers.analyses.drop_sandbox_db") as mock_drop,
        ):
            with self.assertRaises(HTTPException) as ctx:
                await delete_analysis(aid, user_id="usuario_b")
            self.assertEqual(ctx.exception.status_code, 404)
            mock_drop.assert_not_called()

            res = await delete_analysis(aid, user_id="usuario_a")
            self.assertEqual(res.id, aid)
            mock_drop.assert_called_once_with("sandbox_active_1")

    def test_cleanup_expired_sandboxes_drops_expired_only_when_drop_succeeds(self):
        expired = [
            {"id": "11111111-1111-1111-1111-111111111111", "sandbox_db_name": "sandbox_old_1"},
            {"id": "22222222-2222-2222-2222-222222222222", "sandbox_db_name": "sandbox_old_2"},
        ]
        with (
            patch("services.sandbox_cleanup.find_expired_active_sandboxes", return_value=expired),
            patch("services.sandbox_cleanup.drop_sandbox_db", side_effect=[True, False]),
            patch("services.sandbox_cleanup.mark_sandbox_destroyed") as mock_mark,
        ):
            purged = cleanup_expired_sandboxes()

        self.assertEqual(purged, 1)
        mock_mark.assert_called_once_with("11111111-1111-1111-1111-111111111111")

    def test_analyses_schema_has_users_fk_and_store_guards_non_uuid_user(self):
        self.assertIn("user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE", _SCHEMA_DDL)
        self.assertEqual(list_analyses_for_user("no-es-uuid"), [])
        self.assertIsNone(get_analysis_for_user(str(uuid4()), "no-es-uuid"))
        self.assertIsNone(delete_analysis_for_user(str(uuid4()), "no-es-uuid"))


if __name__ == "__main__":
    unittest.main()

