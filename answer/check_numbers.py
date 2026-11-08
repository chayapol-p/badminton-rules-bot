"""
Checks that every number in an answer comes from what the model was shown: no numbers from nowhere.

A number the sources and the question don't hold came from the model's memory: a year, a
string tension, a fine. That check needs no golden answer, so it can run on every request.

Numbers are compared in one normal form, so the same number written two ways still matches:
  - number words from two up become digits: "two" is 2
  - clause numbers stay whole: "9.1.6" is one number, not "9.1" and "6"
  - leading zeros go: "04" in "2027-01-04" is 4
  - trailing decimal zeros go: "13.40" is 13.4
A parent clause counts as shown when a clause under it was: citing "Law 9.1" is fine when
"9.1.6" was in the sources.

Use:
    ungrounded = find_ungrounded_numbers(answer_text, source_text)
"""

import re


# Constants
## Number words, written as digits before numbers are read. "zero" and "one" are left out: in
## speech they're rarely numbers ("one condition", "no one"), and run 1 showed "one" as a false flag
NUMBER_WORDS = {
    "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60",
}

## A number word as a whole word, so "one" in "someone" is left alone
NUMBER_WORD_PATTERN = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\b")

## A number, with every dotted part kept together: 1.55, 9.1.6, 2027
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)*")


# ===== Reading numbers in one normal form =====

def normalise_number(number: str) -> str:
    """Returns the number without leading zeros, and without trailing decimal zeros when it has one dot."""
    parts = number.split(".")
    parts[0] = parts[0].lstrip("0") or "0"

    # One dot is a decimal (13.40 is 13.4); two or more is a clause number, kept as it is
    is_decimal = len(parts) == 2
    if is_decimal:
        parts[1] = parts[1].rstrip("0")
        if not parts[1]:
            return parts[0]
    return ".".join(parts)


def numbers_in(text: str) -> set[str]:
    """Returns every number in the text, number words included, in normal form."""
    text_with_digits = NUMBER_WORD_PATTERN.sub(lambda match: NUMBER_WORDS[match.group(1)], text.lower())
    return {normalise_number(number) for number in NUMBER_PATTERN.findall(text_with_digits)}


# ===== Checking an answer against its sources =====

def is_grounded(number: str, source_numbers: set[str]) -> bool:
    """True when the number is in the sources, or is the parent of a clause number that is."""
    if number in source_numbers:
        return True
    for source_number in source_numbers:
        if source_number.startswith(number + "."):
            return True
    return False


def find_ungrounded_numbers(answer_text: str, source_text: str) -> list[str]:
    """Returns the numbers in the answer that the source text doesn't hold, sorted."""
    source_numbers = numbers_in(source_text)
    ungrounded = []
    for number in numbers_in(answer_text):
        if not is_grounded(number, source_numbers):
            ungrounded.append(number)
    return sorted(ungrounded)
