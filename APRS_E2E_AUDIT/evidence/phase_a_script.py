import sys
import subprocess
import os

out = []
out.append("=== REPOSITORY BASELINE ===")
out.append(f"Current Directory: {os.getcwd()}")
out.append(f"System Python: {sys.executable} ({sys.version})")

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        res = r.stdout.strip()
        if r.stderr.strip():
            res += "\nSTDERR:\n" + r.stderr.strip()
        return res
    except Exception as e:
        return str(e)

out.append("\n=== GIT BRANCH & HEAD ===")
out.append(run_cmd("git branch -v"))
out.append(run_cmd("git log -1 --stat"))

out.append("\n=== GIT STATUS ===")
out.append(run_cmd("git status"))

out.append("\n=== VIRTUAL ENV & TOOL VERSIONS ===")
out.append(f"VIRTUAL_ENV env var: {os.environ.get('VIRTUAL_ENV', 'None')}")
out.append(".venv Python: " + run_cmd(r".\.venv\Scripts\python.exe --version"))
out.append(".venv Streamlit: " + run_cmd(r".\.venv\Scripts\streamlit.exe --version"))
out.append(".venv Pytest: " + run_cmd(r".\.venv\Scripts\pytest.exe --version"))

out.append("\n=== PIP LIST (.venv) ===")
out.append(run_cmd(r".\.venv\Scripts\pip.exe list"))

content = "\n".join(out)
with open("APRS_E2E_AUDIT/evidence/phase_a_baseline.txt", "w", encoding="utf-8") as f:
    f.write(content)
print("Phase A baseline successfully written, size:", len(content))
