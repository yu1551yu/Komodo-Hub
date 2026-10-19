from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, read_rows, write_rows
from services.creative_canvas_service import add_items, candidates, canvas_item, my_canvas, remove_item, reorder


FILES = [
    "creative_canvas_items.json",
    "community_contributions.json",
    "species_sightings.json",
    "komodo_hub.json",
    "conservation_programs.json",
]


class CreativeCanvasTest(unittest.TestCase):
    def setUp(self):
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None for name in FILES}
        write_rows("creative_canvas_items.json", [])
        write_rows("community_contributions.json", [
            {"id": "c1", "authorId": "u1", "organisationId": "org1", "title": "Mangrove notes", "body": "Original article", "type": "article", "status": "published", "programId": "p1", "createdAt": "2026-10-10T10:00:00Z"},
            {"id": "c2", "authorId": "u2", "organisationId": "org1", "title": "Other work", "body": "Private owner", "type": "essay", "status": "published", "createdAt": "2026-10-10T09:00:00Z"},
        ])
        write_rows("species_sightings.json", [
            {"id": "s1", "authorId": "u1", "speciesId": "sp1", "notes": "Coastal observation", "observedAt": "2026-10-09", "publicPlace": "North coast", "preciseLocation": "SECRET", "visibility": "private", "createdAt": "2026-10-10T11:00:00Z"},
        ])
        write_rows("conservation_programs.json", [
            {"id": "p1", "title": "Mangrove Recovery", "summary": "Restore coastal habitat", "status": "published"},
        ])
        (DATA_DIR / "komodo_hub.json").write_text('{"species":[{"id":"sp1","name":"Bali Starling","image":"BS"}]}', encoding="utf-8")

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)

    def test_candidates_only_include_the_owners_work(self):
        result = candidates("u1")
        self.assertEqual({item["id"] for item in result["items"]}, {"c1", "s1"})
        self.assertNotIn("SECRET", str(result))

    def test_batch_add_is_persistent_and_duplicate_safe(self):
        payload = {"items": [{"resourceType": "contribution", "resourceId": "c1"}, {"resourceType": "sighting", "resourceId": "s1"}]}
        first = add_items("u1", payload)
        second = add_items("u1", payload)
        self.assertEqual(len(first["added"]), 2)
        self.assertEqual(len(second["added"]), 0)
        self.assertEqual(len(my_canvas("u1")["items"]), 2)
        self.assertEqual(len(read_rows("creative_canvas_items.json")), 2)

    def test_remove_only_deletes_reference(self):
        result = add_items("u1", {"items": [{"resourceType": "contribution", "resourceId": "c1"}]})
        remove_item("u1", result["added"][0]["id"])
        self.assertEqual(my_canvas("u1")["items"], [])
        self.assertIsNotNone(next((row for row in read_rows("community_contributions.json") if row["id"] == "c1"), None))

    def test_reorder_persists_and_rejects_foreign_ids(self):
        result = add_items("u1", {"items": [{"resourceType": "contribution", "resourceId": "c1"}, {"resourceType": "sighting", "resourceId": "s1"}]})
        ids = [item["id"] for item in result["items"]]
        reordered = reorder("u1", {"itemIds": list(reversed(ids))})
        self.assertEqual([item["id"] for item in reordered["items"]], list(reversed(ids)))
        self.assertEqual([item["id"] for item in my_canvas("u1")["items"]], list(reversed(ids)))
        with self.assertRaisesRegex(ValueError, "INVALID_ORDER"):
            reorder("u1", {"itemIds": [ids[0], "foreign"]})

    def test_another_user_cannot_add_or_read_the_item(self):
        result = add_items("u1", {"items": [{"resourceType": "contribution", "resourceId": "c1"}]})
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            add_items("u2", {"items": [{"resourceType": "contribution", "resourceId": "c1"}]})
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            canvas_item("u2", result["added"][0]["id"])


if __name__ == "__main__":
    unittest.main()
