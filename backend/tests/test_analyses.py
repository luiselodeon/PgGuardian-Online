import io
import unittest

from fastapi import HTTPException, UploadFile

from api.routers.analyses import (
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_SIZE_BYTES,
    create_analysis,
)


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content))


class AnalysesEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_single_sql_file(self):
        res = await create_analysis(
            files=[_upload("01_schema.sql", "-- Esquema con acentos áéíóúñ\nCREATE TABLE t(id int);\n".encode("utf-8"))],
            order=None,
        )
        self.assertEqual(res.status, "validado")
        self.assertEqual(res.file_count, 1)
        self.assertEqual(res.files[0].order, 1)
        self.assertEqual(res.files[0].filename, "01_schema.sql")
        self.assertEqual(res.files[0].encoding, "utf-8")
        self.assertEqual(res.files[0].line_count, 2)

    async def test_valid_reordered_multiple_files(self):
        files = [
            _upload("02_seed.sql", b"INSERT INTO t VALUES (1);"),
            _upload("03_idx.sql", b"CREATE INDEX idx_t ON t(id);"),
            _upload("01_schema.sql", b"CREATE TABLE t(id int);"),
        ]
        res = await create_analysis(files=files, order="[2, 0, 1]")
        self.assertEqual(res.file_count, 3)
        self.assertEqual(
            [(f.order, f.filename) for f in res.files],
            [(1, "01_schema.sql"), (2, "02_seed.sql"), (3, "03_idx.sql")],
        )

    async def test_rejects_empty_file_list(self):
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=[], order=None)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_more_than_five_files(self):
        files = [_upload(f"s{i}.sql", b"SELECT 1;") for i in range(6)]
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=files, order=None)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_invalid_extensions(self):
        for bad_name in ("script.txt", "schema.sql.bak", ".sql"):
            with self.assertRaises(HTTPException) as ctx:
                await create_analysis(files=[_upload(bad_name, b"SELECT 1;")], order=None)
            self.assertEqual(ctx.exception.status_code, 422)

    async def test_rejects_invalid_utf8(self):
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=[_upload("latin1.sql", b"SELECT '\xff\xfe';")], order=None)
        self.assertEqual(ctx.exception.status_code, 422)

    async def test_rejects_single_file_over_10mb(self):
        oversized = b"a" * (MAX_FILE_SIZE_BYTES + 1)
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=[_upload("big.sql", oversized)], order=None)
        self.assertEqual(ctx.exception.status_code, 413)

    async def test_rejects_combined_size_over_25mb(self):
        nine_mb = b"a" * (9 * 1024 * 1024)
        files = [_upload(f"p{i}.sql", nine_mb) for i in range(3)]  # 27 MB total
        self.assertGreater(len(files) * len(nine_mb), MAX_TOTAL_SIZE_BYTES)
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=files, order=None)
        self.assertEqual(ctx.exception.status_code, 413)

    async def test_rejects_invalid_order_parameter(self):
        files = [_upload("a.sql", b"SELECT 1;"), _upload("b.sql", b"SELECT 2;")]
        for bad_order in ("not-json", "[0]", "[0, 0]", "[0, 2]", "[true, false]"):
            with self.assertRaises(HTTPException) as ctx:
                await create_analysis(files=files, order=bad_order)
            self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
