import unittest

from fastapi.testclient import TestClient

from api.database import get_connection
from api.main import app


def _failing_connection():
    raise RuntimeError("TiendaDB no disponible")


class FullScanAuthTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_connection] = _failing_connection
        # Sin `with`: no se ejecuta el lifespan (no inicializa app_db).
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.pop(get_connection, None)

    def test_full_scan_sin_cookie_responde_401_aunque_get_connection_falle(self):
        response = self.client.get("/api/full-scan")

        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()