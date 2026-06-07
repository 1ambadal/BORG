# BORG — Personal AI Operating System

> One conversation. Full context. Zero friction.

BORG is a fully autonomous personal AI OS that runs your life through Telegram and a web dashboard. No manual logging. No app switching. Just talk.

Built with **LangGraph**, **FastAPI**, **PostgreSQL**, and **Telegram Bot API**.

---

## What it can do

| Capability | Example |
|---|---|
| 📧 **Inbox Management** | Reads Gmail, drafts recruiter replies, sends with one tap |
| 🗓️ **Calendar** | "Add a meeting tomorrow at 3PM with Arjun" → instantly scheduled |
| 🏋️ **Fitness Tracking** | "Bench 100kg 3x5" → logged with sets, reps, and weight |
| 🥗 **Macro Counting** | Tell it what you ate → full protein/carb/fat/calorie breakdown |
| 💳 **Expense Tracking** | "Spent 540 on pizza" → categorized under monthly expenses |
| 🛣️ **Learning Roadmaps** | Upload resume + job description → skill gap analysis + curriculum |
| 🎙️ **Voice Commands** | Send a voice note → transcribed and acted on |
| 💼 **Job Scraping** | Background crawlers alert you to new openings matching your target roles |
| 📝 **Notes & Reminders** | Brain dumps → tagged notes + persistent notifications |
| 🔖 **Bookmarks** | Drop a URL → saved and retrievable |
| ✅ **Todos** | "Refactor auth module this week" → tracked |
| ⏰ **Cron Jobs** | "Send me a daily 9AM summary" → scheduled and automated |
| 🔍 **Web Search** | "What's bitcoin at right now?" → live answer inline |

The real magic: send one rambling message hitting 10 different intents — BORG parses and routes all of them correctly.

---

## Architecture

```
Telegram / Web Dashboard
         ↓
      FastAPI
         ↓
    LangGraph Agent
   (conditional routing)
   /    |    |    \
Gmail  Cal  DB   Tools
         ↓
     PostgreSQL
```

- **LangGraph** — agent orchestration with conditional edges; each capability is its own subgraph
- **FastAPI** — backend + webhook handler, runs on port `8000`
- **PostgreSQL** — persistent memory, structured logs, factual store
- **Telegram** — primary conversational interface
- **Web Dashboard** — Notion-style UI for visualization and settings

---

## Quick Start

```bash
# 1. Setup — prompts for env config and installs dependencies
make setup

# 2. Run
make run
```

`make setup` will configure:
- Telegram Bot Token
- LLM API Key
- Tavily API Key (web search)
- PostgreSQL Database URL
- Webhook URL

---

## Docker / Cloud Deployment

1. Ensure a running PostgreSQL instance and set `DATABASE_URL` + `WEBHOOK_URL` in `.env`
2. `WEBHOOK_URL` must be publicly accessible by Telegram

**Google Integration (Gmail + Calendar):**

Go to **Settings → Google Integration** in the web dashboard. Upload your `credentials.json` (must be **Web application** type from Google Cloud Console) and connect your account.

---

## Project Structure

```
├── main.py              # FastAPI entry point, webhook handler
├── agent/               # LangGraph agent logic and tools
├── services/            # PostgreSQL, Gmail, Calendar, and core services
├── telegram_bot/        # Telegram handlers and config
├── static/              # Web dashboard frontend
└── scripts/             # Automated setup utilities
```

---

## Testing

```bash
make test
```

---

## Stress Test

Want to see what BORG can handle? Try sending this in one message:

> *"okay dont judge me — breakfast was 2 samosas and chai, lunch was nothing, dinner was a large dominos pizza like the full thing probably 1800 cals of regret. no gym today. spent 540 on the pizza, 80 on chai, paid electricity bill 2300, also bought new headphones 3200 from amazon. add a meeting tomorrow 9am standup with team, 12pm lunch with Vikram, and block 3-5pm for deep work. btw whats bitcoin at right now. remind me to push code before midnight and to drink water more. also add a todo to refactor the auth module this week, bookmark this article i was reading about pgvector https://pgvector.io and set up a daily cron at 9am to send me a summary of my day. what is wrong with me"*

BORG will correctly parse and act on all 10 intents — including not hallucinating a gym session that didn't happen.

---

## Contributing

PRs welcome. Open an issue first for major changes.

---

## License

MIT