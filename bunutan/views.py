import hashlib
import binascii
import json
import math
import re
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from . import draw
from .forms import EventSettingsForm
from .models import Event, Exclusion, Participant, Reveal, generate_event_code


def get_event() -> Event:
    event, _ = Event.objects.get_or_create(
        pk=1,
        defaults={"title": "Family Bunutan", "year": timezone.localdate().year},
    )
    return event


def json_error(error: str, message: str, status: int) -> JsonResponse:
    return JsonResponse({"ok": False, "error": error, "message": message}, status=status)


def _request_data(request: HttpRequest) -> dict:
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
    return request.POST.dict()


def _client_ip(request: HttpRequest) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


def _rate_key(kind: str, ip: str, suffix: str) -> str:
    digest = hashlib.sha256(f"{kind}:{ip}".encode("utf-8")).hexdigest()
    return f"bunutan:{kind}:{suffix}:{digest}"


def _locked_seconds(kind: str, ip: str) -> int:
    lock_key = _rate_key(kind, ip, "lock")
    expires_at = cache.get(lock_key)
    if expires_at is None:
        return 0
    remaining = math.ceil(float(expires_at) - time.time())
    if remaining <= 0:
        cache.delete(lock_key)
        cache.delete(_rate_key(kind, ip, "attempts"))
        return 0
    return remaining


def _record_failure(kind: str, ip: str) -> int:
    attempts_key = _rate_key(kind, ip, "attempts")
    try:
        count = cache.incr(attempts_key)
    except ValueError:
        cache.add(attempts_key, 1, timeout=300)
        count = int(cache.get(attempts_key, 1))
    if count >= 5:
        cache.set(_rate_key(kind, ip, "lock"), time.time() + 300, timeout=300)
        return _locked_seconds(kind, ip)
    return 0


def _clear_failures(kind: str, ip: str) -> None:
    cache.delete(_rate_key(kind, ip, "attempts"))
    cache.delete(_rate_key(kind, ip, "lock"))


def _normalize_code(value: str) -> str:
    return re.sub(r"[\s-]+", "", value).upper()


def _forbidden_pairs(event: Event, participant_ids: list[int]) -> set[tuple[int, int]]:
    forbidden = {(participant_id, participant_id) for participant_id in participant_ids}
    for a_id, b_id in Exclusion.objects.filter(event=event).values_list("a_id", "b_id"):
        forbidden.add((a_id, b_id))
        forbidden.add((b_id, a_id))
    return forbidden


def _participant_context(request: HttpRequest) -> tuple[bool, int | None]:
    return request.session.get("code_ok") is True, request.session.get("me")


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    if request.path.startswith("/api/"):
        return json_error("csrf_failed", "Hindi na-verify ang request. I-refresh ang page at subukan ulit.", 403)
    return HttpResponse("CSRF verification failed.", status=403)


@require_GET
def enter_page(request: HttpRequest) -> HttpResponse:
    return render(request, "bunutan/enter.html")


def _member_page(request: HttpRequest, template: str) -> HttpResponse:
    code_ok, me = _participant_context(request)
    if not code_ok:
        return redirect("/")
    event = get_event()
    participant_name = None
    if me is not None:
        participant_name = Participant.objects.filter(event=event, pk=me).values_list("name", flat=True).first()
    return render(
        request,
        template,
        {
            "event": event,
            "is_open": event.status == Event.Status.OPEN,
            "is_reveal": event.status == Event.Status.REVEAL,
            "participant_name": participant_name,
        },
    )


@require_GET
def pick_name_page(request: HttpRequest) -> HttpResponse:
    return _member_page(request, "bunutan/pick_name.html")


@require_GET
def bowl_page(request: HttpRequest) -> HttpResponse:
    code_ok, me = _participant_context(request)
    if not code_ok:
        return redirect("/")
    if me is None:
        return redirect("/pick-name/")
    return _member_page(request, "bunutan/bowl.html")


@require_GET
def my_pick_page(request: HttpRequest) -> HttpResponse:
    code_ok, me = _participant_context(request)
    if not code_ok:
        return redirect("/")
    if me is None:
        return redirect("/pick-name/")
    return _member_page(request, "bunutan/my_pick.html")


@require_GET
def wishlists_page(request: HttpRequest) -> HttpResponse:
    code_ok, _ = _participant_context(request)
    if not code_ok:
        return redirect("/")
    return _member_page(request, "bunutan/wishlists.html")


@require_GET
def reveals_page(request: HttpRequest) -> HttpResponse:
    code_ok, _ = _participant_context(request)
    if not code_ok:
        return redirect("/")
    event = get_event()
    reveals = list(
        Reveal.objects.filter(event=event)
        .order_by("giver__name")
        .values("giver__name", "receiver__name")
    )
    return render(request, "bunutan/reveals.html", {"reveals": reveals})


@require_GET
def api_state(request: HttpRequest) -> JsonResponse:
    event = get_event()
    total = Participant.objects.filter(event=event).count()
    drawn_count = Participant.objects.filter(event=event, has_drawn=True).count()
    remaining = Participant.objects.filter(event=event, slip_taken=False).count()
    return JsonResponse(
        {
            "ok": True,
            "title": event.title,
            "year": event.year,
            "budget_text": event.budget_text,
            "party_date": event.party_date.isoformat() if event.party_date else None,
            "status": event.status,
            "total": total,
            "drawn_count": drawn_count,
            "remaining": remaining,
        }
    )


@require_POST
def api_enter(request: HttpRequest) -> JsonResponse:
    ip = _client_ip(request)
    locked = _locked_seconds("code", ip)
    if locked:
        response = json_error("locked_out", "Masyadong maraming maling code. Subukan ulit mamaya.", 429)
        response["Retry-After"] = str(locked)
        return response
    supplied = _normalize_code(str(_request_data(request).get("code", "")))
    event = get_event()
    try:
        code_matches = secrets.compare_digest(supplied.encode("ascii"), event.code.encode("ascii"))
    except UnicodeEncodeError:
        code_matches = False
    if not code_matches:
        locked = _record_failure("code", ip)
        if locked:
            response = json_error("locked_out", "Masyadong maraming maling code. Subukan ulit mamaya.", 429)
            response["Retry-After"] = str(locked)
            return response
        return json_error("bad_code", "Hindi tugma ang code. Pakisuri at subukan ulit.", 403)
    _clear_failures("code", ip)
    request.session["code_ok"] = True
    return JsonResponse({"ok": True})


@require_GET
def api_participants(request: HttpRequest) -> JsonResponse:
    code_ok, _ = _participant_context(request)
    if not code_ok:
        return json_error("not_entered", "Ilagay muna ang event code.", 401)
    event = get_event()
    participants = list(Participant.objects.filter(event=event).values("id", "name", "has_drawn"))
    return JsonResponse(participants, safe=False)


@require_POST
def api_claim(request: HttpRequest) -> JsonResponse:
    code_ok, _ = _participant_context(request)
    if not code_ok:
        return json_error("not_entered", "Ilagay muna ang event code.", 401)
    try:
        participant_id = int(_request_data(request).get("participant_id", ""))
    except (TypeError, ValueError):
        return json_error("not_found", "Hindi makita ang pangalan. Piliin ulit sa listahan.", 404)
    event = get_event()
    participant = Participant.objects.filter(event=event, pk=participant_id).first()
    if participant is None:
        return json_error("not_found", "Hindi makita ang pangalan. Piliin ulit sa listahan.", 404)
    if participant.has_drawn and request.session.get("me") != participant.pk:
        return json_error("already_drawn", "Nakabunot na ang pangalang ito.", 409)
    request.session["me"] = participant.pk
    return JsonResponse({"ok": True})


@require_POST
def api_draw(request: HttpRequest) -> JsonResponse:
    code_ok, me = _participant_context(request)
    if not code_ok or me is None:
        return json_error("not_claimed", "Piliin muna ang pangalan mo.", 401)
    event = get_event()
    if event.status != Event.Status.OPEN:
        return json_error("not_open", "Hindi pa bukas ang bunutan.", 409)

    try:
        with transaction.atomic():
            current_event = Event.objects.select_for_update().get(pk=1)
            if current_event.status != Event.Status.OPEN:
                return json_error("not_open", "Hindi pa bukas ang bunutan.", 409)
            giver = Participant.objects.select_for_update().filter(event=event, pk=me).first()
            if giver is None:
                request.session.pop("me", None)
                return json_error("not_claimed", "Piliin muna ang pangalan mo.", 401)
            if giver.has_drawn:
                return json_error("already_drawn", "Nakabunot ka na. Gamitin ang recovery key para makita ulit ang resulta.", 409)
            remaining_giver_ids = list(
                Participant.objects.filter(event=event, has_drawn=False).values_list("pk", flat=True)
            )
            remaining_receiver_ids = list(
                Participant.objects.filter(event=event, slip_taken=False).values_list("pk", flat=True)
            )
            secrets.SystemRandom().shuffle(remaining_giver_ids)
            secrets.SystemRandom().shuffle(remaining_receiver_ids)
            forbidden = _forbidden_pairs(event, remaining_giver_ids)
            receiver_id = draw.choose_receiver(
                giver.pk, remaining_giver_ids, remaining_receiver_ids, forbidden
            )
            receiver = Participant.objects.get(event=event, pk=receiver_id)
            recovery_key = Fernet.generate_key()
            sealed_pick = Fernet(recovery_key).encrypt(receiver.name.encode("utf-8")).decode("ascii")
            giver.has_drawn = True
            giver.sealed_pick = sealed_pick
            giver.save(update_fields=("has_drawn", "sealed_pick"))
            Participant.objects.filter(event=event, pk=receiver.pk).update(slip_taken=True)
    except draw.DrawDeadlock:
        return json_error("deadlock", "Hindi natuloy ang bunutan. Ipaalam ito sa organizer para i-reset.", 500)

    return JsonResponse({"ok": True, "name": receiver.name, "recovery_key": recovery_key.decode("ascii")})


@require_POST
def api_my_pick(request: HttpRequest) -> JsonResponse:
    code_ok, me = _participant_context(request)
    data = _request_data(request)
    try:
        participant_id = int(data.get("participant_id", ""))
    except (TypeError, ValueError):
        participant_id = -1
    if not code_ok or me is None or participant_id != me:
        return json_error("invalid_key", "Hindi ma-verify ang recovery key.", 403)

    ip = _client_ip(request)
    locked = _locked_seconds("pick", ip)
    if locked:
        response = json_error("locked_out", "Masyadong maraming maling recovery key. Subukan ulit mamaya.", 429)
        response["Retry-After"] = str(locked)
        return response

    event = get_event()
    reveal_requested = data.get("reveal") in (True, 1, "1", "true", "yes")
    if reveal_requested and event.status != Event.Status.REVEAL:
        return json_error("not_revealing", "Hindi pa nagsisimula ang reveal.", 409)
    token = Participant.objects.filter(event=event, pk=me).values_list("sealed_pick", flat=True).first()
    try:
        key = str(data.get("recovery_key", "")).encode("ascii")
        name = Fernet(key).decrypt((token or "").encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError, UnicodeEncodeError, UnicodeDecodeError, binascii.Error):
        locked = _record_failure("pick", ip)
        if locked:
            response = json_error("locked_out", "Masyadong maraming maling recovery key. Subukan ulit mamaya.", 429)
            response["Retry-After"] = str(locked)
            return response
        return json_error("invalid_key", "Hindi ma-verify ang recovery key.", 403)
    _clear_failures("pick", ip)
    if reveal_requested:
        with transaction.atomic():
            current_event = Event.objects.select_for_update().get(pk=1)
            if current_event.status != Event.Status.REVEAL:
                return json_error("not_revealing", "Hindi pa nagsisimula ang reveal.", 409)
            giver = Participant.objects.filter(event=current_event, pk=me).first()
            receiver = Participant.objects.filter(event=current_event, name__iexact=name).first()
            if giver is None or receiver is None:
                return json_error("invalid_key", "Hindi ma-verify ang recovery key.", 403)
            Reveal.objects.get_or_create(event=current_event, giver=giver, defaults={"receiver": receiver})
        return JsonResponse({"ok": True, "name": name, "revealed": True})
    return JsonResponse({"ok": True, "name": name})


@require_POST
def api_wishlist(request: HttpRequest) -> JsonResponse:
    code_ok, me = _participant_context(request)
    if not code_ok or me is None:
        return json_error("not_claimed", "Ilagay ang event code at piliin ang pangalan mo muna.", 401)
    text = str(_request_data(request).get("text", ""))
    if len(text) > 500:
        return json_error("too_long", "Hanggang 500 character lang ang wish list.", 400)
    event = get_event()
    updated = Participant.objects.filter(event=event, pk=me).update(wish_list=text.strip())
    if not updated:
        return json_error("not_claimed", "Piliin muna ang pangalan mo.", 401)
    return JsonResponse({"ok": True})


@require_GET
def api_wishlists(request: HttpRequest) -> JsonResponse:
    code_ok, _ = _participant_context(request)
    if not code_ok:
        return json_error("not_entered", "Ilagay muna ang event code.", 401)
    event = get_event()
    wishlists = list(
        Participant.objects.filter(event=event).exclude(wish_list="").values("name", "wish_list")
    )
    return JsonResponse(wishlists, safe=False)


def _staff_only(user) -> bool:
    return user.is_authenticated and user.is_staff


def staff_required(view):
    return login_required(user_passes_test(_staff_only)(view))


def _manage_context(event: Event, form: EventSettingsForm | None = None) -> dict:
    progress = list(Participant.objects.filter(event=event).values("name", "has_drawn"))
    participant_names = list(Participant.objects.filter(event=event).values_list("name", flat=True))
    exclusion_pairs = list(
        Exclusion.objects.filter(event=event).values_list("a__name", "b__name")
    )
    return {
        "event_settings": {
            "title": event.title,
            "year": event.year,
            "budget_text": event.budget_text,
            "party_date": event.party_date.isoformat() if event.party_date else "",
        },
        "code": event.code,
        "status": event.status,
        "progress": progress,
        "participant_names": participant_names,
        "exclusion_pairs": exclusion_pairs,
        "settings_form": form or EventSettingsForm(instance=event),
        "edits_locked": event.status != Event.Status.SETUP,
    }


def _find_participant(event: Event, name: str) -> Participant | None:
    return Participant.objects.filter(event=event, name__iexact=name.strip()).first()


def _add_participant_names(event: Event, raw_names: list[str]) -> tuple[int, list[str]]:
    clean_names = [name.strip() for name in raw_names if name.strip()]
    if not clean_names:
        return 0, ["Maglagay ng kahit isang pangalan."]
    added = 0
    errors = []
    seen = {name.casefold() for name in Participant.objects.filter(event=event).values_list("name", flat=True)}
    for name in clean_names:
        folded = name.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        if len(name) > 40:
            errors.append(f"{name[:40]}… ay lampas sa 40 character.")
            continue
        try:
            Participant.objects.create(event=event, name=name)
            added += 1
        except (IntegrityError, ValidationError):
            errors.append(f"Hindi maidagdag ang {name}.")
    return added, errors


@staff_required
def manage_dashboard(request: HttpRequest) -> HttpResponse:
    event = get_event()
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "settings":
            form = EventSettingsForm(request.POST, instance=event)
            if form.is_valid():
                form.save()
                messages.success(request, "Na-update ang settings.")
                return redirect("manage_dashboard")
            messages.error(request, "Pakisuri ang event settings.")
            return render(request, "bunutan/manage.html", _manage_context(event, form))

        if action == "regenerate_code":
            event.code = generate_event_code()
            event.save(update_fields=("code",))
            messages.success(request, "Gumawa ng bagong event code.")
        elif action in {"add_one", "bulk_add"}:
            if event.status != Event.Status.SETUP:
                messages.error(request, "Naka-lock na ang listahan ng pangalan pagkatapos buksan ang bunutan.")
            else:
                names = [request.POST.get("name", "")] if action == "add_one" else request.POST.get("names", "").splitlines()
                added, errors = _add_participant_names(event, names)
                if added:
                    messages.success(request, f"Nagdagdag ng {added} pangalan.")
                for error in errors:
                    messages.error(request, error)
        elif action == "delete_participant":
            if event.status != Event.Status.SETUP:
                messages.error(request, "Naka-lock na ang listahan ng pangalan pagkatapos buksan ang bunutan.")
            else:
                participant = _find_participant(event, request.POST.get("name", ""))
                if participant:
                    participant.delete()
                    messages.success(request, "Tinanggal ang participant at kaugnay na exclusions.")
                else:
                    messages.error(request, "Hindi makita ang pangalan.")
        elif action in {"add_exclusion", "remove_exclusion"}:
            if event.status != Event.Status.SETUP:
                messages.error(request, "Naka-lock na ang exclusions pagkatapos buksan ang bunutan.")
            else:
                a = _find_participant(event, request.POST.get("name_a", ""))
                b = _find_participant(event, request.POST.get("name_b", ""))
                if not a or not b or a.pk == b.pk:
                    messages.error(request, "Pumili ng dalawang magkaibang pangalan.")
                else:
                    first, second = sorted((a, b), key=lambda participant: participant.pk)
                    if action == "add_exclusion":
                        _, created = Exclusion.objects.get_or_create(event=event, a=first, b=second)
                        messages.success(request, "Idinagdag ang mutual exclusion." if created else "Naka-set na ang exclusion na ito.")
                    else:
                        deleted, _ = Exclusion.objects.filter(event=event, a=first, b=second).delete()
                        messages.success(request, "Tinanggal ang exclusion." if deleted else "Walang ganoong exclusion.")
        elif action == "open":
            if event.status != Event.Status.SETUP:
                messages.error(request, "Setup status lang ang puwedeng buksan.")
            else:
                ids = list(Participant.objects.filter(event=event).values_list("pk", flat=True))
                if len(ids) < 3:
                    messages.error(request, "Kailangan ng hindi bababa sa 3 participants.")
                elif draw.has_perfect_matching(ids, ids, _forbidden_pairs(event, ids)):
                    event.status = Event.Status.OPEN
                    event.save(update_fields=("status",))
                    messages.success(request, "Bukas na ang bunutan.")
                else:
                    forbidden = _forbidden_pairs(event, ids)
                    blocked = [
                        _find_participant(event, str(name)).name
                        for participant_id, name in Participant.objects.filter(event=event).values_list("pk", "name")
                        if not any(draw.allowed(participant_id, receiver, forbidden) for receiver in ids)
                    ]
                    if blocked:
                        detail = "Walang pinapayagang recipient para kay: " + ", ".join(blocked) + "."
                    else:
                        pairs = [f"{a} ↔ {b}" for a, b in Exclusion.objects.filter(event=event).values_list("a__name", "b__name")]
                        detail = "Pinagsama-sama, ginagawang imposibleng kumpletuhin ng self-draw rule at exclusions ang assignment. Suriin ang exclusions: " + (", ".join(pairs) if pairs else "walang exclusion na naka-set") + "."
                    messages.error(request, detail)
        elif action == "close":
            event.status = Event.Status.CLOSED
            event.save(update_fields=("status",))
            messages.success(request, "Isinara ang bunutan.")
        elif action == "reveal":
            if event.status != Event.Status.OPEN:
                messages.error(request, "Buksan muna ang bunutan bago simulan ang reveal.")
            elif Participant.objects.filter(event=event, has_drawn=False).exists():
                messages.error(request, "Hintayin munang makabunot ang lahat bago simulan ang reveal.")
            else:
                event.status = Event.Status.REVEAL
                event.save(update_fields=("status",))
                messages.success(request, "Nagsimula na ang voluntary reveal.")
        elif action == "reset":
            if request.POST.get("confirm", "").strip() != "RESET":
                messages.error(request, "I-type ang RESET para kumpirmahin ang pagbura ng draw results.")
            else:
                with transaction.atomic():
                    Participant.objects.filter(event=event).update(has_drawn=False, slip_taken=False, sealed_pick=None)
                    Reveal.objects.filter(event=event).delete()
                    event.status = Event.Status.SETUP
                    event.save(update_fields=("status",))
                messages.success(request, "Na-reset ang draw. Kailangang bumunot muli ang lahat.")
        else:
            messages.error(request, "Hindi kilalang action.")
        return redirect("manage_dashboard")

    return render(request, "bunutan/manage.html", _manage_context(event))


def manage_login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("manage_dashboard")
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
        if user is not None and user.is_staff:
            login(request, user)
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(next_url)
            return redirect("manage_dashboard")
        messages.error(request, "Hindi wasto ang organizer username o password.")
    return render(request, "bunutan/manage_login.html")


@login_required
@require_POST
def manage_logout(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("manage_login")
