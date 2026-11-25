# TestOps - walkthrough for the team, 25 November 2026

**https://<container-app-domain>.azurecontainerapps.io/**

Seven minutes, five pages, one point: *a finding is evidence, and you can check it without trusting us.*

## 1. The corpus (30 s)

Open the home page. Say what it is: **41 analysis runs, 226 case pages** from real repositories - demo-booking-platform
(Java + Cypress), Demo Product, demo-service. Nothing here was typed in by hand; each page is rendered from rows a run stored.

Do not apologise for it being read-only. Say why: the analysis needs GitHub and a token, and they are not in the image on
purpose.

## 2. One case, with the agent off (2 min)

`/case/case-demo-booking-levels-20261124T123451-05`

Read the verdict aloud: **"Checked, but the product already exposes this."** Then walk down the page:

- **The source band** - `142 .java parsed, 25 surfaces (routes and engine modules) · consulted`, with links to the product
  repo and the test repo at the exact commit.
- **The test line** - `room-management.feature:15`, marked, at commit `fe8537db`.
- **The product line** - `RoomController.java:42`, the `@RequestMapping` and the `createRoom` signature, marked, at commit
  `efe2deb8`.
- **The caption that admits what it hides** - *"The signature is 2 of 6 lines of this declaration (lines 42-43); the other 4
  lines are the body, which this page does not print."*

The point to say out loud: **the tool shows both sides of its own argument.** You do not have to take the verdict on faith;
the page is the evidence.

## 3. The same case, two agents (2 min)

Add `?agent=foundry` and the explanation is written by the **hosted Foundry agent** `testops-narrator`, which calls
`deepseek-flash` with its own managed identity. The block says so: *written by the Foundry hosted agent*, and
*served by: foundry-hosted-agent*.

Add `?agent=on` and the same block is written by this build's own model call.

- The block is **labelled**: written by the model (or the agent) from the stored record, "commentary, not evidence".
- The verdict above it is **byte-identical** to the agent-off page. That is enforced by a test over all 275 real pages.
- The explanation names what the finding means and what to do about it in plain English.

Say the honest thing about the guard: **every sentence must cite a record identifier, and a fact that disagrees with the
cited row kills the reply.** Three of ten real replies currently come back without citations and are repaired or discarded -
which is the next slide's point, not a secret.

## 4. The meter (1.5 min)

`/agent-report`

- The routes side by side: the model route and the hosted agent, with calls, tokens and failures by kind.
- Views, explanations, **rejected**, failed, cache hits, tokens - broken down **by state**, so a cached page is not counted
  as an explanation's value and a failure is not counted as a loss.
- Tokens are the provider's own usage figures. **No price is invented on the page**; cost is measured in tokens, and a price
  enters from the provider's list.
- Measured today: **~1,470 tokens in, ~253 out, 3.2 s per explanation.**
- Two links on every explanation: *"This helped" / "This did not."* That is the other half of the A/B.

The argument: **this is how you decide whether an agent earns its place** - views against votes against tokens, not a demo
that looked good once.

## 5. Can this deployment reach a model? (30 s)

`/agent-check`

Plain page: endpoint, model, whether a token exists (never its value), and the actual probe rows. Useful if someone asks
"what happens when the model is down" - the answer is *the page falls back and says why*, and you can show it.

## Questions you will be asked

**"Why isn't this in Foundry?"**
Foundry hosts models and agents behind an API. This is a website; it runs on Container Apps. The model it calls **is** in
Foundry - project `<foundry-account>`, deployment `deepseek-flash`. Same subscription, two different services doing what each
is for.

**"Is the verdict the model's opinion?"**
No. The verdict is deterministic rules over stored rows; two runs on the same commit produce the same finding. The model
writes commentary on top and cannot change the verdict - switching it off leaves the page byte-identical.

**"What does it cost?"**
Tokens per explanation are on `/agent-report`. At the measured rate, a case explanation is on the order of a few hundred
thousandths of a dollar; the page states tokens rather than a price because the price is a provider list we have not
verified.

**"Is it secure?"**
Public URL, no login, public repository data only. One replica, 0.25 vCPU. Say so plainly.

**"What happens when it's wrong?"**
The page shows the test line, the product line and the word they share. A reader can disagree with the finding in ten
seconds, which is the point.
