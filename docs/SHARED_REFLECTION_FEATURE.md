# Shareable Weekly Reflection — Feature Documentation

## Overview

This document covers the **shareable weekly reflection link** feature added on top of the existing `WeeklyReflection` digest. Previously the user could only **copy a text summary** to their clipboard. Now they can also generate a **persistent, read-only URL** that renders a frozen snapshot of their weekly reflection so others can view it in a browser.

---

## 1. What was added

### User-facing changes
- **New "Share link" button** on the Weekly Reflection card (sits next to "Copy summary").
- Clicking it:
  1. POSTs to the backend to snapshot the current reflection.
  2. Receives a short id (e.g. `37d9449cf0`).
  3. Copies a URL like `http://<host>/shared/37d9449cf0` to the clipboard.
  4. Shows a transient "Link copied!" confirmation.
- **New public route** `/shared/:id` renders the frozen snapshot read-only — no nav chrome interactions needed, just the digest.

### Backend additions
| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/reflection/share` | `POST` | Snapshot current weekly reflection, persist it, return `{ "id": "..." }`. |
| `/api/shared/{id}` | `GET` | Return the frozen `WeeklyReflection` payload for the given id, or `404`. |

### Frontend additions
- [SharedReflection.tsx](frontend/src/pages/SharedReflection.tsx) — public read-only page.
- New route in [App.tsx](frontend/src/App.tsx): `<Route path="/shared/:id" element={<SharedReflection />} />`.
- New API helpers in [api.ts](frontend/src/lib/api.ts): `api.reflection.share()`, `api.shared.get(id)`, plus convenience exports `createShareLink` and `getSharedReflection`.
- New button + handler in [WeeklyReflectionCard.tsx](frontend/src/components/WeeklyReflectionCard.tsx).

### Files touched
- **Created**: [backend/app/routes/shared.py](backend/app/routes/shared.py), [frontend/src/pages/SharedReflection.tsx](frontend/src/pages/SharedReflection.tsx).
- **Modified**: [backend/app/main.py](backend/app/main.py), [frontend/src/App.tsx](frontend/src/App.tsx), [frontend/src/lib/api.ts](frontend/src/lib/api.ts), [frontend/src/components/WeeklyReflectionCard.tsx](frontend/src/components/WeeklyReflectionCard.tsx).
- **Created at runtime**: `backend/.data/shared_reflections.json` (storage).

---

## 2. Design decisions

### 2.1 Snapshot on share (not "live" link)
The link captures the reflection **as of the moment "Share link" was clicked**. We do **not** re-compute the digest when the recipient opens the URL.

**Why:**
- Sharing intent is "here is my week" — the recipient should see what the sender saw, not a moving target.
- The underlying `build_weekly_reflection` is window-based (rolling 7 days from `now`). If we recomputed on read, the snapshot would silently change every day and become meaningless after a week.
- Keeps the shared page **completely independent of the owner's mutable entries** — no privacy leak when the owner later adds/edits entries.

### 2.2 Opaque random id, not slug or counter
`uuid.uuid4().hex[:10]` — 10 hex chars (~40 bits of entropy).

**Why:**
- **Unguessable**: a numeric counter (`/shared/1`, `/shared/2`) would let anyone enumerate every shared reflection. 40 bits is enough that brute-forcing is infeasible for the scale of a personal app while keeping URLs short.
- **No PII in the id**: contrast with using user/date which would leak identity.
- This is **capability-style auth** — possession of the link grants read access. Acceptable for a low-stakes mood tracker; would not be sufficient for sensitive data.

### 2.3 JSON file storage (consistent with the rest of the app)
Stored in `backend/.data/shared_reflections.json` as `{ id: { created_at, reflection: {...} } }`.

**Why:**
- Mirrors the existing storage pattern (`entries.json`) — no new dependency, no DB to spin up, easy to inspect and reset by deleting the file.
- The whole project intentionally avoids ORMs/databases ("intentionally simple — no database, no ORM" per [storage.py](backend/app/storage.py)).
- Trade-off: not safe for concurrent writers under load. Acceptable here because this is a single-user dev app and writes are infrequent (one per "Share link" click).

### 2.4 Reuse the existing `WeeklyReflection` Pydantic model
The share endpoint serializes the same model the `/api/reflection/weekly` endpoint already returns, and the share-get endpoint returns the same shape.

**Why:**
- Zero schema duplication — the frontend's `WeeklyReflection` TypeScript type works for both pages.
- Future changes to the reflection shape automatically apply to both live and shared views.

### 2.5 Frozen snapshot includes `share_text`
The pre-formatted multi-line summary (`share_text`) is part of the stored payload, and the shared page also renders it in a `<pre>` block.

**Why:**
- The recipient may want to copy/paste the canonical summary too, not just read the cards.
- Recomputing it on read would require re-running the formatter against the snapshot — including it once at write time is simpler and avoids duplicating formatting logic between live and shared views.

### 2.6 Public route lives **inside** `<Layout>`
We added `<Route path="/shared/:id" element={<SharedReflection />} />` inside the existing `<Layout>` wrapper rather than building a standalone shell.

**Why:**
- Consistency: the recipient still sees the app's brand and navigation, which contextualizes what they're looking at.
- Minimal change: one route, no Layout refactor.
- Trade-off: the nav links ("Dashboard", "History", etc.) are clickable but won't be meaningful for an unauthenticated viewer. Acceptable since there's no auth model anyway.

### 2.7 Localhost links — explicit limitation
The Share link feature uses `window.location.origin`, which during development resolves to `http://localhost:5173`. That URL only works on the developer's own machine.

**Why we did not solve "real sharing" in this PR:**
- Real internet sharing requires either (a) a tunnel like Cloudflared / VS Code Dev Tunnels, or (b) a deployed backend + frontend.
- That's a deployment/ops concern, not a product/code concern — and conflates the share-snapshot feature with hosting work.
- The current code is **deployment-ready**: when the app is hosted at a real domain, `window.location.origin` will produce a real shareable URL with zero code changes.

---

## 3. Implementation process

### Step 1 — Audit the existing implementation
Read the existing card, model, route, and storage to understand what was already in place:
- [components/WeeklyReflectionCard.tsx](frontend/src/components/WeeklyReflectionCard.tsx) — already had a `share_text` field and "Copy summary" button.
- [models/reflection.py](backend/app/models/reflection.py) — `WeeklyReflection` Pydantic model already includes `share_text: Optional[str]`.
- [routes/reflection.py](backend/app/routes/reflection.py) — single `GET /reflection/weekly` endpoint.
- [storage.py](backend/app/storage.py) — JSON file pattern used for entries.

This made it clear that:
- Clipboard sharing was already done.
- A "link" feature would require **new storage** (we need to persist snapshots) plus **two new endpoints** and **one new frontend route**.

### Step 2 — Backend: persistent snapshot store
Created [backend/app/routes/shared.py](backend/app/routes/shared.py):
- Helpers `_read_all()` / `_write_all()` over `backend/.data/shared_reflections.json` — same shape as [storage.py](backend/app/storage.py) for `entries.json`.
- `POST /reflection/share` calls the existing `build_weekly_reflection` service against current entries (no duplication of digest logic), generates a 10-char hex id, stores the snapshot keyed by id.
- `GET /shared/{id}` looks up by id, returns the stored `WeeklyReflection` or raises `HTTPException(404)`.
- Registered the router in [backend/app/main.py](backend/app/main.py) under `/api`.

### Step 3 — Frontend API client
Extended [frontend/src/lib/api.ts](frontend/src/lib/api.ts):
- Added `api.reflection.share()` (POST, no body, returns `{id}`).
- Added `api.shared.get(id)`.
- Exposed `createShareLink` and `getSharedReflection` as named exports for ergonomics.

### Step 4 — Share button on the card
Updated [WeeklyReflectionCard.tsx](frontend/src/components/WeeklyReflectionCard.tsx):
- Added two pieces of local state: `sharing` (request in flight) and `linkCopied` (transient confirmation).
- Added a `handleShareLink` async handler that calls `createShareLink()`, constructs `${window.location.origin}/shared/${id}`, and writes that URL to the clipboard.
- Wrapped the existing "Copy summary" button in a `<div className="flex gap-2">` and added the new "Share link" button beside it.
- Both buttons share the same conditional render guard (`data.share_text` exists), since both are meaningless without a real summary.

### Step 5 — Public viewer page
Created [SharedReflection.tsx](frontend/src/pages/SharedReflection.tsx):
- Pulls `:id` via `useParams` (already had `react-router-dom` v6).
- Calls `getSharedReflection(id)`; handles loading / not-found / success states.
- Renders a stripped-down version of the card: window range, the three KPIs (avg mood/energy/trend), top tags, narrative, and the raw `share_text` in a `<pre>` block so the recipient can copy it.
- Intentionally **does not** include the "Copy summary" or "Share link" buttons — the recipient isn't the author.

### Step 6 — Router wiring
Added the route to [App.tsx](frontend/src/App.tsx): `<Route path="/shared/:id" element={<SharedReflection />} />`. Imported the new page.

### Step 7 — Verification
- Restarted the FastAPI backend to load the new router.
- Hit `POST /api/reflection/share` via `curl`, confirmed it returned `{"id": "37d9449cf0"}`.
- Confirmed `get_errors` returned clean on all touched files (no TS / Python diagnostics).

---

## 4. How to use

1. Open `http://localhost:5173/` and ensure the **Weekly Reflection** card is visible at the top of the Dashboard.
2. Click **Share link** (right side of the card header).
3. The button briefly says "Sharing…" then "Link copied!" — the URL is now on your clipboard.
4. Paste it into another browser tab (or send to a colleague if your dev server is exposed via a tunnel) to view the frozen snapshot.

To verify the snapshot is actually frozen: share a link, then log a new entry, then revisit the shared URL — the numbers will be unchanged.

---

## 5. Known limitations & future work

| Area | Limitation | Suggested follow-up |
| --- | --- | --- |
| **Hosting** | Links are `localhost` in dev. | Document a "Share publicly" path: VS Code Dev Tunnels, Cloudflared, or deploy. |
| **Expiry** | Snapshots live forever. | Add `expires_at` and a periodic cleanup, or a TTL of e.g. 30 days. |
| **Revocation** | No way to invalidate a shared link. | Add `DELETE /api/shared/{id}` + a "Manage shared links" UI. |
| **Multi-user** | App is single-user; any visitor can mint a share link from your data. | Out of scope until an auth model exists. |
| **Concurrency** | JSON file storage is not safe under concurrent writers. | Move to SQLite if the app ever serves real concurrent traffic. |
| **Discoverability of one's own shares** | The user can't list previously shared links. | Add `GET /api/reflection/shares` returning ids + `created_at`. |
| **Tests** | No new automated tests were added. | Add a backend test that POSTs `/reflection/share`, then GETs `/shared/{id}` and asserts the payload matches the live `/reflection/weekly` output captured at that instant. |
