import subprocess

def run_cmd(msg):
    subprocess.run(["git", "commit", "-a", "-m", msg], check=True)

with open("app/config/settings.py", "r") as f:
    content = f.read()

content = content.replace('app_name: str = "memescout"', 'app_name: str = "meco"')
content = content.replace('telegram_session_name: str = "memescout"', 'telegram_session_name: str = "meco"')
content = content.replace('postgresql+asyncpg://postgres:postgres@localhost:5432/memescout', 'postgresql+asyncpg://postgres:postgres@localhost:5432/meco')

with open("app/config/settings.py", "w") as f:
    f.write(content)

run_cmd("Update setting defaults from memescout to meco")

with open(".env", "r") as f:
    env_content = f.read()

env_content = env_content.replace('DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/memescout', 'DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/meco')

with open(".env", "w") as f:
    f.write(env_content)
