import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_quest_source_to_paratranz as quest_sync


class FakeClient:
    def __init__(self) -> None:
        self.files = {
            20208: [{"id": 10, "name": "CTNH/en_us.json", "total": 3}],
            20209: [],
        }
        self.uploads: list[tuple[int, str, str, int | None, int]] = []

    def get_files(self, project_id: int) -> list[dict]:
        return self.files[project_id]

    def upload_file(self, project_id, filename, content, path, file_id=None):
        self.uploads.append((project_id, filename, path, file_id, len(content)))
        if file_id is not None:
            return {"status": "hashMatched"}
        return {"file": {"total": 3}}


class FindQuestFileTests(unittest.TestCase):
    def test_finds_exact_ctnh_locale_file(self) -> None:
        files = [
            {"id": 1, "name": "CTNHCore/en_us.json"},
            {"id": 2, "name": "CTNH/en_us.json"},
        ]

        self.assertEqual(quest_sync.find_quest_file(files, "en_us")["id"], 2)

    def test_missing_locale_returns_none(self) -> None:
        files = [{"id": 2, "name": "CTNH/en_us.json"}]

        self.assertIsNone(quest_sync.find_quest_file(files, "ja_jp"))


class SyncQuestSourceTests(unittest.TestCase):
    def test_updates_existing_file_and_creates_missing(self) -> None:
        client = FakeClient()
        zh = {"ctnh.a.title": "A", "ctnh.b.title": "B", "ctnh.c.title": "C"}

        reports = quest_sync.sync_quest_source(
            client,
            [
                {"locale": "en_us", "project_id": 20208},
                {"locale": "ja_jp", "project_id": 20209},
            ],
            zh,
        )

        self.assertEqual(len(client.uploads), 2)
        project_id, filename, path, file_id, size = client.uploads[0]
        self.assertEqual((project_id, filename, path, file_id), (20208, "en_us.json", "CTNH", 10))
        self.assertGreater(size, 0)
        self.assertIn("unchanged (hash matched)", reports[0])
        self.assertIsNone(client.uploads[1][3])
        self.assertIn("created (3 entries)", reports[1])

    def test_dry_run_does_not_upload(self) -> None:
        client = FakeClient()

        reports = quest_sync.sync_quest_source(
            client,
            [{"locale": "en_us", "project_id": 20208}],
            {"a": "b"},
            dry_run=True,
        )

        self.assertEqual(client.uploads, [])
        self.assertIn("[dry-run]", reports[0])


if __name__ == "__main__":
    unittest.main()
