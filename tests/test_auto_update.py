import os
import subprocess
import tempfile
import textwrap
import shutil
import pytest
from pathlib import Path


def run_script(env, repo_dir):
    script = Path(__file__).parents[1] / "scripts" / "auto_update_and_restart.sh"
    assert script.exists(), f"script missing: {script}"
    # Ensure executable
    script.chmod(0o755)
    if os.name == "nt":
        git_bash = os.path.join("C:\\Program Files", "Git", "bin", "bash.exe")
        bash = git_bash if os.path.exists(git_bash) else shutil.which("bash")
        if not bash:
            pytest.skip("bash not available on Windows for .sh script execution")
        proc = subprocess.run([bash, str(script)], env=env, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    else:
        proc = subprocess.run([str(script)], env=env, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def init_sample_repo(repo_dir: Path):
    # Initialize a git repo with a known_good branch and a commit
    subprocess.run(["git", "init"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    (repo_dir / "README.md").write_text("sample repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_dir, check=True)
    subprocess.run(["git", "checkout", "-b", "known_good"], cwd=repo_dir, check=True)
    # Add a local 'origin' remote pointing to the repo itself so fetch works in tests
    subprocess.run(["git", "remote", "add", "origin", str(repo_dir)], cwd=repo_dir, check=True)


def test_auto_update_runs(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    init_sample_repo(repo_dir)

    # Prepare environment to override the script variables and avoid side effects
    env = os.environ.copy()
    env["REPO_DIR"] = str(repo_dir)
    env["BRANCH"] = "known_good"
    env["PYTHON"] = "/usr/bin/python3"
    env["SKIP_PIP"] = "1"
    env["SKIP_SYSTEMCTL"] = "1"
    if os.name == "nt":
        env["SKIP_GIT"] = "1"
    # Ensure PATH contains git and bash
    if os.name == "nt":
        env["PATH"] = "/usr/bin:/bin:/mingw64/bin"
    else:
        env["PATH"] = os.environ.get("PATH", "/usr/bin:/bin")

    code, out = run_script(env, repo_dir)
    # Script logs to $REPO_DIR/logs/auto_update.log by default; read that file
    log_file = repo_dir / "logs" / "auto_update.log"
    assert code == 0
    assert log_file.exists(), f"expected log file at {log_file}"
    log_text = log_file.read_text()
    assert "Auto-update run starting" in log_text
    if os.name == "nt" and "SKIP_GIT=1" in log_text:
        assert "skipping git fetch/checkout/pull" in log_text
    else:
        assert ("Pulling latest from origin/known_good" in log_text) or ("Fetching origin" in log_text)