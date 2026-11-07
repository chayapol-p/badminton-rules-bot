"""
Groups the clause chunks by section (x.x), with a word limit, to compare with single clauses and windows.

A section is a clause numbered x.x together with every clause under it: 9.1 holds 9.1.1 to
9.1.7. When a section runs past the word limit, it is split one level down (9.1.1, 9.1.2, ...),
and again if needed, so no group passes the limit unless one clause alone does. This follows
section-aware chunking with a size cap, such as Unstructured's by_title strategy: a group never
mixes two sections, and a cap splits sections that are too big.

The word limit matches the windows (about 300 words), so groups and windows compare at the
same size: structure against fixed length.

Every group records the clause chunks it covers, so the scorer counts a location as found
when a retrieved group covers its clause.

Use:
    section_groups = build_section_groups(load_chunks())
"""

from scripts.build_rule_chunks import context_header
from retrieval.window_chunks import clause_as_printed


# Constants
## Group at x.x first, as in "9.1"
SECTION_DEPTH = 2

## Split a group one level down when its clauses pass this many words (windows hold about 300)
GROUP_WORD_LIMIT = 300


# ===== Keys and sizes =====

def section_key(chunk, depth):
    """Returns what a clause shares with the rest of its group at this depth: document, format, number prefix."""
    number_prefix = ".".join(chunk["clause"].split(".")[:depth])
    return (chunk["document"], chunk["alternative_format"], number_prefix)


def group_word_count(group_chunks):
    """Returns how many words the group's clauses hold, as printed."""
    word_count = 0
    for chunk in group_chunks:
        word_count += len(clause_as_printed(chunk).split())
    return word_count


# ===== Splitting into groups =====

def split_by_key(chunks, depth):
    """Splits the chunks into runs that share a section key at this depth, keeping the ingest order."""
    chunks_by_key = {}
    for chunk in chunks:
        chunks_by_key.setdefault(section_key(chunk, depth), []).append(chunk)
    return list(chunks_by_key.values())


def split_until_under_limit(group_chunks, depth):
    """Returns the group whole if it fits the word limit, or its parts one level down, split again as needed."""
    fits_limit = group_word_count(group_chunks) <= GROUP_WORD_LIMIT
    is_single_clause = len(group_chunks) == 1
    if fits_limit or is_single_clause:
        return [group_chunks]

    # The section's own clause (9.1) keeps a group of its own; each child (9.1.1, 9.1.2) starts one
    groups = []
    for part in split_by_key(group_chunks, depth + 1):
        groups.extend(split_until_under_limit(part, depth + 1))
    return groups


# ===== Building the group records =====

def group_record(group_chunks):
    """Returns one group: its id, document, text, search text and covered clause ids."""
    first_chunk = group_chunks[0]
    group_text = "\n\n".join(clause_as_printed(chunk) for chunk in group_chunks)
    return {
        "id": f"section-{first_chunk['id']}",
        "document": first_chunk["document"],
        "text": group_text,

        # The first clause's context header names the section, like a clause's search_text
        "search_text": f"{context_header(first_chunk)}\n{group_text}",
        "covers": [chunk["id"] for chunk in group_chunks],
    }


def build_section_groups(chunks):
    """Returns the section groups for every document, in ingest order."""
    section_groups = []
    for section_chunks in split_by_key(chunks, SECTION_DEPTH):
        for group_chunks in split_until_under_limit(section_chunks, SECTION_DEPTH):
            section_groups.append(group_record(group_chunks))
    return section_groups
