"""
Tests the numbers-not-in-the-sources check: number words, clause numbers, normal forms and parent clauses.
"""

from answer.check_numbers import find_ungrounded_numbers, normalise_number, numbers_in


# ===== Reading numbers =====

def test_clause_numbers_stay_whole_and_number_words_become_digits():
    assert numbers_in("Law 9.1.6 gives two points") == {"9.1.6", "2"}


def test_one_is_not_read_as_a_number():
    """Run 1 flagged "one condition" as a number not in the sources: "zero" and "one" are left out."""
    assert numbers_in("No one may serve until one condition holds") == set()


def test_leading_and_trailing_zeros_go():
    assert normalise_number("04") == "4"
    assert normalise_number("13.40") == "13.4"
    assert normalise_number("2.0") == "2"
    assert normalise_number("9.1.0") == "9.1.0", "a clause number keeps every part"


# ===== Checking an answer =====

def test_a_number_in_the_sources_is_grounded():
    source_text = "The posts shall be 1.55 metres in height."
    assert find_ungrounded_numbers("The posts are 1.55 metres tall.", source_text) == []


def test_a_number_not_in_the_sources_is_listed():
    source_text = "The posts shall be 1.55 metres in height."
    assert find_ungrounded_numbers("Posts are 1.55 m, since 1992.", source_text) == ["1992"]


def test_a_parent_clause_counts_as_shown_when_a_clause_under_it_was():
    source_text = "[laws-9.1.6] Clause 9.1.6\nThe whole shuttle shall be below the server's waist."
    assert find_ungrounded_numbers("Law 9.1 covers it, in 9.1.6.", source_text) == []
