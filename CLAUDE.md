# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Grest Manager — a Django 6.0 web app for managing children's summer camps (GREST). Designed to stay small and maintainable. Deployed on Railway (gunicorn + WhiteNoise + Postgres). Source language for UI, comments, and commit messages is Italian.

## Layout

The Django project lives in `grestmanager-project/` (not the repo root). Run all `manage.py` commands from there.

- `core/` — project config (`settings.py`, `urls.py`, `wsgi.py`/`asgi.py`)
- `grestmanager/` — the single application (models, views, forms, urls, admin, templates)

## Commands

All from `grestmanager-project/`:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver              # dev server
python manage.py test                   # full test suite (tests.py is currently a stub)
python manage.py test grestmanager.tests.SomeTest.test_method   # single test
python manage.py makemigrations grestmanager
python manage.py collectstatic          # required before deploy; WhiteNoise serves from STATIC_ROOT
gunicorn core.wsgi                       # production entrypoint (see Procfile)
```

## Configuration & environment

`core/settings.py` reads everything from environment variables (loaded from a `.env` in `grestmanager-project/` via python-dotenv). Key vars: `SECRET_KEY`, `DEBUG`, `DATABASE_URL` (parsed by `dj-database-url`), `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`. Note `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are **comma-split** strings, not single values.

- `DEBUG=False` automatically enables SSL redirect and secure/CSRF cookies — expect HTTPS-only behavior when testing a non-debug build locally.
- The database is always Postgres via `DATABASE_URL`; there is no SQLite fallback configured (the SQLite block is commented out). Set `DATABASE_URL` before running anything that hits the DB.
- Locale is fixed to Italian / `Europe/Rome`.

## Architecture & conventions

**Ownership-based authorization.** Every `Person` has a `managed_by` FK to the auth user. The core access rule throughout the app is "you can only see/edit the people you manage." Detail/update/delete/create views enforce this by overriding `dispatch()` and raising `PermissionDenied` when `obj.managed_by != request.user` (or, for nested resources, `obj.related_to.managed_by`). Queryset-based views filter with `managed_by=self.request.user` / `related_to__managed_by=...`. When adding any view that touches `Person`, `Subscription`, or `TimeEntry`, replicate this ownership check — it is the app's only authorization boundary.

**CBV vs FBV split (intentional).** Most views are class-based generic views. Two views (`subscriptions`, `time_entries` in `views.py`) are function-based **on purpose**: they combine `@permission_required(..., raise_exception=True)` with per-user queryset filtering, which the author found awkward to express with mixins. Don't "modernize" these to CBVs without preserving both behaviors.

**Django permissions + groups.** List/create views gate on model permissions like `grestmanager.add_person` and `grestmanager.add_subscription` (via `PermissionRequiredMixin` or the decorator). On registration, `RegisterView` adds each new user to a group named **`BaseUsers`**. This group must exist in the database (create it in the admin and assign the relevant `grestmanager` permissions) or new users get no permissions and registration logs an error. This is a required manual setup step, not derivable from code.

**Domain models** (`grestmanager/models.py`): `Person` (managed_by user), `Event` (has subscription open/close window + `is_subscription_open()`), `Subscription` (Person↔Event, with `is_active()`/`was_issued_recently()`), `TimeEntry` (check-in/out records with `entry_type` IN/OUT from `EntryType` text choices). `SubscriptionCreateView` enforces a business rule that a person can't be subscribed more than once.

**Templates** are split across three locations:
- `grestmanager/templates/grestmanager/` — app pages (extend `base.html`)
- `templates/registration/` — Django auth views (login, logout, password reset/change) + custom `register.html`
- `templates/django_registration/` — for the optional `django-registration` flow, which is **currently disabled** (commented out in `core/urls.py`, `INSTALLED_APPS`, and email settings). The active auth uses `django.contrib.auth.urls` plus the custom `RegisterView`.

**URLs.** App routes live under the `grestmanager/` prefix with `app_name = "grestmanager"`, so always reverse as `grestmanager:<name>` (e.g. `grestmanager:persons`). Auth routes are mounted at `accounts/` at the project level.

## Notes for changes

- `RegisterView.form_valid` contains `print("DEBUG: ...")` statements left in for development — remove or convert to logging if touching that code.
- `staticfiles/` is committed but is `collectstatic` output; edit source assets under `grestmanager/static/`, not `staticfiles/`.
