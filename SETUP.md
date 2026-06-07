# 🚀 Setup Guide: Career Assistant Bot

Setting up your AI Career Assistant is now easier than ever. Follow the **Quick Start** to set up PostgreSQL, your credentials, and start the application.

---

## ⚡ Quick Start (Recommended)

Run the interactive setup script which handles environment creation, dependency installation, and basic configuration.

```bash
python3 setup.py
```

Follow the prompts to enter your API keys, database connection string, and webhook URL. Once finished, start the bot:

```bash
source venv/bin/activate  # On Linux/Mac
python main.py
```

> [!IMPORTANT]
> The bot operates strictly in **Webhook Mode** for production reliability. You must supply a valid `WEBHOOK_URL` (like an `ngrok` HTTPS tunnel during development or your domain in production).

---

## 📋 Prerequisites
Before running the setup, ensure you have:
- **Python 3.10+**: [Download Python](https://www.python.org/downloads/)
- **PostgreSQL**: A running PostgreSQL instance (either local or cloud-hosted)
- **API Keys**:
    - **LLM API Key**: A single, consolidated API key supporting Gemini, DeepSeek, or OpenAI.
    - **Tavily API Key**: [Tavily API Key](https://tavily.com/) (for web search/scraping)
- **Telegram Account**: Create your bot via [@BotFather](https://t.me/botfather).

---

## 🔑 Google Calendar & Gmail Integration

To allow the bot to manage your calendar and send emails, you need to configure OAuth:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and enable the **Google Calendar API** and **Gmail API**.
3. Go to **APIs & Services > Credentials** and create an **OAuth 2.0 Client ID**.
   - ⚠️ Select **Web application** (not Desktop app).
4. Add your redirect URI under **Authorized redirect URIs**:
   - Local: `http://127.0.0.1:8000/api/google/callback`
   - Production: `https://your-domain.com/api/google/callback`
5. Download the credentials JSON file.
6. Open the Dashboard (`/app.html`), go to **Settings**, and click **Upload credentials.json**.
7. Click **Connect Google Account** — you'll be redirected to Google to grant permissions.
8. Once authorized, the `token.json` is saved automatically on the server.

---

## 🌐 Webhook Tunneling (Local Development)

Since webhooks are mandatory:
1. Install [ngrok](https://ngrok.com/) and run `ngrok http 8000`.
2. Copy the forwarding HTTPS URL.
3. Update `.env` with `WEBHOOK_URL=https://your-ngrok-subdomain.ngrok-free.app` (do not add a trailing slash).
4. Start the application, and the bot will register the webhook with Telegram automatically.

---

## 🚀 Running the Bot

```bash
python main.py
```

### Access the Dashboard
Open your browser to: `http://localhost:8000/app.html`

---

## 🧪 Testing
1. Send `/start` to your bot on Telegram.
2. Go to the dashboard settings page to connect your Google account.
3. Try saying "Add a meeting at 5pm tomorrow" to the bot on Telegram.
4. Run the test suite using `make test`.

