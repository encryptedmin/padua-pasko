# Bunutan

Bunutan is a small server-rendered Django app for a Filipino Christmas gift exchange. The templates provide stable, minimal markup; a separate frontend can connect the forms and controls to the JSON endpoints.

## Requirements

- Python 3.14.5
- Django 6.1 (the current release line compatible with Python 3.14)
- SQLite, included with Python
- `cryptography` for Fernet encryption

The only Python dependencies are Django and `cryptography`.

## Setup

On Windows, double-click `start-system.bat` for local testing. It creates `.venv` and installs the listed requirements when needed, checks/creates model migrations, applies pending migrations, and starts the server at `http://127.0.0.1:8000/`. It does not create an organizer account or add demo participants; on a fresh database, run `python manage.py createsuperuser` and `python manage.py seed_demo` once from this folder.

From this directory, create and activate a virtual environment, then install dependencies and prepare the database:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

$env:DJANGO_SECRET_KEY = "replace-with-a-long-random-secret"
$env:DJANGO_DEBUG = "True"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1"

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

The organizer account is a Django staff user created with `createsuperuser`; use `/manage/login/` to sign in. The demo command creates the event and ten example participants, including one mutual spouse exclusion. It is safe to rerun while the event is still in `SETUP`.

For deployment, set `DJANGO_SECRET_KEY` to a private random value, set `DJANGO_DEBUG=False`, and set `DJANGO_ALLOWED_HOSTS` to the exact host names or IP addresses that serve the app. Do not use the development fallback key in a public deployment.

## Reach the app on family phones

Connect the host computer and phones to the same trusted Wi-Fi network. Find the computer's private LAN address, then set it in `DJANGO_ALLOWED_HOSTS` and bind Django to all network interfaces:

```powershell
$env:DJANGO_SECRET_KEY = "your-private-random-secret"
$env:DJANGO_DEBUG = "False"
$env:DJANGO_ALLOWED_HOSTS = "localhost,127.0.0.1,192.168.1.25"
python manage.py runserver 0.0.0.0:8000
```

Replace `192.168.1.25` with the host computer's actual LAN address. Family members can open `http://192.168.1.25:8000/` on their phones and enter the event code from `/manage/`. Allow inbound TCP port 8000 on the host firewall for the trusted family network only. For an internet-facing deployment, use a production WSGI/ASGI server and HTTPS rather than Django's development server.

## Privacy model and limits

- The database never stores a readable giver-to-receiver mapping. A participant row stores `has_drawn`, `slip_taken`, and that giver's Fernet-encrypted receiver name. The draw generates a fresh key and returns it once to the member; the server never stores the key.
- The organizer dashboard builds the progress board from only participant names and `has_drawn`. It does not query draw fields for its participant context. There is no Django admin site.
- Members see each participant's draw status and a remaining-slip count. The public participant endpoint contains only `id`, `name`, and `has_drawn` for each person.
- The Fernet key is the only way to recover that participant's encrypted result. If it is lost, the organizer must reset the draw; everybody draws again.
- This protects picks from someone inspecting the database or using the organizer panel. The shared event code does not verify individual identity: anyone who knows it can select another participant's name before that participant draws. The app therefore relies on family members to choose their own names. Add individual authentication before using it where identity impersonation is a concern.
- Run with `DJANGO_DEBUG=False`, keep the Django secret private, and do not browse or copy the SQLite database during the draw. Database access can reveal participant status and encrypted picks even though it cannot decrypt them without the one-time keys.
- Mutual swaps such as A drawing B and B drawing A are valid by design. Exclusions only prohibit the configured mutual pairs and self-draws.
- The default LocMem cache keeps wrong-code and wrong-key lockouts in process memory. It is suitable for a single-process family event server. A multi-process deployment needs a shared cache to enforce lockouts consistently.

## Organizer and member flows

- Public pages: `/`, `/pick-name/`, `/bowl/`, `/my-pick/`, `/wishlists/`.
- JSON API: `/api/state`, `/api/enter`, `/api/participants`, `/api/claim`, `/api/draw`, `/api/my-pick`, `/api/wishlist`, and `/api/wishlists`.
- During `REVEAL`, members can voluntarily publish a result through `/api/my-pick`; only opted-in results appear at `/reveals/`.
- Organizer panel: `/manage/`. Participant and exclusion edits lock once the event leaves `SETUP`.
- Every POST is protected by Django CSRF middleware. JSON clients should send the CSRF token in the `X-CSRFToken` header.
- Wrong event codes and recovery keys are rate limited to five failed attempts per IP followed by a five-minute lockout.

## Tests

Run the requested Django and matching-algorithm suite with:

```powershell
$env:DJANGO_SECRET_KEY = "test-only-secret"
python manage.py test
```

