import os
import subprocess
import sys
import shutil


def run_command(command, description):
    print(f"🚀 {description}...")
    try:
        subprocess.run(command, check=True, shell=True)
        print(f"✅ {description} completed.\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during {description}: {e}")
        return False
    return True


def setup_venv():
    if not os.path.exists("venv"):
        if not run_command(
            f"{sys.executable} -m venv venv", "Creating virtual environment"
        ):
            return False

    pip_path = (
        os.path.join("venv", "bin", "pip")
        if os.name != "nt"
        else os.path.join("venv", "Scripts", "pip")
    )
    if not run_command(f"{pip_path} install --upgrade pip", "Updating pip"):
        return False
    if not run_command(
        f"{pip_path} install -r requirements.txt", "Installing dependencies"
    ):
        return False
    return True


def setup_env():
    print("📝 Configuring environment variables...")
    env_vars = {
        "TELEGRAM_BOT_TOKEN": "Enter your Telegram Bot Token",
        "LLM_API_KEY": "Enter your LLM API Key (Gemini/DeepSeek/OpenAI)",
        "TAVILY_API_KEY": "Enter your Tavily API Key",
        "WEBHOOK_URL": "Enter your Webhook URL (e.g., https://your-domain.com/webhook)",
        "DASHBOARD_USER_ID": "Enter your Telegram User ID (for dashboard access)",
        "DATABASE_URL": "Enter PostgreSQL DATABASE_URL (default: postgresql://webdocuser:webdocpassword@localhost:5433/bot_db)",
    }

    current_env = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    current_env[key] = value

    new_env = {}
    for var, prompt in env_vars.items():
        default = current_env.get(var, "")
        if var == "DATABASE_URL" and not default:
            default = "postgresql://webdocuser:webdocpassword@localhost:5433/bot_db"

        user_input = input(f"{prompt} [{default}]: ").strip()
        new_env[var] = user_input if user_input else default

    with open(".env", "w") as f:
        for var, value in new_env.items():
            f.write(f"{var}={value}\n")
    print("✅ .env file generated.\n")


def check_google_credentials():
    print("🔑 Checking Google Cloud Credentials...")
    if not os.path.exists("credentials.json"):
        path = input(
            "Enter path to your 'credentials.json' (or press Enter to skip if already present): "
        ).strip()
        if path and os.path.exists(path):
            shutil.copy(path, "credentials.json")
            print("✅ credentials.json copied to project root.")
        else:
            print(
                "⚠️ credentials.json not found. Google services (Sheets, etc.) might not work."
            )
    else:
        print("✅ credentials.json found.")


def check_token():
    print("🎫 Checking Google OAuth Token...")
    if not os.path.exists("token.pickle"):
        if os.path.exists("credentials.json"):
            print("token.pickle missing. Attempting to generate...")
            python_path = (
                os.path.join("venv", "bin", "python")
                if os.name != "nt"
                else os.path.join("venv", "Scripts", "python")
            )
            if os.path.exists(python_path):
                run_command(
                    f"{python_path} scripts/generate_token.py",
                    "Generating token.pickle",
                )
            else:
                print("⚠️ Virtual environment not found. Please run setup again.")
        else:
            print("⚠️ Cannot generate token.pickle without credentials.json.")
    else:
        print("✅ token.pickle found.")


def main():
    print("=== Bot Automated Setup ===\n")

    setup_env()

    if not setup_venv():
        print("❌ Setup failed during dependency installation.")
        return

    check_google_credentials()
    check_token()

    print(
        "\n✨ Setup complete! You can now run the bot using 'make run' or 'python main.py'."
    )


if __name__ == "__main__":
    main()
