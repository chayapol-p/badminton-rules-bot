"""
Checks that product code never imports the retired answer flows, so the app runs only the product flow.
The retired flows live in experiments/retired_flows/ and only the experiment scripts and their tests may use them.
"""

from pathlib import Path

# Constants
## The folders the app and the evals run from
PRODUCT_FOLDERS = ["answer_flows", "app", "evals", "retrieval"]

## The words an import of a retired flow starts with
RETIRED_IMPORT_STARTS = ["from experiments", "import experiments"]


def find_experiment_imports(repo_folder: Path) -> list[str]:
    """Lists each line in a product file that imports from experiments/, as 'file:line: import'."""
    problems = []
    for folder_name in PRODUCT_FOLDERS:
        for python_file in sorted((repo_folder / folder_name).rglob("*.py")):
            for line_number, line in enumerate(python_file.read_text().splitlines(), start=1):
                is_experiment_import = any(line.lstrip().startswith(start) for start in RETIRED_IMPORT_STARTS)
                if is_experiment_import:
                    problems.append(f"{python_file.relative_to(repo_folder)}:{line_number}: {line.strip()}")
    return problems


def test_product_code_does_not_import_experiments():
    """The app must never load a retired flow, so no product file may import one."""
    repo_folder = Path(__file__).resolve().parent.parent
    assert find_experiment_imports(repo_folder) == []
