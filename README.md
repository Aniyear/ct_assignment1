# Personal CFO Agent

A multi-tenant personal finance assistant: a Telegram bot that talks to an LLM, calls
financial tools and stores everything in **the user's own Notion workspace**.

Built for the course **Cognitive Technologies**, Practical Assignment 1.
Team: Aniyar Baibossyn, Salamat Sagyndykov, Shynggys Saiduldinov.

## Why this project

A typical hobby Telegram bot hard-codes one owner: one Notion token, one set of database
IDs in environment variables. This project removes that coupling. Any person can start the
same bot, connect **their own** Notion and get their own private set of databases created
automatically. Nothing about the owner is baked into the code.

## What it can do

* Understands free-form messages: `spent 3500 on groceries with Kaspi`, `salary 400000 to Kaspi`
* Saves expenses and incomes as Notion rows and automatically adjusts account balances
* Answers analytical questions: `how much did I spend this month`, `top categories`
* Edits and deletes previous records found by name
* Gives saving advice based on real numbers, not guesses
* Exposes its own behaviour: `/status` (state and tool statistics) and `/trace` (last actions)

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

Copy `.env.example` to `.env` and fill in two required values:

| Variable | Where to get it |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | @BotFather in Telegram, command `/newbot` |
| `OPENROUTER_API_KEY` | openrouter.ai -> Keys -> Create key |

Optional values (`OPENROUTER_MODEL`, `LLM_BASE_URL`, `USERS_FILE`, `ALLOWED_USER_IDS`,
`DEFAULT_CURRENCY`, `TIMEZONE`, `PORT`) are documented inside `.env.example`.

**Any OpenAI-compatible provider works.** Examples:

```env
# free models through OpenRouter
OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

# or Google AI Studio directly
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENROUTER_API_KEY=<Google AI Studio key>
OPENROUTER_MODEL=gemini-2.0-flash
```

The model **must support function calling**, otherwise the agent cannot write to Notion.

### 3. Run

```bash
python main.py
```

### 4. Connect Notion (done by each user inside the bot)

1. Open `notion.so/my-integrations`, create an integration, copy the Internal Integration Secret (`ntn_...`).
2. In the bot: `/connect ntn_...` (then delete that message from the chat).
3. Create an empty Notion page, open `...` -> **Connections** -> add your integration.
4. In the bot: `/setup <page link>`. The bot creates four databases and seeds 15 categories.
5. Start writing: `add an account Card with balance 100000`, then `spent 2000 on coffee from Card`.

## Deploying on Render

* Type: **Web Service**, Build Command `pip install -r requirements.txt`, Start Command `python main.py`
* Add the same environment variables
* Attach a **Disk** and set `USERS_FILE=/var/data/users.json`, otherwise user profiles are erased on every deploy
* The built-in health endpoints `/` and `/health` keep the service alive

## Giving the bot to other people

Nothing extra is needed: every user runs `/connect` and `/setup` with their own Notion, and
profiles are isolated by Telegram user id. To restrict access, list allowed ids in
`ALLOWED_USER_IDS`. To leave, a user sends `/disconnect`, which deletes the stored token.

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
