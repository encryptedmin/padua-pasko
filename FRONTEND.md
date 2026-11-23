# Bunutan frontend

This frontend uses Django templates, local static files, and vanilla JavaScript modules. It has no build step or npm dependency. Start the existing project with:

```powershell
python manage.py runserver 0.0.0.0:8000
```

## Files

- `templates/bunutan/`: shared base plus entry, participant, bowl, private pick, wish list, reveal, and organizer screens.
- `static/css/bunutan.css`: responsive festive theme, dialogs, cards, waiting states, bowl, reveal, and reduced-motion styles.
- `static/css/fonts.css`: local `Baloo 2` and `Mountains of Christmas` faces.
- `static/js/api.js`: same-origin JSON requests, CSRF header, normalized errors, and 10-second timeout.
- `static/js/fx.js`, `site.js`, `storage.js`, `reveal.js`: effects, settings, local identity record, and private reveal behavior.
- `static/js/pages/`: page-specific entry, name-pick, bowl, private-pick, wishlist, and organizer behavior.
- `static/vendor/`: local copies of Tailwind's browser CDN build, animate.css, GSAP, canvas-confetti, and local font files. Runtime pages do not load remote assets.
- `static/img/parol.svg`: favicon artwork.
- `bunutan_site/settings.py`: points Django's staticfiles finder at the project `static/` directory so `runserver` serves these assets.

## Animation timing

- Name cards stagger by 45 ms (capped at 420 ms); confirmation modal uses animate.css bounce-in.
- A bowl draw waits about 560 ms before the API call and waits at least 3 seconds before starting the countdown, even if the request returns sooner. The slip flight takes about 720 ms; the `3`, `2`, `1` beats each take about 680 ms, followed by a 760 ms flip settle.
- The reveal requires a 520 ms press-and-hold. The result auto-hides after 20 seconds of inactivity and on tab hide. Motion-reduced mode uses fades, disables confetti, and skips bowl flight/shake.
- Organizer counts poll every 15 seconds. Waiting member pages poll every 10 seconds.

## Backend contract TODOs

- **New-device or cleared-session recovery for an already-drawn participant:** `my_pick_page` redirects to `/pick-name/` unless the Django session already has `me`. The current `/api/claim` rejects an already-drawn participant on a different session, while `/api/my-pick` also needs that participant in the session. A recovery key by itself therefore cannot restore the participant identity on a new phone or after the session is cleared. The UI explains this limitation; backend work would need an explicit recovery flow. No backend behavior was changed here.
- **Ambiguous draw timeout:** `/api/state` reports event totals and status, not whether the current participant drew or the resulting name. If `/api/draw` commits but its response is lost, the frontend cannot prove the result from the current contract. It checks the error and state, uses a matching local recovery record when available, and otherwise tells the participant to contact the organizer for a reset.

## Manual QA checklist

1. Enter an incorrect code, then a correct 9-character code; verify shake/red feedback and transition.
2. Trigger the backend lockout and verify the countdown disables and re-enables code entry.
3. Pick a name, verify the confirmation dialog, cancel, then confirm and reach the bowl.
4. Load `/pick-name/` and `/bowl/` while the event is not OPEN; open it from the organizer panel and verify auto-transition.
5. On a low-end Android phone and iPhone Safari, shake and draw; verify no double draw, the 3-second minimum, countdown, flight, and flip.
6. Verify hold-to-reveal, keyboard/screen-reader toggle, `Itago`, 20-second idle hide, and hide on tab switch.
7. Verify the recovery key is shown once and saved, then reopen `/my-pick/` on the same device. On a new device, test manual identity/key entry and confirm the backend limitation above is communicated.
8. Enable OS reduced motion and the in-page motion setting; verify fades replace shake/flight/confetti.
9. Use the organizer panel at 360 px width; verify stats, code copy/invitation, participant chips, exclusions, settings, danger confirmations, and RESET gate.

Physical-device QA in item 5 and 9 remains to be performed on the target family devices.
