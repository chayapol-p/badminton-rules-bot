"""
The inline markers of a natural answer (record 0027): [n] right after a claim points to source n in the numbered
list under the answer. One home for the marker pattern, so the flow that renumbers markers and the check that
checks them read markers the same way.

Use:
    bracketed_texts = MARKER_PATTERN.findall(sentence_text)
    cited_numbers = find_marker_numbers(sentence_text)
    sentence_text = renumber_markers(sentence_text, new_number_by_old)
"""

import re


# Constants
## An inline marker as the model writes it: anything in square brackets, so a bad one ("[laws-1.4]") is caught too
MARKER_PATTERN = re.compile(r"\[([^\[\]]*)\]")


# ===== Reading and renumbering markers =====

def find_marker_numbers(text: str) -> set[int]:
    """Returns the numbers of the [n] markers in the text; bracketed text that isn't a number is left out."""
    numbers = set()
    for bracketed_text in MARKER_PATTERN.findall(text):
        if bracketed_text.isdigit():
            numbers.add(int(bracketed_text))
    return numbers


def renumber_markers(text: str, new_number_by_old: dict[int, int]) -> str:
    """Returns the text with each [n] in the map changed to its new number; any other bracketed text stays as it is."""

    def renumber_one(match: re.Match) -> str:
        """Returns one bracketed text, renumbered when it is a marker the map moves."""
        bracketed_text = match.group(1)
        is_moved_marker = bracketed_text.isdigit() and int(bracketed_text) in new_number_by_old
        if is_moved_marker:
            return f"[{new_number_by_old[int(bracketed_text)]}]"
        return match.group(0)

    return MARKER_PATTERN.sub(renumber_one, text)
