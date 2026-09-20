"""Static texts. The whole interface is plain text without markdown markup."""

WELCOME = """👋 Hi! I am your personal finance assistant.

I save your expenses and incomes into your own Notion workspace and show where the money goes.

Two steps to get started:

1️⃣ Create a Notion integration at notion.so/my-integrations and copy the secret (it starts with ntn_).
Send me: /connect ntn_your_token

2️⃣ Create an empty page in Notion, open the "..." menu, choose Connections and pick your integration.
Then send me: /setup page_link

I will create the Expenses, Incomes, Accounts and Categories databases there myself."""

HELP = """❓ What I can do

• "spent 3500 on groceries with Kaspi" — I save the expense and subtract it from the account
• "got my salary 400000 to Kaspi" — I save the income
• "add an account Cash with balance 20000"
• "how much did I spend this month"
• "change the category of the taxi record to Transport"
• "where can I save money"

Commands:
• /connect — connect your Notion
• /setup — create the databases from the template
• /status — what is connected
• /trace — my latest actions
• /forget — clear the conversation context
• /disconnect — delete my profile"""

NEED_CONNECT = "🔑 Connect Notion first: /connect ntn_your_token"
NEED_SETUP = "📚 One step left: /setup notion_page_link"
NOT_ALLOWED = "⛔ This bot is private. Ask the owner to add your ID to ALLOWED_USER_IDS."
