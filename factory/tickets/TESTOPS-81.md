---
id: TESTOPS-81
title: A bare POST / is not a route a reader can act on - name the service
feature: F1
status: ready
autonomy: build
depends_on: TESTOPS-70
---

# TESTOPS-81 - "POST /" appears three times and means three different routes

## Why this exists

The first real corpus run gives advice a developer cannot follow:

    The test asserts the step ... will be created through a browser, but the product already declares POST /,
    so the check re-verifies work the developer has already done.
    What to do: Assert this at the API: call POST / and check the response.

`POST /` is literally what the source says - `RoomController` has no class-level prefix and writes
`@RequestMapping(value = "/", method = RequestMethod.POST)` - but the platform mounts each module under its own path, so
the servable route is `/room`. The corpus holds **three** `POST /` surfaces (booking, message, room) and **five**
`GET /{id:[0-9]*}` surfaces across different services, distinguished only by the file they came from. A reader given
`GET /{id:[0-9]*}` without the service cannot tell which route it is, and the advice to "call it" is unactionable.

## Acceptance criteria

| id | criterion |
|----|-----------|
| AC1 | Every route a page shows carries the **module or service** it belongs to, taken from the source path (`room`, `booking`, `message`, `auth`, `branding`, `report`), rendered as a qualifier: `POST / in the room service`. Where the reader cannot tell the module, it says so rather than guessing. |
| AC2 | The advice sentence uses the qualified route, so "call `POST / in the room service` and check the response" is something a person can do. Pinned by a page test. |
| AC3 | The unqualified route is still recorded on the claim as the reader read it, so the evidence remains faithful to the source; only the page adds the qualifier. No route may be rewritten. |
| AC4 | Ambiguity is visible: three surfaces named `POST /` must be distinguishable in any list a reader sees (run page, case page), and a test asserts that two surfaces from different modules never render identically. |
| AC5 | Full suite green; contract suite green; goldens regenerated deliberately and listed. |
