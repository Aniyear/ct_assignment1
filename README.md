# Personal CFO Agent

A multi-tenant personal finance assistant: a Telegram bot that talks to an LLM, calls
financial tools and stores everything in **the user's own Notion workspace**.

Built for the course **Cognitive Technologies**, Practical Assignment 1.
Team: Aniyar Baibossyn, Salamat Sagyndykov, Shynggys Saiduldinov.

## What it can do

* Understands free-form messages: `spent 3500 on groceries with Kaspi`, `salary 400000 to Kaspi`
* Saves expenses and incomes as Notion rows and automatically adjusts account balances
* Answers analytical questions: `how much did I spend this month`, `top categories`
* Edits and deletes previous records found by name
* Gives saving advice based on real numbers, not guesses
* Exposes its own behaviour: `/status` (state and tool statistics) and `/trace` (last actions)
* Works with any OpenAI-compatible model provider, switched by one environment variable

## Architecture at a glance

```
Telegram  ->  bot/handlers.py        interface layer, no business logic
          ->  core/agent.py          model -> tool -> model loop (decision making)
          ->  core/tools.py          10 finance tools, each returns ok=true/false
          ->  core/notion_client.py  thin Notion API client, one per user
          ->  Notion databases       long-term memory

core/users.py      per-user profiles: token + database ids  (multi-tenancy)
core/memory.py     short-term sliding window of the dialogue
core/tool_log.py   log of every tool call (basis for self-evaluation)
```

See `docs/ARCHITECTURE.md` for the mapping between cognitive functions and source files,
and `docs/REPORT_Assignment1.md` for the full assignment report.

## Setup

### 1. Install

```bash
git clone https://github.com/Aniyear/ct_assignment1.git
cd ct_assignment1
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

### 2. Configure

Copy `.env.example` to `.env`. Two things are required: the Telegram bot token from
@BotFather, and an API key for one model provider.

### 3. Choose a model provider

The agent speaks the OpenAI chat-completions protocol, so the provider is pure configuration.
Set `AI_PROVIDER` and fill in only the matching key.

| `AI_PROVIDER` | Key variable | Where to get the key | Default model |
| --- | --- | --- | --- |
| `openrouter` (default) | `OPENROUTER_API_KEY` | openrouter.ai/keys | `deepseek/deepseek-chat` |
| `gemini` | `GEMINI_API_KEY` | aistudio.google.com/apikey | `gemini-2.0-flash` |
| `groq` | `GROQ_API_KEY` | console.groq.com/keys | `llama-3.3-70b-versatile` |
| `custom` | `LLM_API_KEY` | any OpenAI-compatible service | set `LLM_MODEL` and `LLM_BASE_URL` yourself |

**Google Gemini example** — this is all you need in `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:ABC...
AI_PROVIDER=gemini
GEMINI_API_KEY=AIza...
```

The base URL and the model are filled in from the preset
(`https://generativelanguage.googleapis.com/v1beta/openai`, `gemini-2.0-flash`).
To pick another Gemini model, add `LLM_MODEL=gemini-2.5-flash` — `LLM_MODEL` and
`LLM_BASE_URL` always override the preset.

> The model **must support function calling**, otherwise the agent cannot write to Notion.
> `gemini-2.0-flash`, `gemini-2.5-flash` and `deepseek/deepseek-chat` all do. Free tiers have
> rate limits, so a long tool chain may occasionally hit a 429.

Other optional variables (`LLM_TIMEOUT`, `MAX_TOOL_ITERATIONS`, `USERS_FILE`,
`ALLOWED_USER_IDS`, `DEFAULT_CURRENCY`, `TIMEZONE`, `PORT`) are documented in `.env.example`.

### 4. Run

```bash
python main.py
```

If a required variable is missing, the process exits immediately and names it.

### 5. Connect Notion (done by each user inside the bot)

1. Open `notion.so/my-integrations`, create an integration, copy the Internal Integration Secret (`ntn_...`).
2. In the bot: `/connect ntn_...` (then delete that message from the chat).
3. Create an empty Notion page, open `...` -> **Connections** -> add your integration.
4. In the bot: `/setup <page link>`. The bot creates four databases and seeds 15 categories.
5. Start writing: `add an account Card with balance 100000`, then `spent 2000 on coffee from Card`.

## Commands

| Command | Purpose |
| --- | --- |
| `/start`, `/help` | onboarding and examples |
| `/connect <token>` | connect a personal Notion integration |
| `/setup <page link>` | create the four databases |
| `/status` | connection state, model, tool statistics |
| `/trace` | the last ten tool calls with success flags and timings |
| `/forget` | clear the short-term conversation memory |
| `/disconnect` | delete the stored profile and token |

## Data model created by /setup

| Database | Key properties |
| --- | --- |
| Finance - Expenses | Name, Amount, Date, Notes, Category (relation), Account (relation) |
| Finance - Incomes | Source, Amount, Date, Notes, Account (relation) |
| Finance - Accounts | Name, Balance, Currency |
| Finance - Categories | Name, Kind (expense / income) |

## Security notes

* Tokens are never committed: `.env` and `data/` are in `.gitignore`
* A Notion integration only sees the pages explicitly shared with it
* `/status` shows a masked token only (`ntn_123...abcd`)
