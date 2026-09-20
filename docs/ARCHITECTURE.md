# Architecture

## Layers

| Layer | Files | Responsibility |
| --- | --- | --- |
| Interface | `bot/handlers.py`, `bot/keyboards.py`, `bot/texts.py` | Telegram I/O only. No business logic, no Notion calls. |
| Reasoning | `core/agent.py` | The model -> tool -> model loop, system prompt, iteration limit. |
| Action | `core/tools.py` | Ten finance tools plus the JSON schemas exposed to the model. |
| Integration | `core/notion_client.py`, `core/workspace.py` | Notion REST calls and the database template. |
| State | `core/users.py`, `core/memory.py`, `core/tool_log.py` | Persistent profiles, short-term dialogue window, tool call journal. |
| Runtime | `main.py`, `config/settings.py` | Process startup, health endpoint, environment configuration. |

## Path of one message

1. `bot/handlers.on_text` receives the text and checks the access guard and profile readiness.
2. The short-term history is taken from `core/memory.py`.
3. `core/agent.respond` sends system prompt + history + message + tool schemas to the model.
4. If the model answers with `tool_calls`, each call is executed by `core/tools.FinanceTools.call`.
5. Every call is timed and written to `core/tool_log.py` together with its `ok` flag.
6. The tool result is appended to the message list and the model is called again.
7. The loop ends when the model returns plain text or when `MAX_TOOL_ITERATIONS` is reached.

## Multi-tenancy

`core/users.py` stores one `UserProfile` per Telegram id: Notion token, parent page id and the
four database ids. `FinanceTools` builds a `NotionClient` from that profile, so two users never
share a client, a token or a database. Nothing user-specific exists in `config/settings.py`.

## Cognitive function to source file map

| Cognitive function | Where it lives |
| --- | --- |
| Perception | `bot/handlers.py` (input channel), LLM parsing of free text into tool arguments |
| Attention | `core/agent.SYSTEM_PROMPT`, `core/memory.MAX_TURNS`, tool selection |
| Memory | `core/memory.py` (short term), `core/users.py` and Notion databases (long term) |
| Knowledge representation | `core/workspace.FIELDS`, `core/tools.TOOLS_SCHEMA` |
| Learning | absent by design, see the report |
| Reasoning | the iterative loop in `core/agent.respond` |
| Decision making | choice of tool and arguments inside that loop |
| Planning | multi-step chains, e.g. `list_accounts` -> `add_expense` -> balance update |
| Communication | `bot/texts.py`, prompt formatting rules 6 and 7 |
| Self-evaluation | `core/tool_log.py`, `/status`, `/trace`, prompt rule 2 |

## Deliberate limitations

* No vector store and no retrieval: the model sees only the last twelve turns.
* No fine-tuning and no weight updates: behaviour between sessions is identical.
* No autonomous actions: the agent acts only in response to a user message.
* No background scheduler in this version, so there is no self-initiated behaviour.
