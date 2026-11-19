"""
Checks which code may import which:
- Product code never imports the retired answer flows, so the app runs only the product flow. The retired flows live
  in experiments/retired_flows/ and only the experiment scripts and their tests may use them.
- The bot (answer_flows/ and retrieval/) never imports the web app or the evals, so it runs on its own and the app
  and the evals sit on top of it.
"""

from pathlib import Path

# Constants
## The folders the app and the evals run from
PRODUCT_FOLDERS = ["answer_flows", "app", "evals", "retrieval"]

## The folders that make up the bot itself
BOT_FOLDERS = ["answer_flows", "retrieval"]

## The words an import of a retired flow starts with
RETIRED_IMPORT_STARTS = ["from experiments", "import experiments"]

## The words an import of the web app or the evals starts with
APP_OR_EVALS_IMPORT_STARTS = ["from app", "import app", "from evals", "import evals"]

## The project folder
REPO_FOLDER = Path(__file__).resolve().parent.parent


def starts_with_import(line: str, import_start: str) -> bool:
    """True when the line imports the named package or one of its modules ("from app " or "from app.settings")."""
    code = line.lstrip()
    return code.startswith(import_start + " ") or code.startswith(import_start + ".")


def find_imports(folder_names: list[str], import_starts: list[str]) -> list[str]:
    """Lists each line in the folders' Python files that starts with one of the imports, as 'file:line: import'."""
    problems = []
    for folder_name in folder_names:
        for python_file in sorted((REPO_FOLDER / folder_name).rglob("*.py")):
            for line_number, line in enumerate(python_file.read_text().splitlines(), start=1):
                is_listed_import = any(starts_with_import(line, start) for start in import_starts)
                if is_listed_import:
                    problems.append(f"{python_file.relative_to(REPO_FOLDER)}:{line_number}: {line.strip()}")
    return problems


def test_product_code_does_not_import_experiments():
    """The app must never load a retired flow, so no product file may import one."""
    assert find_imports(PRODUCT_FOLDERS, RETIRED_IMPORT_STARTS) == []


def test_the_bot_does_not_import_the_app_or_the_evals():
    """The bot must run without the web app or the evals, so no bot file may import either."""
    assert find_imports(BOT_FOLDERS, APP_OR_EVALS_IMPORT_STARTS) == []
