# Career Assistant Bot

An intelligent and professional AI Career Assistant built with FastAPI, LangGraph, PostgreSQL, and Telegram.

## 🚀 Quick Start

The easiest way to get started is using the automated setup script.

1.  **Run Setup**:
    ```bash
    make setup
    ```
    This will:
    - Prompt for necessary environment configuration (Telegram Token, consolidated LLM API Key, Tavily API Key, PostgreSQL Database URL, and Webhook URL).
    - Create a `.env` file.
    - Initialize a virtual environment and install all dependencies.

2.  **Run the Bot**:
    ```bash
    make run
    ```

## 🐳 Docker/Cloud Deployment

For production and containerized deployments:

1.  **Configuration**:
    Ensure your production environment has a running PostgreSQL instance, and configure `.env` with `DATABASE_URL` and the mandatory public `WEBHOOK_URL` (accessible by Telegram).
2.  **Google Integration**:
    Authorize Google services (Gmail, Calendar) directly from the Web Dashboard under **Settings → Google Integration**. Upload your `credentials.json` (must be **Web application** type from Google Cloud Console) and click **Connect Google Account**.

## 🛠️ Project Structure

- `main.py`: FastAPI entry point and webhook handler. Runs on port `8000` (host `0.0.0.0`) by default.
- `agent/`: LangGraph agent logic and tools.
- `services/`: Core logic for PostgreSQL database, Gmail/Calendar services, and more.
- `telegram_bot/`: Telegram bot handlers and configuration.
- `static/`: Notion-style dashboard frontend.
- `scripts/`: Utility scripts for automated setup.

## 🧪 Testing

Run the test suite using:
```bash
make test
```

## 🧹 Maintenance

Clean up temporary files and the virtual environment:
```bash
make clean
```
