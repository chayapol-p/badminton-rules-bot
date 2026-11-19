"""
Downloads the three BWF rule books the bot reads, and checks each one against its frozen hash, so every clone builds
its clauses from the same PDFs the results were measured on. The PDFs belong to BWF and are never committed.

A book already saved with the right hash is skipped. A download with another hash stops the script and is not saved:
BWF may have published a new version, and every chunk, test and score assumes the frozen one.

  Input:  the BWF statutes pages below, and the frozen hashes in evals/golden_questions.json ("corpus_frozen")
  Output: data/bwf/<file>.pdf for each book

Run from the project root, then build the clauses and the rule map:
    uv run python -m scripts.download_rule_books
    uv run python -m scripts.build_rule_chunks
    uv run python -m scripts.build_rule_links
"""

import hashlib
import json
import sys

import httpx

from evals.golden_answer_chunks import QUESTIONS_FILE
from scripts.build_rule_chunks import PDF_FOLDER


# Constants
## Where BWF publishes each book (https://corporate.bwfbadminton.com/statutes/), by its key in "corpus_frozen"
BWF_DOCUMENTS_ADDRESS = "https://extranet.bwf.sport/docs/document-system/81/1466/1470/"
DOWNLOAD_URL_BY_DOCUMENT = {
    "laws": BWF_DOCUMENTS_ADDRESS + "Section%204.1%20-%20Laws%20of%20Badminton%20-%2026%20April%202025%20V5.0%20(2)%20.pdf",
    "itto": BWF_DOCUMENTS_ADDRESS + "Section%204.1.1%20-%20Instructions%20to%20Technical%20Officials%20(ITTO)%20-"
                                    "%2026%20April%202025%20V7.0%20(5).pdf",
    "alt": BWF_DOCUMENTS_ADDRESS + "Section%204.1.4%20-%20Alternative%20Laws%20of%20Badminton%20-"
                                   "%2004%20January%202027%20(V2.0).pdf",
}

## Seconds to wait for one book before giving up
DOWNLOAD_TIMEOUT_SECONDS = 60


# Returns the SHA-256 of a file's bytes, as hex
def hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# Downloads one book, checks its hash, and saves it; stops the script when the hash differs
def download_rule_book(document: str, file_name: str, expected_hash: str) -> None:
    pdf_path = PDF_FOLDER / file_name

    # A book already saved with the right hash needs no download
    if pdf_path.exists() and hash_bytes(pdf_path.read_bytes()) == expected_hash:
        print(f"{file_name}: already here")
        return

    # Download it; a network error or a missing page stops the script, because every build step needs all three
    response = httpx.get(DOWNLOAD_URL_BY_DOCUMENT[document], follow_redirects=True, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()

    # Save it only when it is the frozen version
    downloaded_hash = hash_bytes(response.content)
    if downloaded_hash != expected_hash:
        sys.exit(f"{file_name}: the download's hash is {downloaded_hash}, not the frozen {expected_hash}. "
                 "BWF may have published a new version; the file was not saved.")
    pdf_path.write_bytes(response.content)
    print(f"{file_name}: downloaded and checked")


# Downloads every book named in "corpus_frozen"
def main() -> None:
    frozen_books = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))["corpus_frozen"]
    PDF_FOLDER.mkdir(parents=True, exist_ok=True)
    for document, frozen_book in frozen_books.items():
        download_rule_book(document, frozen_book["file"], frozen_book["sha256"])


if __name__ == "__main__":
    main()
