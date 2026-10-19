from __future__ import annotations

import json
import unittest

from models.species_repository import DATA_FILE
from routes.species import detail, index


class SpeciesApiTest(unittest.TestCase):
    def setUp(self):
        self.backup = DATA_FILE.read_bytes() if DATA_FILE.is_file() else None
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(
            json.dumps(
                {
                    "species": [
                        {
                            "id": "sp-test",
                            "name": "Test Starling",
                            "latin": "Testus birdus",
                            "knowledge": "A public knowledge entry.",
                            "level": "Endangered",
                            "region": "Bali",
                            "habitat": "Forest",
                            "population": "Small",
                            "threats": "Habitat loss",
                            "protectionMethods": "Habitat protection",
                            "emoji": "TS",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        if self.backup is None:
            DATA_FILE.unlink(missing_ok=True)
        else:
            DATA_FILE.write_bytes(self.backup)

    def test_guest_can_view_species_list(self):
        status, body = index()
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["species"][0]["id"], "sp-test")

    def test_guest_can_view_species_detail(self):
        status, body = detail("sp-test")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["species"]["name"], "Test Starling")

    def test_missing_species_returns_not_found(self):
        status, body = detail("missing")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

    def test_empty_species_list_is_supported(self):
        DATA_FILE.write_text(json.dumps({"species": []}), encoding="utf-8")
        status, body = index()
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["species"], [])

    def test_database_read_failure_returns_error(self):
        DATA_FILE.write_text("{not-json", encoding="utf-8")
        status, body = index()
        self.assertEqual(status, 500)
        self.assertEqual(body["error"]["code"], "DATA_ERROR")


if __name__ == "__main__":
    unittest.main()
