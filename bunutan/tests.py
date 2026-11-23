import random
import os
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase

from . import draw
from .models import Event, Exclusion, Participant, Reveal


class DrawAlgorithmTests(TestCase):
    def test_simulations_with_random_exclusions_and_random_giver_order(self):
        for size in (3, 4, 5, 8, 12, 30):
            ids = list(range(1, size + 1))
            for run in range(500):
                rng = random.Random(size * 10000 + run)
                reference_receivers = ids[:]
                while True:
                    rng.shuffle(reference_receivers)
                    if all(giver != receiver for giver, receiver in zip(ids, reference_receivers)):
                        break
                reference = dict(zip(ids, reference_receivers))
                forbidden = {(person, person) for person in ids}
                possible_pairs = [
                    (a, b)
                    for a in ids
                    for b in ids
                    if a < b and reference[a] != b and reference[b] != a
                ]
                rng.shuffle(possible_pairs)
                for a, b in possible_pairs[: rng.randint(0, max(1, size // 8))]:
                    forbidden.add((a, b))
                    forbidden.add((b, a))

                giver_order = ids[:]
                rng.shuffle(giver_order)
                remaining_givers = ids[:]
                remaining_receivers = ids[:]
                result = {}
                for giver in giver_order:
                    receiver = draw.choose_receiver(
                        giver,
                        remaining_givers,
                        remaining_receivers,
                        forbidden,
                        rng=rng,
                        weight_completions=False,
                    )
                    result[giver] = receiver
                    remaining_givers.remove(giver)
                    remaining_receivers.remove(receiver)

                self.assertEqual(set(result), set(ids))
                self.assertEqual(set(result.values()), set(ids))
                for giver, receiver in result.items():
                    self.assertNotEqual(giver, receiver)
                    self.assertNotIn((giver, receiver), forbidden)

    def test_last_giver_with_only_one_remaining_receiver(self):
        self.assertEqual(draw.choose_receiver(7, [7], [3], {(7, 7)}), 3)

    def test_opening_graph_feasibility_and_deadlock_detection(self):
        self.assertTrue(draw.has_perfect_matching([1, 2, 3], [1, 2, 3], {(1, 1), (2, 2), (3, 3)}))
        impossible = {(1, 1), (1, 2), (1, 3), (2, 2), (3, 3)}
        self.assertFalse(draw.has_perfect_matching([1, 2, 3], [1, 2, 3], impossible))
        with self.assertRaises(draw.DrawDeadlock):
            draw.choose_receiver(1, [1, 2, 3], [1, 2, 3], impossible)

    def test_four_person_draws_are_roughly_uniform(self):
        ids = [1, 2, 3, 4]
        forbidden = {(person, person) for person in ids}
        rng = random.Random(81023)
        counts = Counter()
        for _ in range(3000):
            givers = ids[:]
            rng.shuffle(givers)
            remaining_givers = ids[:]
            remaining_receivers = ids[:]
            result = {}
            for giver in givers:
                receiver = draw.choose_receiver(
                    giver, remaining_givers, remaining_receivers, forbidden, rng=rng
                )
                result[giver] = receiver
                remaining_givers.remove(giver)
                remaining_receivers.remove(receiver)
            counts[tuple(result[giver] for giver in ids)] += 1
        self.assertEqual(len(counts), 9)
        self.assertGreater(min(counts.values()), 250)
        self.assertLess(max(counts.values()), 420)


class ApiAndPrivacyTests(TestCase):
    def setUp(self):
        cache.clear()
        # The application intentionally treats Event(pk=1) as its singleton.
        # PostgreSQL sequences don't roll back with TestCase transactions, so
        # pinning the fixture avoids later tests accidentally exercising a
        # different event after earlier cases consume sequence values.
        self.event = Event.objects.create(pk=1, year=2026, code="23456789A")
        self.people = [Participant.objects.create(event=self.event, name=name) for name in ("Ate Joy", "Kuya Migs", "Lola Nena")]
        self.client = Client()

    def set_member_session(self, participant=None):
        session = self.client.session
        session["code_ok"] = True
        if participant is None:
            session.pop("me", None)
        else:
            session["me"] = participant.pk
        session.save()

    def post_json(self, path, payload):
        import json

        return self.client.post(path, data=json.dumps(payload), content_type="application/json")

    def test_api_draw_requires_claim_and_open_event(self):
        self.set_member_session()
        response = self.post_json("/api/draw", {})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "not_claimed")

        self.set_member_session(self.people[0])
        response = self.post_json("/api/draw", {})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "not_open")

    def test_draw_is_single_use_and_key_decrypts_only_its_saved_pick(self):
        self.event.status = Event.Status.OPEN
        self.event.save(update_fields=("status",))
        self.set_member_session(self.people[0])
        response = self.post_json("/api/draw", {})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(set(result), {"ok", "name", "recovery_key"})
        self.assertIn(result["name"], {person.name for person in self.people})

        giver = Participant.objects.get(pk=self.people[0].pk)
        self.assertTrue(giver.has_drawn)
        self.assertIsNotNone(giver.sealed_pick)
        self.assertNotEqual(giver.sealed_pick, result["name"])
        self.assertEqual(Fernet(result["recovery_key"].encode()).decrypt(giver.sealed_pick.encode()).decode(), result["name"])

        second = self.post_json("/api/draw", {})
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["error"], "already_drawn")
        self.assertEqual(Participant.objects.filter(event=self.event, slip_taken=True).count(), 1)

        replay = self.post_json(
            "/api/my-pick",
            {"participant_id": self.people[0].pk, "recovery_key": result["recovery_key"]},
        )
        self.assertEqual(replay.json(), {"ok": True, "name": result["name"]})
        bad = self.post_json(
            "/api/my-pick", {"participant_id": self.people[0].pk, "recovery_key": "wrong"}
        )
        self.assertEqual(bad.status_code, 403)
        self.assertEqual(bad.json()["error"], "invalid_key")

    def test_recovery_key_attempts_are_rate_limited(self):
        self.event.status = Event.Status.OPEN
        self.event.save(update_fields=("status",))
        self.set_member_session(self.people[0])
        result = self.post_json("/api/draw", {}).json()
        payload = {"participant_id": self.people[0].pk, "recovery_key": "not-a-valid-fernet-key"}
        for _ in range(4):
            response = self.post_json("/api/my-pick", payload)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"], "invalid_key")
        response = self.post_json("/api/my-pick", payload)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "locked_out")
        self.assertGreater(int(response["Retry-After"]), 0)
        payload["recovery_key"] = result["recovery_key"]
        self.assertEqual(self.post_json("/api/my-pick", payload).status_code, 429)

    def test_code_normalization_and_five_attempt_lockout(self):
        response = self.post_json("/api/enter", {"code": " 2345-6789a "})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session.get("code_ok"))

        cache.clear()
        unicode_code = self.post_json("/api/enter", {"code": "😀12345678"})
        self.assertEqual(unicode_code.status_code, 403)
        cache.clear()
        for _ in range(4):
            response = self.post_json("/api/enter", {"code": "AAAAAAAAA"})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"], "bad_code")
        response = self.post_json("/api/enter", {"code": "AAAAAAAAA"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "locked_out")
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(self.post_json("/api/enter", {"code": self.event.code}).status_code, 429)

    def test_participant_endpoint_has_only_allowlisted_fields(self):
        self.set_member_session()
        response = self.client.get("/api/participants")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()[0]), {"id", "name", "has_drawn"})
        self.assertNotIn("slip_taken", response.content.decode())
        self.assertNotIn("sealed_pick", response.content.decode())

    def test_organizer_pages_do_not_expose_draw_data_or_recovery_keys(self):
        self.event.status = Event.Status.OPEN
        self.event.save(update_fields=("status",))
        recovery_keys = []
        ciphertexts = []
        for participant in self.people:
            self.set_member_session(participant)
            response = self.post_json("/api/draw", {})
            self.assertEqual(response.status_code, 200)
            recovery_keys.append(response.json()["recovery_key"])
            ciphertexts.append(Participant.objects.get(pk=participant.pk).sealed_pick)

        user = get_user_model().objects.create_user(username="organizer", password="secret", is_staff=True)
        self.client.force_login(user)
        for path in ("/manage/", "/manage/login/"):
            html = self.client.get(path).content.decode()
            self.assertNotIn("slip_taken", html)
            self.assertNotIn("sealed_pick", html)
            for value in recovery_keys + ciphertexts:
                self.assertNotIn(value, html)

    def test_reveal_is_created_only_after_explicit_opt_in(self):
        self.event.status = Event.Status.OPEN
        self.event.save(update_fields=("status",))
        participant = self.people[0]
        self.set_member_session(participant)
        result = self.post_json("/api/draw", {}).json()
        self.assertEqual(Reveal.objects.count(), 0)

        self.event.status = Event.Status.REVEAL
        self.event.save(update_fields=("status",))
        pick_payload = {"participant_id": participant.pk, "recovery_key": result["recovery_key"]}
        private_view = self.post_json("/api/my-pick", pick_payload)
        self.assertEqual(private_view.status_code, 200)
        self.assertEqual(Reveal.objects.count(), 0)

        reveal_response = self.post_json("/api/my-pick", {**pick_payload, "reveal": True})
        self.assertEqual(reveal_response.status_code, 200)
        self.assertTrue(reveal_response.json()["revealed"])
        self.assertEqual(Reveal.objects.count(), 1)
        page = self.client.get("/reveals/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, f"was {participant.name}'s monito/monita")

    def test_csrf_is_required_for_json_post(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/api/enter", data='{"code":"23456789A"}', content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "csrf_failed")


class OrganizerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.event = Event.objects.create(pk=1, year=2026, code="23456789A")
        self.people = [Participant.objects.create(event=self.event, name=name) for name in ("Mama", "Papa", "Ate Joy")]
        self.user = get_user_model().objects.create_user(username="admin", password="secret", is_staff=True)
        self.client.force_login(self.user)

    def test_participant_names_are_trimmed_and_case_insensitive(self):
        participant = Participant.objects.create(event=self.event, name="  Ate Nina  ")
        self.assertEqual(participant.name, "Ate Nina")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Participant.objects.create(event=self.event, name="  mAmA  ")

    def test_participant_add_form_reports_case_insensitive_duplicates(self):
        response = self.client.post(
            "/manage/",
            {"action": "add_one", "name": "mAmA"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "May kaparehong pangalan na: mAmA.")
        self.assertEqual(Participant.objects.filter(event=self.event).count(), 3)

    def test_participant_add_form_handles_database_integrity_error(self):
        with patch.object(Participant, "save", side_effect=IntegrityError("duplicate")):
            response = self.client.post(
                "/manage/",
                {"action": "add_one", "name": "Cousin Bea"},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "May kaparehong pangalan na: Cousin Bea.")

    def test_open_validates_and_locked_edits_are_rejected(self):
        Participant.objects.create(event=self.event, name="Cousin Bea")
        Exclusion.objects.create(event=self.event, a=self.people[0], b=self.people[1])
        response = self.client.post("/manage/", {"action": "open"})
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.OPEN)

        before_count = Participant.objects.filter(event=self.event).count()
        before_exclusions = Exclusion.objects.filter(event=self.event).count()
        self.client.post("/manage/", {"action": "add_one", "name": "Cousin Bea"})
        self.client.post("/manage/", {"action": "delete_participant", "name": self.people[0].name})
        self.client.post(
            "/manage/",
            {"action": "add_exclusion", "name_a": self.people[0].name, "name_b": self.people[1].name},
        )
        self.client.post(
            "/manage/",
            {"action": "remove_exclusion", "name_a": self.people[0].name, "name_b": self.people[1].name},
        )
        self.assertEqual(Participant.objects.filter(event=self.event).count(), before_count)
        self.assertEqual(Exclusion.objects.filter(event=self.event).count(), before_exclusions)

    def test_infeasible_graph_stays_in_setup_and_reports_reason(self):
        Exclusion.objects.create(event=self.event, a=self.people[0], b=self.people[1])
        Exclusion.objects.create(event=self.event, a=self.people[0], b=self.people[2])
        response = self.client.post("/manage/", {"action": "open"}, follow=True)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.SETUP)
        self.assertContains(response, "Walang pinapayagang recipient para kay: Mama")

    def test_reveal_action_waits_for_all_draws(self):
        self.event.status = Event.Status.OPEN
        self.event.save(update_fields=("status",))
        self.client.post("/manage/", {"action": "reveal"})
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.OPEN)

        Participant.objects.filter(event=self.event).update(has_drawn=True)
        self.client.post("/manage/", {"action": "reveal"})
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.REVEAL)


class HealthAndBootstrapTests(TestCase):
    def test_healthz_queries_database_without_creating_a_session(self):
        before = Session.objects.count()
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertNotIn("sessionid", response.cookies)
        self.assertEqual(Session.objects.count(), before)

    def test_healthz_returns_service_unavailable_on_database_error(self):
        with patch("bunutan.views.connection.cursor", side_effect=DatabaseError("database unavailable")):
            response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"ok": False})

    def test_ensure_superuser_skips_when_required_environment_is_missing(self):
        env = os.environ.copy()
        env.pop("DJANGO_SUPERUSER_USERNAME", None)
        env.pop("DJANGO_SUPERUSER_PASSWORD", None)
        output = StringIO()
        with patch.dict(os.environ, env, clear=True):
            call_command("ensure_superuser", stdout=output)
        self.assertEqual(output.getvalue(), "")
        self.assertFalse(get_user_model().objects.filter(username="render-organizer").exists())

    def test_ensure_superuser_is_idempotent_and_preserves_existing_password(self):
        env = {
            "DJANGO_SUPERUSER_USERNAME": "render-organizer",
            "DJANGO_SUPERUSER_PASSWORD": "first-secret-password",
            "DJANGO_SUPERUSER_EMAIL": "organizer@example.test",
        }
        output = StringIO()
        with patch.dict(os.environ, env, clear=False):
            call_command("ensure_superuser", stdout=output)
        user = get_user_model().objects.get(username="render-organizer")
        original_hash = user.password
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("first-secret-password"))

        env["DJANGO_SUPERUSER_PASSWORD"] = "replacement-must-not-be-used"
        output = StringIO()
        with patch.dict(os.environ, env, clear=False):
            call_command("ensure_superuser", stdout=output)
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)
        self.assertTrue(user.check_password("first-secret-password"))
        self.assertIn("already exists; unchanged", output.getvalue())
        self.assertNotIn("replacement-must-not-be-used", output.getvalue())


@skipUnless(connection.vendor == "postgresql", "row-lock concurrency test requires PostgreSQL")
class DrawConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.event = Event.objects.create(pk=1, year=2026, code="23456789A", status=Event.Status.OPEN)
        self.people = [
            Participant.objects.create(event=self.event, name=name)
            for name in ("Mama", "Papa", "Ate Joy", "Kuya Migs", "Lola Nena")
        ]

    def _client_for(self, participant):
        client = Client()
        session = client.session
        session["code_ok"] = True
        session["me"] = participant.pk
        session.save()
        return client

    def test_simultaneous_draws_by_different_givers_take_distinct_receivers(self):
        clients = [self._client_for(person) for person in self.people[:2]]
        barrier = Barrier(3)

        def draw(client):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return client.post("/api/draw", data="{}", content_type="application/json")
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(draw, client) for client in clients]
            barrier.wait(timeout=15)
            responses = [future.result(timeout=30) for future in futures]

        self.assertEqual([response.status_code for response in responses], [200, 200])
        names = [response.json()["name"] for response in responses]
        self.assertEqual(len(set(names)), 2)
        self.assertEqual(Participant.objects.filter(event=self.event, slip_taken=True).count(), 2)
