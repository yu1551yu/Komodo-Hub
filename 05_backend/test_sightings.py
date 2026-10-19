from __future__ import annotations

import unittest

from models.json_store import DATA_DIR, write_rows
from models.work_repository import list_rows
from routes import sightings
from services.sighting_service import community_sightings, create, my_sightings, public_sightings, sighting_detail

FILES = ["users.json", "community_organisations.json", "community_memberships.json", "species_sightings.json", "komodo_hub.json"]


class GuestHandler:
    headers = {}


class SightingsTest(unittest.TestCase):
    def setUp(self):
        self.backup = {name: (DATA_DIR / name).read_bytes() if (DATA_DIR / name).is_file() else None for name in FILES}
        write_rows("users.json", [
            {"id": "member1", "name": "Member One", "email": "member@example.test", "role": "PUBLIC"},
            {"id": "other1", "name": "Other One", "email": "other@example.test", "role": "PUBLIC"},
        ])
        write_rows("community_organisations.json", [
            {"id": "org1", "name": "Org One", "status": "approved"},
            {"id": "org2", "name": "Org Two", "status": "approved"},
        ])
        write_rows("community_memberships.json", [
            {"id": "mem1", "organisationId": "org1", "userId": "member1", "role": "MEMBER", "status": "active"},
        ])
        write_rows("species_sightings.json", [])
        (DATA_DIR / "komodo_hub.json").write_text(
            '{"species":[{"id":"sp1","name":"Test Dragon","latin":"Varanus test","knowledge":"Test species"}]}',
            encoding="utf-8",
        )

    def tearDown(self):
        for name, data in self.backup.items():
            path = DATA_DIR / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)

    def _body(self, **patch):
        body = {
            "speciesId": "sp1",
            "notes": "Observed one animal moving near the forest edge.",
            "observedAt": "2026-10-09T09:30",
            "publicPlace": "West district",
            "preciseLocation": "-8.123, 119.456 near nesting site",
            "visibility": "public",
        }
        body.update(patch)
        return body

    def test_authenticated_user_can_save_and_read_report(self):
        result = create({"id": "member1"}, self._body())
        saved = list_rows("species_sightings.json")[0]
        self.assertEqual(saved["authorId"], "member1")
        self.assertEqual(saved["verificationStatus"], "unverified")
        self.assertEqual(my_sightings({"id": "member1"})["sightings"][0]["preciseLocation"], saved["preciseLocation"])
        self.assertEqual(sighting_detail(result["sighting"]["id"])["sighting"]["species"]["id"], "sp1")
        self.assertIsNone(result["sighting"]["community"])
        self.assertIsNone(result["sighting"]["libraryStatus"])

    def test_guest_cannot_submit(self):
        status, body = sightings.post(GuestHandler(), self._body())
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "UNAUTHORIZED")

    def test_invalid_species_and_foreign_community_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SPECIES"):
            create({"id": "member1"}, self._body(speciesId="missing"))
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            create({"id": "member1"}, self._body(organisationId="org2"))

    def test_community_report_is_linked_and_requires_membership(self):
        result = create({"id": "member1"}, self._body(organisationId="org1", visibility="community"))
        rows = community_sightings({"id": "member1"}, "org1")["sightings"]
        self.assertEqual(rows[0]["id"], result["sighting"]["id"])
        self.assertEqual(rows[0]["community"]["id"], "org1")
        with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
            community_sightings({"id": "other1"}, "org1")

    def test_public_api_omits_sensitive_and_private_fields(self):
        create({"id": "member1"}, self._body(authorId="other1"))
        public = public_sightings()["sightings"][0]
        self.assertNotIn("preciseLocation", public)
        self.assertNotIn("id", public["author"])
        self.assertNotIn("email", public["author"])
        self.assertEqual(public["verificationStatus"], "unverified")

    def test_private_reports_are_not_public(self):
        result = create({"id": "member1"}, self._body(visibility="private"))
        self.assertEqual(public_sightings()["sightings"], [])
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            sighting_detail(result["sighting"]["id"])


if __name__ == "__main__":
    unittest.main()
