# Practical Assignment 1
## Analysis of the Cognitive Functions of a Modern AI System

**Course:** Cognitive Technologies, Master's programme, year 2
**Team:** Aniyar Baibossyn, Salamat Sagyndykov, Shynggys Saiduldinov
**System under analysis:** Personal CFO Agent, a Telegram-based personal finance assistant
**Repository:** https://github.com/Aniyear/ct_assignment1

---

## 1. Choice of the system and justification

Instead of analysing a closed commercial product such as ChatGPT, Siri or Alexa, we analyse a
system designed and implemented by our team. The assignment permits a custom system when the
choice is justified. Our justification has three parts.

1. **Full observability.** For a closed product we could only speculate about its internal
   mechanisms, because the architecture is not published. Here every claim can be supported by
   a specific file, function or constant in the source code.
2. **It is a real working prototype, not a mock-up.** The system contains an LLM-based
   reasoning loop, ten executable tools, persistent external storage in Notion, a multi-user
   profile layer and an introspection layer. It is a representative instance of the class
   "LLM agent with tools", which is the dominant form of applied AI systems today.
3. **Verifiability.** Each verdict in section 3 can be reproduced: run the bot, send a message
   and inspect `/trace`, which prints the actual sequence of internal actions.

---

## 2. Brief description of the system

**Purpose.** To remove the friction of personal accounting. The user writes an ordinary
sentence in a messenger, and the system converts it into structured financial records and
analytical answers.

**Users.** Private individuals who keep personal finances. The system is multi-tenant: each
user connects their own Notion workspace, so there is no shared data between users.

**Inputs.** Natural-language text messages in Telegram (Russian, English or mixed), button
presses that expand into pre-written prompts, and slash commands (`/connect`, `/setup`,
`/status`, `/trace`, `/forget`, `/disconnect`).

**Outputs.** Plain-text replies in Telegram, and side effects in the external world: new and
modified rows in four Notion databases, recalculated account balances, and entries in the
internal tool-call log.

**Domain.** Personal finance: expenses, incomes, accounts, categories, period summaries and
saving advice. The domain is intentionally narrow, which is important for the analysis below:
the boundaries of competence are defined by the tool set, not by the model.

**Technology stack.** Python 3.11+, aiogram 3 (Telegram), an OpenAI-compatible LLM endpoint
(OpenRouter, Google AI Studio and similar), the Notion REST API v2022-06-28, aiohttp for the
health endpoint, JSON file storage for user profiles.

**Architecture type.** A ReAct-style LLM agent with function calling: the model observes,
chooses a tool, receives the result and repeats until it can answer. It is deliberately **not**
a classical cognitive architecture such as SOAR or ACT-R: there is no production-rule memory,
no chunking, no goal stack maintained by the system itself.

```
Telegram -> handlers -> agent loop -> tools -> Notion
                          ^             |
                          +-- results ---+
```

---

## 3. Analysis of cognitive functions

### 3.1 Perception - Partially

**How it is implemented.** The only sensory channel is text. `bot/handlers.on_text` receives
the message; the LLM performs the actual interpretation, extracting entities from free text:
amount, object of spending, category, account and date. The sentence "spent 3500 on groceries
with Kaspi" becomes `add_expense(amount=3500, title="groceries", category="Groceries",
account="Kaspi")`.

**Evidence.** The mapping is visible in `/trace`, which prints the tool name and the arguments
that were actually produced from the sentence. The extraction is not rule-based: there are no
regular expressions for amounts in the code, so the interpretation step is genuinely performed
by the model.

**Limitations.** One modality only. Voice, photographs of receipts and PDF statements are not
perceived. There is no perception of the environment: the system does not know the time of
day, the user's location or anything not written in the message. Perception is also passive:
nothing is perceived until the user speaks.

### 3.2 Attention - Partially

**How it is implemented.** Three mechanisms filter what the system processes. First, the system
prompt in `core/agent.py` narrows the scope to finance and forbids inventing numbers. Second,
`core/memory.MAX_TURNS = 12` bounds the context window, so older turns are dropped. Third, the
model performs selective tool choice: out of ten available tools only the relevant ones are
called, which is a form of task-relevant focus.

**Evidence.** For the request "how much did I spend this month" the log shows a single
`summary` call rather than all ten tools; irrelevant capabilities are ignored.

**Limitations.** Attention is not adaptive and not learned. The window size is a hard-coded
constant, not the result of a salience computation. The system cannot decide that an unusually
large expense deserves more processing than a routine one; there is no notion of salience at
all.

### 3.3 Memory - Partially

**How it is implemented.** Four distinct levels exist.

| Level | Mechanism | Lifetime |
| --- | --- | --- |
| Working memory | the `messages` list built in `agent.respond` | one request |
| Short-term memory | `core/memory.py`, sliding window of 12 turns | process lifetime |
| Long-term episodic memory | rows in the Notion databases | permanent |
| Configuration memory | `core/users.py`, JSON profiles | permanent |

**Evidence.** After a restart the conversation context is gone, but every expense remains in
Notion and the user does not need to reconnect: the profile was flushed to disk atomically
(`tmp` file plus `os.replace`).

**Limitations.** This is storage, not memory in the cognitive sense. There is no consolidation,
no forgetting curve, no associative retrieval: the system cannot recall "something similar
happened in spring" unless the exact rows are queried by an explicit filter. Short-term memory
is lost on restart, and long-term data is retrieved by structured queries only, never by
similarity. Semantic search over past records is absent.

### 3.4 Knowledge representation - Partially

**How it is implemented.** Domain knowledge is represented explicitly in two places.
`core/workspace.FIELDS` describes the ontology of the domain: an expense has an amount, a date,
a category and an account; categories have a kind; accounts have a balance. Relations between
entities are real Notion relation properties, so the schema is a small graph, not a flat table.
`core/tools.TOOLS_SCHEMA` represents procedural knowledge: what actions exist, which arguments
they require and what they mean.

**Evidence.** The model never sees raw Notion JSON. It sees the declarative schema and operates
on its concepts, which is why renaming a column in `FIELDS` changes behaviour everywhere at
once.

**Limitations.** The representation is static and externally authored. The system cannot extend
its own ontology: it can add a category row, but it cannot invent a new property, a new entity
type or a new relation. There is no inference over the knowledge structure itself, no taxonomy
reasoning and no rules such as "subscriptions are recurring, therefore expect one next month".
General world knowledge lives in the model's weights and is neither inspectable nor editable.

### 3.5 Learning - No

**How it is implemented.** It is not. There is no training loop, no fine-tuning, no reward
signal, no update of any parameter based on interaction. The model weights are frozen; the code
is fixed; behaviour on day 100 is identical to behaviour on day 1.

**Why "No" and not "Partially".** One could argue that the accumulating Notion rows constitute
learning, but they do not. The data grows while the decision policy stays constant: the same
sentence produces the same tool call regardless of how many records exist. If the user corrects
the system ten times, the eleventh time it makes the same mistake, because corrections are not
stored as preferences and never influence the prompt. Accumulating data without changing the
policy is logging, not learning.

**Limitations.** No personalisation, no adaptation, no error-driven improvement. This is the
weakest point of the system and the primary direction for future work.

### 3.6 Reasoning - Partially

**How it is implemented.** The loop in `agent.respond` implements iterative reasoning of the
ReAct type: the model forms a hypothesis about what is needed, acts, observes the actual result
and revises. If a category name is unknown, the model calls `list_categories`, inspects the real
list and only then writes the record. Arithmetic is delegated: the summary totals are computed
in Python inside `tools.summary`, and the prompt explicitly forbids mental arithmetic, because
LLM arithmetic is unreliable.

**Evidence.** A `/trace` entry for a single user message frequently contains a chain of two or
three tools, which means intermediate results influenced later decisions.

**Limitations.** The reasoning is probabilistic text generation, not verified logical inference.
There is no formal proof, no consistency checking and no guarantee of correctness. The chain is
bounded by `MAX_TOOL_ITERATIONS = 6`, and the system cannot explain **why** it chose a tool
beyond describing what it did. Causal reasoning about finances ("spending grew because a
subscription renewed") is imitated linguistically rather than derived.

### 3.7 Decision making - Partially

**How it is implemented.** At each iteration the system decides: answer directly, or call a tool
and which one, with which arguments, and whether to stop. It resolves underspecified input on
its own, for instance mapping "coffee" to the existing "Cafes and restaurants" category rather
than interrogating the user, as instructed by rule 5 of the system prompt.

**Evidence.** The same user phrasing can lead to different tool sequences depending on the state
of the data, which shows the decision is computed rather than hard-wired.

**Limitations.** All decisions are reactive and instrumental: they concern *how* to fulfil a
request, never *whether* to act or *what goal to pursue*. The system never refuses a purchase,
never sets a savings goal by itself and never acts without a message. There is no utility
function, no risk model and no comparison of alternatives. Financial decisions remain entirely
with the human: the system is decision **support**.

### 3.8 Planning - Partially

**How it is implemented.** Plans are formed implicitly and executed step by step. Recording an
expense against an account is a three-step plan: find the account row, create the expense row,
then recalculate and write the new balance (`_adjust_balance`). The request "where can I save
money" is decomposed into: obtain the monthly summary, identify the largest category, formulate
a recommendation.

**Evidence.** The ordering constraint is real and visible in `setup_workspace`, where Accounts
and Categories must be created before Expenses and Incomes, because the latter need existing
database ids for their relation properties.

**Limitations.** The plan is never materialised as an object: there is no explicit plan
structure that could be inspected, stored, criticised or resumed. There is no long-horizon
planning ("save 500 000 by December"), no re-planning after failure beyond a single retry, and
no plan persistence across sessions. Because there is no scheduler in this version, the system
cannot plan anything that happens in the future without the user.

### 3.9 Communication - Yes

**How it is implemented.** This is the most completely realised function. The system understands
free-form, ungrammatical, mixed-language input and answers in the user's language. Output
formatting is constrained for the channel: rules 6 and 7 of the prompt forbid markdown headings
and tables, which render badly in Telegram, and require thousands separators and the currency
symbol. Onboarding is dialogic: `bot/texts.py` explains the two connection steps, and when a
Notion call fails the bot reports the real API message plus the concrete fix ("open the page,
click ..., choose Connections").

**Evidence.** Errors are surfaced, not hidden; the failure path is as carefully worded as the
success path.

**Limitations.** One modality and no model of the interlocutor: the system does not adapt its
register to an expert versus a novice, and it does not track the emotional state of the user.
We still mark this function as fully implemented, because within its channel the communicative
loop is complete: understanding, generation, clarification and error reporting.

### 3.10 Self-evaluation and reflection - Partially

**How it is implemented.** Three mechanisms. First, every tool returns a structured result with
an explicit `ok` flag, so failure is data rather than an exception; rule 2 of the prompt forbids
reporting success when `ok=false`. Second, `core/tool_log.py` records each call with its
arguments, duration, success flag and truncated result. Third, `/status` and `/trace` expose
that introspective data: number of calls, number of failures, average latency, most used tools
and the last ten actions.

**Evidence.** The agent can therefore observe its own behaviour, and a user can verify any claim
the agent makes about what it did. This directly addresses the classic failure mode in which an
assistant claims to have saved something it never saved.

**Limitations.** This is monitoring, not reflection. The statistics are displayed but never fed
back into the decision process: a tool that fails every time keeps being called with the same
arguments. The system has no confidence estimate, cannot say "I am unsure about this category",
and cannot detect that it systematically misclassifies a certain kind of purchase. It cannot
reason about its own limitations except by quoting text written for it by the developers.

---

## 4. Analysis of limitations

The assignment warns against two specific confusions. Both apply to our system and we state
them explicitly.

**Conversation history is not long-term memory.** Our `ConversationMemory` is a `deque` with
`maxlen=12` living in RAM. It disappears on restart, it has no structure, no importance
weighting and no retrieval by meaning. The Notion databases are genuinely persistent, but they
are an external database queried by explicit filters, not a memory system that influences future
behaviour on its own.

**Generating a reply is not decision making.** The model produces the statistically likely
continuation, which in our case happens to be a structured tool call. There is no evaluation of
alternatives, no expected-utility computation and no consequence model. When the agent "decides"
to use the category Transport, it is pattern completion, and it can silently be wrong.

**Additional systemic limitations.**

* **Dependence on an external model.** If the provider is down or the free quota is exhausted,
  every cognitive function stops at once. There is no degraded local mode.
* **Closed capability set.** The agent can only do what the ten tools allow. It cannot compose
  a new capability at runtime; a missing action must be written by a programmer.
* **No autonomy.** Without an incoming message the process is idle. It cannot notice on the 25th
  of the month that the budget is nearly spent.
* **No verification of user input.** If the user says 3 500 but meant 35 000, the error enters
  the long-term store unchallenged; there is no plausibility check against history.
* **Statelessness of reasoning.** Each request rebuilds the context from scratch; nothing is
  carried over except the raw last turns.

---

## 5. Summary table

| Cognitive function | Implemented | How it is implemented | Evidence / justification | Limitations |
| --- | --- | --- | --- | --- |
| Perception | Partially | LLM extraction of entities from free text in Telegram | "spent 3500 on groceries with Kaspi" becomes a structured `add_expense` call, visible in `/trace` | Text only; no voice, images or receipts; passive and environment-blind |
| Attention | Partially | Domain-restricting system prompt, 12-turn window, selective tool choice | Only `summary` is called for a summary request, not all ten tools | Fixed constants, no salience model, not adaptive |
| Memory | Partially | Working list, 12-turn window, Notion rows, JSON profiles | Data survives restart, context does not | Storage without consolidation, forgetting or associative recall |
| Knowledge representation | Partially | `FIELDS` ontology with relations, `TOOLS_SCHEMA` procedural knowledge | Schema changes propagate through the whole system from one place | Static, developer-authored; the system cannot extend its own ontology |
| Learning | No | Not implemented | Identical inputs give identical behaviour regardless of history | No adaptation, no personalisation, no error correction |
| Reasoning | Partially | Iterative ReAct loop, arithmetic delegated to Python | Multi-tool chains in one turn, revised after observing results | Probabilistic, unverified, capped at six iterations |
| Decision making | Partially | Tool and argument selection, autonomous resolution of ambiguity | "coffee" is mapped to an existing category without asking | Instrumental only; no goals, utility or risk model; no financial autonomy |
| Planning | Partially | Implicit multi-step chains with ordering constraints | Accounts and Categories are created before Expenses and Incomes | No explicit plan object, no long horizon, no persistence |
| Communication | Yes | Free-form NLU, language mirroring, channel-aware formatting, actionable errors | Notion errors are reported with the exact remedy | Single modality, no model of the interlocutor |
| Self-evaluation | Partially | `ok` flags, tool log, `/status`, `/trace` | The agent's claims can be verified against its own log | Monitoring only; statistics never influence future decisions |

---

## 6. Overall verdict

**The Personal CFO Agent is a partially cognitive system: an intelligent system with elements of
a cognitive architecture, but without a developed cognitive architecture.**

Arguments in favour of calling it cognitive:

* It has several interacting functions rather than a single input-output mapping.
* It perceives unstructured input and converts it into structured action.
* It reasons iteratively, observing the consequences of its own actions.
* It maintains internal state at several levels and can inspect its own activity.

Arguments against:

* Learning is entirely absent, and learning is the central property of cognition.
* Memory is storage; there is no consolidation or associative retrieval.
* Self-evaluation is monitoring; the system does not use it to improve.
* There is no autonomy, no goal formation and no self-initiated behaviour.
* There is no unified control structure over the functions: they are coordinated by a prompt and
  a for-loop, not by an architecture in the sense of SOAR or ACT-R.

A useful way to summarise the boundary: the system is **a cognitive interface to a database**,
not **a cognitive agent**. It brings human-like flexibility to the input and output of an
otherwise conventional CRUD application.

---

## 7. Answers to the assignment questions

**1. Which cognitive functions are implemented most fully?**
Communication is the only one we consider complete: understanding free text, answering in the
user's language, formatting for the channel and reporting failures with a remedy. Close behind
are reasoning and perception, because the tool-calling loop makes both observable and effective
within the finance domain.

**2. Which are implemented only partially?**
Perception, attention, memory, knowledge representation, reasoning, decision making, planning
and self-evaluation. In every case the mechanism exists and demonstrably works, but it lacks the
property that would make it cognitive rather than merely functional: adaptivity for attention,
consolidation for memory, self-extension for knowledge, verification for reasoning, goals for
decision making, an explicit plan object for planning, and feedback for self-evaluation.

**3. Which are absent?**
Learning. Also absent are emotional evaluation, motivation, goal generation and any form of
self-initiated activity. The system has no internal drive to do anything.

**4. Which components and technologies provide the existing functions?**
The LLM accessed through an OpenAI-compatible endpoint provides perception, language reasoning
and generation. The function-calling protocol plus `core/tools.py` provides action and grounds
the decisions in real effects. The Notion API provides long-term storage. `core/memory.py`
provides short-term context, `core/users.py` provides persistent configuration and isolation
between users, and `core/tool_log.py` provides introspection. The system prompt acts as the
control policy that ties these parts together.

**5. Does the system make autonomous decisions, or only support decisions?**
Only support, with a narrow band of operational autonomy. It autonomously decides which tool to
call and how to interpret an ambiguous phrase, and it writes to the database without asking for
confirmation. It never decides anything financial: it does not choose to save, to cancel a
subscription or to warn about a budget. Every consequential decision stays with the user, and
the system cannot act at all without being addressed first.

**6. Does the system learn during interaction, or is it pre-trained?**
It is entirely pre-trained and frozen. Nothing in the running system changes as a result of
interaction except the contents of the database. There is no fine-tuning, no memory of
corrections and no adaptation of the prompt. The illusion of familiarity comes only from the
fact that the data it queries grows over time.

**7. Are its memory, reasoning and planning full analogues of human cognition?**
No, and in three different ways. Human memory is associative, reconstructive and selective; ours
is exact, indexed and complete, which is simultaneously better and qualitatively different.
Human reasoning includes causal models and self-correction; ours is next-token prediction
constrained by a loop. Human planning maintains hierarchical goals over long horizons; ours is a
sequence of at most six tool calls that disappears when the answer is produced.

**8. Is it a cognitive system, and why?**
Partially. It satisfies some criteria - perception of unstructured input, internal state,
iterative reasoning grounded in feedback, and self-observation - and fails the decisive ones:
learning, autonomy, goal formation and an integrated control architecture. Calling it fully
cognitive would confuse the appearance of cognition, which the language model supplies very
convincingly, with its mechanisms.

**9. What should be added to make it more cognitive?**
In order of impact:

1. **Learning from corrections.** Persist user corrections as preference rules (for example,
   "Magnum is always Groceries") and inject them into the prompt. This alone turns a frozen
   policy into an adaptive one.
2. **Associative long-term memory.** Store embeddings of past transactions and dialogue and
   retrieve by similarity, so the system can recall analogous situations instead of only exact
   filters.
3. **Feedback from self-evaluation.** Use the tool log at decision time: if a tool has been
   failing, change the strategy or tell the user, instead of repeating the same call.
4. **Goals and autonomy.** Add budgets and savings goals plus a scheduler, so the system can act
   on its own initiative: "you have spent 80 percent of the food budget and it is only the 20th".
5. **Confidence and verification.** Have the model report certainty for category assignments and
   check new amounts against historical distributions, asking for confirmation on outliers.
6. **Multimodal perception.** Receipt photographs via OCR and voice messages via speech to text.

---

## 8. Distribution of work in the team

| Member | Responsibility |
| --- | --- |
| Aniyar Baibossyn | Agent core, tool-calling loop, Notion integration and workspace template |
| Salamat Sagyndykov | Telegram layer, multi-user profiles, observability (`/status`, `/trace`), deployment |
| Shynggys Saiduldinov | Cognitive analysis, evidence collection from the tool log, report and presentation |

## 9. Presentation plan (7-10 minutes)

1. Problem and system demonstration: one live message becomes a Notion row (1.5 min).
2. Architecture diagram and where each cognitive function physically lives (2 min).
3. Three functions in depth: communication as the strongest, reasoning as partial, learning as
   absent (3 min).
4. Summary table and the overall verdict with its justification (1.5 min).
5. What we would add to make the system genuinely cognitive (1 min).

**Prepared answers for likely questions.**

* *"Is the LLM itself the cognitive system, not your code?"* The model supplies language ability;
  the architecture around it supplies memory, action, state and introspection. Neither is
  cognitive alone, and the composition is still only partially cognitive, which is exactly our
  verdict.
* *"Your bot remembers my expenses, so why is learning absent?"* Remembering data and changing
  behaviour are different things. Our policy is identical after a thousand records, so the
  system accumulates knowledge without acquiring competence.
* *"Why is communication rated fully implemented while everything else is partial?"* Because
  within its single channel the communicative loop is complete, whereas the other functions all
  miss a defining property. The rating is about completeness of the function, not about the
  number of modalities.
