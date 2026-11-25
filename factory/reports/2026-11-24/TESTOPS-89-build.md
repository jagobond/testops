# TESTOPS-89 build report - the missing token now says why it is missing

Branch `factory/testops-89-agent-check`. Session date 2026-11-24.

## What was wrong

`managed_identity_token()` asked IMDS once, at `api-version=2018-02-01`, with a three-second
timeout, and threw the exception away. Whatever the deployment replied, the tool could only say
"no token". The identity, the role assignment and the endpoint were all fine; the lookup was blind.

## The cause in the deployed container (AC4) - determined, not narrowed

A new revision was deployed (`testops--0000004`, image `testopsdemo30562.azurecr.io/testops:20261124-161320`)
carrying this change, and `/agent-check` was read from the live app. Its own words:

    No explanation would be served right now: the metadata service did not answer (unreachable)
    and no az CLI is on this PATH.

    Managed identity (IMDS)   did not answer (unreachable)
    The az CLI                 no az CLI on this PATH
    Token in the environment   no

    api-version  Attempt  Status  Error code  Exception  Detail                                       Elapsed
    2018-02-01   1        -       -           URLError   <urlopen error [Errno 111] Connection refused>  15
    2018-02-01   2        -       -           URLError   <urlopen error [Errno 111] Connection refused>   0
    2019-08-01   1        -       -           URLError   <urlopen error [Errno 111] Connection refused>   0
    2019-08-01   2        -       -           URLError   <urlopen error [Errno 111] Connection refused>   0

So the cause is not the api-version, not the timeout and not the identity: **the container's network
path refuses TCP to `169.254.169.254:80` outright** (`ECONNREFUSED`, answered in 15 ms on the first
attempt and ~0 ms after - a reset, not a timeout or a route black hole). Both api-versions, both
attempts. The image is `python:3.12-slim`, which has no `az` CLI, so the documented second path was
never available either. Nothing in the token code could have changed that; only the diagnosis could.

The ledger row was read back from the live app: the diagnosis is stored as `agent_token_probe` row 2,
beside the calls and views.

## What changed

- `testops/judgement/client.py` - `probe_identity()` replaces the single blind request. Both
  `2018-02-01` and `2019-08-01` are tried; a transport failure is retried once per api-version; a
  definitive answer (4xx) is not retried but moves to the next api-version; the timeout is 10 s. Each
  attempt records api-version, attempt number, status, the response body's error code (both the IMDS
  `{"error": "...", "error_description": "..."}` shape and the ARM `{"error": {"code": ...}}` shape),
  exception class, detail and elapsed ms. `Probe.as_dict()` - the only form ever cached, stored or
  rendered - has no token field at all. `az_token()` now records whether `az` was present, whether it
  answered and why not.
- `testops/store/schema.sql` - additive table `agent_token_probe`, one row per lookup, no column that
  can hold a token. Created on open by the existing `executescript`; no schema version bump, no row
  rewritten (same pattern as TESTOPS-88's tables).
- `testops/judgement/agent.py` - the token cache now keeps the probe beside the token; `diagnosis()`
  reports endpoint, endpoint variable, model, model variable, `environment_token` as a yes/no, the
  IMDS probe and the `az` probe; `served_sentence()` is the one top sentence; `record_diagnosis()`
  writes the ledger row; a case page that finds no token records the probe it already paid for, so
  the reason reaches the store even if nobody opens `/agent-check`.
- `testops/web/app.py` - `/agent-check`: the sentence, the configuration, IMDS and `az` in words, and
  every attempt as a table row. `?refresh=1` resolves the token afresh. Linked from `/agent-report`.
- `testops/judgement/client.py` - `TESTOPS_FOUNDRY_ENDPOINT` is now read as an endpoint setting
  beside `TESTOPS_AGENT_ENDPOINT`. **This was a real second finding:** the documented deployment sets
  `TESTOPS_FOUNDRY_ENDPOINT`, and the build only read `TESTOPS_AGENT_ENDPOINT`. The demo worked by
  coincidence - the derived default URL happens to be the same string. The page now names the
  variable that configured it, so this could not have stayed invisible.

## The token on the page, in a log line, in the ledger (AC3)

Structural, and pinned. The probe hands `as_dict()` around; the token lives only on the dataclass in
the frame that asked for it. `tests/test_agent_check.py` feeds a known token through the environment
and asserts that no eight-character window of it appears in the rendered page or in any
`agent_token_probe` row.

## Verification

    env -u PYTHONPATH -u VIRTUAL_ENV -u CONDA_PREFIX PYTHONNOUSERSITE=1 \
      C:/Users/<name>/Projects/testops/.venv/Scripts/python.exe -m pytest -q
    1342 passed, 2 skipped in 281.56s (EXIT=0)

That includes the AC5 gates as they already stood: `test_every_real_case_page_is_byte_identical_to_the_pre_change_build`
(all 275 real case and run pages) and the page contracts. The TESTOPS-88 citation validator was not
touched: `explain_case` gained one line on its unconfigured branch and nothing on the reply path.

New tests (10): api-versions and 10 s/one-retry constants; a 400 body's error code recorded and not
retried; the ARM-shaped body; one retry per api-version on transport failure; which version and
attempt answered; the `Metadata: true` header and the timeout actually passed; the page stating each
fact; the no-token-substring gate; the case page recording the probe it paid for; nothing recorded
when nothing was probed.

The two failures seen mid-build were mine and are fixed: a backslash inside an f-string expression
(the 3.11 floor test) and an over-long assertion string.

## Left for the Lead - not done here, because each is a product decision

1. **The app cannot reach IMDS.** Unless the platform is made to serve it, the token has to arrive
   another way. Two candidates, in order: (a) Container Apps also exposes the App Service-style
   identity endpoint through the `IDENTITY_ENDPOINT`/`IDENTITY_HEADER` environment variables - a
   probe for those is the obvious next ticket and is a few lines in `client.py`; (b) set
   `TESTOPS_AGENT_TOKEN` from a Container Apps secret, which needs a shorter-lived token and a
   refresh story. Worth confirming (a) against the live app before building it.
2. The demo now runs revision `testops--0000004`; the previous revision can be deactivated if the
   walkthrough needs the old behaviour.
