# Deploying TestOps

Every value below is read from the environment. None of them is in the source, and an unset one is
either a default that means something (a port, a timeout) or an honest *unconfigured* state that
names the variable. Values here are placeholders: replace them, never commit the replacements.

## The web application

| variable | placeholder | what it is for |
|---|---|---|
| `TESTOPS_FOUNDRY_ACCOUNT` | `<account>` | The Foundry account. The first half of a derived model or agent address; unset means the route is unconfigured. |
| `TESTOPS_AGENT_PROJECT` | `<project>` | The project inside that account. The second half of the derived address; unset means the route is unconfigured. |
| `TESTOPS_AGENT_ENDPOINT` | `https://<host>/openai/v1/chat/completions` | An explicit chat-completions address for the model route. Wins over the derived form. |
| `TESTOPS_FOUNDRY_ENDPOINT` | `https://<host>/openai/v1/chat/completions` | The same override under the name the Container Apps deployment uses. Ignored when `TESTOPS_AGENT_ENDPOINT` is set. |
| `TESTOPS_AGENT_ROUTE_ENDPOINT` | `https://<host>/agents/<agent>/endpoint/protocols/openai/responses?api-version=v1` | An explicit address for the hosted-agent route. Separate from the model route's variable on purpose: one variable with two meanings would let a deployment configure one route and believe it had configured two. |
| `TESTOPS_AGENT_MODEL` | `<model-deployment-name>` | The model name sent in each request. Defaults to `deepseek-flash`. |
| `TESTOPS_AGENT_NAME` | `<agent-name>` | The hosted agent's name inside the project. Defaults to `testops-narrator`, which is the name this repository deploys. |
| `TESTOPS_AGENT_TIMEOUT` | `20` | Seconds the page waits for the hosted agent before saying it took too long. A non-positive or unreadable value falls back to 20. |
| `TESTOPS_AGENT_TOKEN` | `<token>` | The credential for both routes: the bearer token for the model route, the `api-key` for the hosted agent. Never read from `.env`, never logged, never rendered. |
| `TESTOPS_AGENT_CLIENT_ID` | `<client-id>` | A user-assigned managed identity's client id, for the metadata-service lookup. Unset means the machine's default identity. |
| `TESTOPS_AGENT_FALLBACK` | `model` | Set to `model` to let a failed hosted-agent call be answered by the model route. Unset means a failure stays a failure. |
| `TESTOPS_DATA` | `/data` | The directory holding the evidence store and its blobs. Defaults to `data`; a container mounts a volume here. |
| `TESTOPS_HOME` | `/app` | The base directory relative settings are resolved from. Empty means the process's working directory. |
| `TESTOPS_ENV` | `/run/secrets/testops.env` | The file secrets are read from at call time. Defaults to `.env`, which is never committed. |

## The hosted agent (`agents/narrator`)

Set as environment variables on the agent's own definition, not on the web application.

| variable | placeholder | what it is for |
|---|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | `https://<account>.services.ai.azure.com/api/projects/<project>` | The project endpoint the agent calls the model through. Required: the agent refuses to start without it. |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | `<model-deployment-name>` | The model deployment the agent asks. Defaults to `deepseek-flash`. |
| `PORT` | `8088` | The port the agent's own server listens on. |
| `IDENTITY_ENDPOINT` | injected by the platform | The instance metadata endpoint the agent asks for a token. |
| `IDENTITY_HEADER` | injected by the platform | The header the instance metadata endpoint requires. |
| `FOUNDRY_AGENT_INSTANCE_CLIENT_ID` | injected by the platform | The agent's own instance identity, when the endpoint issues tokens for more than one. |

`agents/narrator/deploy.py` reads two variables of its own and exits with a named error when either
is unset:

| variable | placeholder | what it is for |
|---|---|---|
| `TESTOPS_PROJECT_ENDPOINT` | `https://<account>.services.ai.azure.com/api/projects/<project>` | The project to create the agent version in. |
| `TESTOPS_AGENT_NAME` | `<agent-name>` | The agent to deploy. |

## Tooling

| variable | placeholder | what it is for |
|---|---|---|
| `AZURE_SUBSCRIPTION_ID` | `<subscription-id>` | The subscription `cost_probe.py` prices and `scripts/draw_azure_diagram.py` labels. Both refuse to run without it. |
| `AZURE_DEVOPS_PAT` | `<token>` | Read by the scratch collectors in `scripts/t_*.py` when they are pointed at an Azure DevOps board. Optional; nothing on the page reads it. |
| `TESTOPS_FLOOR_PYTHON` | `/usr/bin/python3.11` | Optional: a Python 3.11 an operator wants `tests/test_python_floor.py` to run its guards against, in addition to whatever 3.11 is on `PATH`. |

## What "unconfigured" means

With `TESTOPS_FOUNDRY_ACCOUNT` or `TESTOPS_AGENT_PROJECT` absent, no address is derived: the model
route and the hosted-agent route report themselves unconfigured, `/agent-check` names the variable
that is missing, and a case page serves its ordinary agent-off page. The application still starts,
still serves evidence, and never falls back to an address nobody configured.
