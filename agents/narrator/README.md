# testops-narrator - the hosted Foundry agent

Source for the hosted agent the `?agent=foundry` route calls. Deployed from a zip of this directory
(`main.py` and `requirements.txt` at the root) with `deploy.py`.

## What it does, and does not do

It takes `{"system": ..., "user": ...}` as the Responses input, asks the `deepseek-flash` deployment for an
explanation, and returns the model's reply verbatim plus a final line:

    USAGE {"prompt_tokens": n, "completion_tokens": n, "model": ..., "served_by": "foundry-hosted-agent",
           "token_source": "instance-endpoint", "attempts": n}

It decides nothing. The citation guard, the verdict and the case state stay in TestOps, so the agent's prose is
screened by the same code as the model route's.

## The three things that cost an evening

1. **`DefaultAzureCredential` resolves to the agent blueprint identity, which cannot be given roles**
   (`PrincipalTypeNotSupported`). The identity that holds the role assignments is the *instance* identity,
   `FOUNDRY_AGENT_INSTANCE_CLIENT_ID`. The token is minted from the platform endpoint the runtime injects:
   `GET $IDENTITY_ENDPOINT?resource=https://ai.azure.com&api-version=2019-08-01&client_id=$FOUNDRY_AGENT_INSTANCE_CLIENT_ID`
   with `X-IDENTITY-HEADER: $IDENTITY_HEADER`. The classic `169.254.169.254` metadata address is refused here.
2. **The audience must be `https://ai.azure.com`** for the project-scoped model route. Asking for
   `cognitiveservices.azure.com` returns a 401 whose message names the wrong audience only if you are lucky.
3. **The first call of a fresh session can 401 while the instance identity warms up**, then succeed seconds later.
   `_model` retries up to three times and reports `attempts` in the USAGE line, so the behaviour is visible rather
   than papered over. Measured: 6/6 successful after the retry was added.

## Deploying

    ENV: az login (or a session with role access on the account)
    python deploy.py            # uses ../.venv only if azure-ai-projects is installed there

The agent name is `testops-narrator`; invocation is
`POST .../agents/testops-narrator/endpoint/protocols/openai/responses?api-version=v1`
with either `api-key:` (the Cognitive Services key) or an Entra bearer token.
