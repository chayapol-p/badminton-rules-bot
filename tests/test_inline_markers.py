"""Tests reading and renumbering a natural answer's inline [n] markers."""

from answer_flows.shared.inline_markers import find_marker_numbers, renumber_markers


def test_only_number_markers_are_read():
    assert find_marker_numbers('Win by two [1][3], say "[name of player(s)]" [laws-7.4].') == {1, 3}


def test_renumbering_moves_only_the_markers_in_the_map():
    text = 'Posts [1], strings [4], "[name of player(s)]" [9].'
    assert renumber_markers(text, {4: 2}) == 'Posts [1], strings [2], "[name of player(s)]" [9].'
