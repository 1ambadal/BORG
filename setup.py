import os
import subprocess
import sys
import shutil


def print_banner():
    print("\n" + "=" * 50)
    print("🚀 Career Assistant Bot - Easy Setup")
    print("=" * 50 + "\n")


def run_command(command, description):
    print(f"📦 {description}...")
    try:
        subprocess.check_call(command, shell=True)
        print(f"✅ {description} completed.\n")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during: {description}")
        sys.exit(1)


def setup_venv():
    if not os.path.exists("venv"):
        run_command(f"{sys.executable} -m venv venv", "Creating virtual environment")
    else:
        print("ℹ️ Virtual environment already exists.\n")


def install_dependencies():
    pip_path = (
        os.path.join("venv", "bin", "pip")
        if os.name != "nt"
        else os.path.join("venv", "Scripts", "pip")
    )
    run_command(f"{pip_path} install -r requirements.txt", "Installing dependencies")


def setup_env():
    if not os.path.exists(".env"):
        print("📝 Configuring .env file...")
        shutil.copy(".env.example", ".env")

        telegram_token = input(
            "Enter your Telegram Bot Token (from @BotFather): "
        ).strip()
        llm_key = input("Enter your LLM API Key (Gemini/DeepSeek/OpenAI): ").strip()
        tavily_key = input("Enter your Tavily API Key: ").strip()
        webhook_url = input("Enter your Webhook URL (e.g., https://your-domain.com): ").strip()

        with open(".env", "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                new_lines.append(f"TELEGRAM_BOT_TOKEN={telegram_token}\n")
            elif line.startswith("LLM_API_KEY="):
                new_lines.append(f"LLM_API_KEY={llm_key}\n")
            elif line.startswith("TAVILY_API_KEY="):
                new_lines.append(f"TAVILY_API_KEY={tavily_key}\n")
            elif line.startswith("WEBHOOK_URL="):
                new_lines.append(f"WEBHOOK_URL={webhook_url}\n")
            else:
                new_lines.append(line)

        with open(".env", "w") as f:
            f.writelines(new_lines)
        print("✅ .env file created and configured.\n")
    else:
        print("ℹ️ .env file already exists. Skipping configuration.\n")


def setup_google_auth():
    if not os.path.exists("credentials.json"):
        print("⚠️ Warning: 'credentials.json' not found.")
        print("To use Google Calendar/Docs features, please follow these steps:")
        print("1. Go to Google Cloud Console.")
        print("2. Enable Google Calendar API.")
        print("3. Create OAuth 2.0 Client ID (Desktop App).")
        print("4. Download JSON and rename it to 'credentials.json' in this folder.")
        print("-" * 30)
    else:
        if not os.path.exists("token.pickle"):
            print("🔑 Generating Google OAuth token...")
            python_path = (
                os.path.join("venv", "bin", "python")
                if os.name != "nt"
                else os.path.join("venv", "Scripts", "python")
            )
            run_command(
                f"{python_path} scripts/generate_token.py", "Generating token.pickle"
            )
        else:
            print("ℹ️ 'token.pickle' already exists.\n")


def main():
    print_banner()

    setup_venv()
    install_dependencies()
    setup_env()
    setup_google_auth()

    print("=" * 50)
    print("🎉 Setup Complete!")
    print("=" * 50)
    print("\nTo start the bot, run:")
    if os.name != "nt":
        print("source venv/bin/activate && python main.py")
    else:
        print("venv\\Scripts\\activate && python main.py")
    print("Access the dashboard at: http://localhost:8000/")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
