"""
Builds the README pictures for the badminton rules bot in the shop-drawing style shared with co-carpenter:
drafting paper in light mode, a blueprint in dark mode, hand lettering, pencil-red notes, a dimension line
and a title block on every sheet.

Pictures: sheet 1, the rule map (one clause on its own, then the same clause with the clauses the books link to it);
sheet 2, how it works (built once, then each question's path, with model calls and code steps told apart);
sheet 3, refusal in code (one call that did everything, then a gather call, a code gate and a write call);
sheet 4, citations by number (the model types quotes, then the model cites numbers and code copies the quotes).
The clause names and texts come from data/rule_links.json and data/rule_chunks.json (Law 9.1.6 and its links).

  Input:  nothing; every picture is drawn from the data in this file
  Output: <output folder>/<picture>.html and <picture>-dark.html, one <svg> per page
          (export each page to PNG with readme-kit's export_png.py into docs/images/)

Run: python3 docs/diagram/build_pictures.py docs/diagram
Fonts: the .woff2 files and their licences sit in docs/diagram/fonts/.
"""

import pathlib
import sys


# Constants
## Colour tokens: paper (light) and blueprint (dark), the same as co-carpenter's
PAPER = {
    "background": "#f7f8f5", "grid": "rgba(47,95,120,0.13)", "grid_major": "rgba(47,95,120,0.22)",
    "ink": "#1f2a30", "soft": "#55636b", "pencil": "#b0482a",
    "accent": "#2f6b4f", "accent_fill": "rgba(47,107,79,0.12)", "model": "#2f5f9a", "model_fill": "rgba(47,95,154,0.10)",
}
BLUEPRINT = {
    "background": "#123049", "grid": "rgba(190,220,240,0.12)", "grid_major": "rgba(190,220,240,0.22)",
    "ink": "#e4eef5", "soft": "#a9c0cf", "pencil": "#ffb38a",
    "accent": "#8fe0b4", "accent_fill": "rgba(143,224,180,0.14)", "model": "#9cc4f2", "model_fill": "rgba(156,196,242,0.14)",
}

## Fonts: hand lettering for names and notes, mono for small technical labels
HAND_FONT = "'Architects Daughter', 'Comic Sans MS', cursive"
MONO_FONT = "'Geist Mono', ui-monospace, monospace"

## Sheet size and numbering
PROJECT_NAME = "BADMINTON RULES BOT"
SHEET_COUNT = 5
SHEET_WIDTH = 960


# ===== Text helpers =====

# Write hand-lettered text, for names and pencil notes
def hand_text(colors: dict, x: float, y: float, text: str, size: int = 16, color_key: str = "ink",
              anchor: str = "start") -> str:
    return (f'<text x="{x}" y="{y}" fill="{colors[color_key]}" font-size="{size}" font-family="{HAND_FONT}" '
            f'text-anchor="{anchor}">{text}</text>')


# Write small mono text, for labels on connectors and the title block
def mono_text(colors: dict, x: float, y: float, text: str, size: int = 10, color_key: str = "soft",
              anchor: str = "start", spacing: str = "0.08em") -> str:
    return (f'<text x="{x}" y="{y}" fill="{colors[color_key]}" font-size="{size}" font-family="{MONO_FONT}" '
            f'text-anchor="{anchor}" letter-spacing="{spacing}">{text}</text>')


# ===== Line helpers: arrows and the dimension line =====

# Define one arrowhead per colour, so every connector can carry its own
def arrow_markers(colors: dict) -> str:
    markers = []
    for color_key in ("ink", "soft", "accent", "pencil"):
        markers.append(f'<marker id="arrow-{color_key}" markerWidth="9" markerHeight="7" refX="8" refY="3.5" '
                       f'orient="auto"><path d="M0 0.5 L8 3.5 L0 6.5" fill="none" stroke="{colors[color_key]}" '
                       f'stroke-width="1.2"/></marker>')
    return "".join(markers)


# Draw a right-angled connector through a list of (x, y) points, with an arrowhead at the end
def line_arrow(colors: dict, points: list[tuple[float, float]], color_key: str = "ink") -> str:
    path = "M " + " L ".join(f"{x},{y}" for x, y in points)
    return (f'<path d="{path}" fill="none" stroke="{colors[color_key]}" stroke-width="1.3" '
            f'marker-end="url(#arrow-{color_key})"/>')


# Draw a drafting dimension line: a thin line with a slash tick at each end
def dimension_line(colors: dict, start: tuple[float, float], end: tuple[float, float],
                   color_key: str = "pencil") -> str:
    (start_x, start_y), (end_x, end_y) = start, end
    parts = [f'<line x1="{start_x}" y1="{start_y}" x2="{end_x}" y2="{end_y}" stroke="{colors[color_key]}" '
             f'stroke-width="1"/>']
    for tick_x, tick_y in (start, end):
        parts.append(f'<line x1="{tick_x - 6}" y1="{tick_y + 6}" x2="{tick_x + 6}" y2="{tick_y - 6}" '
                     f'stroke="{colors[color_key]}" stroke-width="1.2"/>')
    return "".join(parts)


# ===== Shape helpers: boxes =====

## How each kind of part is drawn (the "Part kinds" rule of the shop-drawing design system): on a sheet with a key,
## the key may give marks a kind meaning: a dashed outline for a model call, rounded corners for a reply to the user,
## hatching for stored data. Red pencil stays for notes only, because a red part would read as a mistake.
PART_KINDS = {
    "plain": {"stroke": "ink", "fill": "", "corner": 0, "hatched": False, "dashed": False},
    "found": {"stroke": "accent", "fill": "accent_fill", "corner": 0, "hatched": False, "dashed": False},
    "code": {"stroke": "accent", "fill": "accent_fill", "corner": 0, "hatched": False, "dashed": False},
    "model": {"stroke": "model", "fill": "model_fill", "corner": 0, "hatched": False, "dashed": True},
    "reply": {"stroke": "ink", "fill": "", "corner": 16, "hatched": False, "dashed": False},
    "data": {"stroke": "ink", "fill": "", "corner": 0, "hatched": True, "dashed": False},
}


# Draw a part on the drawing; opaque so lines behind it stay hidden, styled by its kind
def drawn_box(colors: dict, x: float, y: float, width: float, height: float, kind: str = "plain") -> str:
    style = PART_KINDS[kind]
    corner = style["corner"]
    is_tinted = style["fill"] != ""
    stroke_width = 1.6 if is_tinted else 1.3
    parts = [f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{corner}" fill="{colors["background"]}"/>']
    if style["hatched"]:
        parts.append(hatching(colors, x, y, width, height))
        # A clear band behind the text, so the hatching never runs through the letters
        parts.append(f'<rect x="{x + 8}" y="{y + 10}" width="{width - 16}" height="{height - 16}" '
                     f'fill="{colors["background"]}"/>')
    if is_tinted:
        parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{corner}" '
                     f'fill="{colors[style["fill"]]}"/>')

    # Model calls get a dashed outline, so they differ by shape as well as colour
    dash = ' stroke-dasharray="7,4"' if style["dashed"] else ""
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{corner}" fill="none" '
                 f'stroke="{colors[style["stroke"]]}" stroke-width="{stroke_width}"{dash}/>')
    return "".join(parts)


# Draw diagonal hatching inside a rectangle, the drafting mark for solid material
def hatching(colors: dict, x: float, y: float, width: float, height: float, spacing: int = 9) -> str:
    clip_id = f"hatch-{int(x)}-{int(y)}"
    lines = [f'<line x1="{x + offset}" y1="{y + height}" x2="{x + offset + height}" y2="{y}" '
             f'stroke="{colors["soft"]}" stroke-width="0.7"/>' for offset in range(-int(height), int(width), spacing)]
    return (f'<clipPath id="{clip_id}"><rect x="{x}" y="{y}" width="{width}" height="{height}"/></clipPath>'
            f'<g clip-path="url(#{clip_id})">' + "".join(lines) + '</g>')


# Draw a box with a hand-lettered name, a mono line under it and, when given, a small tag in its corner
def labelled_box(colors: dict, x: float, y: float, width: float, height: float, name: str, sublabel: str,
                 kind: str = "plain", tag: str = "", name_size: int = 15) -> str:
    center_x = x + width / 2
    name_y = y + height / 2 + 2
    parts = [drawn_box(colors, x, y, width, height, kind)]
    if tag:
        tag_color = "model" if kind == "model" else "soft"
        parts.append(mono_text(colors, x + 7, y + 13, tag, size=8, color_key=tag_color))
    parts.append(hand_text(colors, center_x, name_y, name, size=name_size, anchor="middle"))
    parts.append(mono_text(colors, center_x, name_y + 17, sublabel, size=10, anchor="middle", spacing="0"))
    return "".join(parts)


# ===== Sheet helpers: the paper, the border and the title block =====

# Draw drafting paper: background, a fine grid, a coarse grid and the sheet border
def sheet_paper(colors: dict, width: int, height: int) -> str:
    return (f'<defs>'
            f'<pattern id="grid-fine" width="16" height="16" patternUnits="userSpaceOnUse">'
            f'<path d="M16 0H0V16" fill="none" stroke="{colors["grid"]}" stroke-width="0.6"/></pattern>'
            f'<pattern id="grid-coarse" width="80" height="80" patternUnits="userSpaceOnUse">'
            f'<path d="M80 0H0V80" fill="none" stroke="{colors["grid_major"]}" stroke-width="0.9"/></pattern>'
            f'{arrow_markers(colors)}</defs>'
            f'<rect width="{width}" height="{height}" fill="{colors["background"]}"/>'
            f'<rect width="{width}" height="{height}" fill="url(#grid-fine)"/>'
            f'<rect width="{width}" height="{height}" fill="url(#grid-coarse)"/>'
            f'<rect x="12" y="12" width="{width - 24}" height="{height - 24}" fill="none" stroke="{colors["ink"]}" '
            f'stroke-width="1.2"/>')


# Draw the drafting-sheet corner: project, sheet title and sheet number
def title_block(colors: dict, width: int, height: int, sheet_title: str, sheet_number: int) -> str:
    block_right, block_bottom, block_height = width - 12, height - 12, 32
    cell_widths = [176, 136, 96]
    block_left = block_right - sum(cell_widths)
    block_top = block_bottom - block_height
    cell_texts = [PROJECT_NAME, sheet_title, f"SHEET {sheet_number} / {SHEET_COUNT}"]

    # The block's frame
    parts = [f'<rect x="{block_left}" y="{block_top}" width="{sum(cell_widths)}" height="{block_height}" '
             f'fill="{colors["background"]}" stroke="{colors["ink"]}" stroke-width="1.2"/>']

    # One cell per text, with a divider before every cell but the first
    cell_left = block_left
    for cell_index, (cell_width, text) in enumerate(zip(cell_widths, cell_texts)):
        if cell_index > 0:
            parts.append(f'<line x1="{cell_left}" y1="{block_top}" x2="{cell_left}" y2="{block_bottom}" '
                         f'stroke="{colors["ink"]}" stroke-width="1"/>')
        color_key = "ink" if cell_index == 0 else "soft"
        parts.append(mono_text(colors, cell_left + 10, block_top + 20, text, size=10, color_key=color_key))
        cell_left += cell_width
    return "".join(parts)


# ===== Picture: sheet 1, the rule map =====

RULE_MAP_HEIGHT = 620

## The clause search finds, and the four the rule map links to it (from data/rule_links.json)
FOUND_CLAUSE = ("LAW 9.1.6", "below 1.15 m when hit")
LINKED_CLAUSES = [  # name, plain summary, link label, box position (x, y)
    ("ALTERNATIVE SERVICE", "below the server's waist", "REPLACES", (412, 112)),
    ("LAW 17.3 + 3 ITTO", "who calls a service fault", "CITES", (708, 112)),
    ("PARA 9.1.6.1", "wheelchair: below the armpit", "EXCEPTION TO", (412, 376)),
    ("PARA 9.1.6.2", "standing: alternative service", "EXCEPTION TO", (708, 376)),
]
LINKED_BOX_WIDTH, LINKED_BOX_HEIGHT = 212, 64
FOUND_BOX_WIDTH, FOUND_BOX_HEIGHT = 196, 72


# Draw the rule-map sheet: one clause on its own on the left, the same clause with its linked clauses on the right
def rule_map_svg(colors: dict, slug: str) -> str:
    parts = [sheet_paper(colors, SHEET_WIDTH, RULE_MAP_HEIGHT)]

    # The question, as a pencil note across the top
    parts.append(hand_text(colors, 40, 60, "a wheelchair player asks: how high may I serve?", size=19,
                           color_key="pencil"))

    # Left: the clause on its own, and what it misses
    parts.append(mono_text(colors, 40, 92, "SEARCH ALONE"))
    alone_x, alone_y = 40, 240
    parts.append(labelled_box(colors, alone_x, alone_y, FOUND_BOX_WIDTH, FOUND_BOX_HEIGHT, *FOUND_CLAUSE, kind="found"))
    parts.append(hand_text(colors, alone_x, alone_y + FOUND_BOX_HEIGHT + 34, "only the standing limit,", size=15,
                           color_key="pencil"))
    parts.append(hand_text(colors, alone_x, alone_y + FOUND_BOX_HEIGHT + 56, "so the answer is wrong", size=15,
                           color_key="pencil"))

    # A quiet divider between the two halves (solid, because a dashed line means "planned")
    parts.append(half_divider(colors, 300, RULE_MAP_HEIGHT))
    parts.append(mono_text(colors, 412, 92, "SEARCH WITH THE RULE MAP"))

    # Right: the found clause in the middle
    found_x = 412 + (LINKED_BOX_WIDTH * 2 + 84 - FOUND_BOX_WIDTH) / 2
    found_y = 240
    parts.append(labelled_box(colors, found_x, found_y, FOUND_BOX_WIDTH, FOUND_BOX_HEIGHT, *FOUND_CLAUSE, kind="found"))

    # Each linked clause, with a labelled connector into the found clause
    found_center_x = found_x + FOUND_BOX_WIDTH / 2
    for name, summary, link_label, (box_x, box_y) in LINKED_CLAUSES:
        parts.append(labelled_box(colors, box_x, box_y, LINKED_BOX_WIDTH, LINKED_BOX_HEIGHT, name, summary))
        box_center_x = box_x + LINKED_BOX_WIDTH / 2
        is_above = box_y < found_y
        start_y = box_y + LINKED_BOX_HEIGHT if is_above else box_y
        end_y = found_y if is_above else found_y + FOUND_BOX_HEIGHT
        is_left = box_center_x < found_center_x
        entry_x = found_center_x - 40 if is_left else found_center_x + 40
        middle_y = (start_y + end_y) / 2
        parts.append(line_arrow(colors, [(box_center_x, start_y), (box_center_x, middle_y), (entry_x, middle_y),
                                         (entry_x, end_y)]))
        label_y = middle_y - 6 if is_above else middle_y + 16
        parts.append(mono_text(colors, box_center_x + 8, label_y, link_label))

    # The pencil note pointing at the clause that holds the answer
    wheelchair_x, wheelchair_y = LINKED_CLAUSES[2][3]
    parts.append(hand_text(colors, wheelchair_x, wheelchair_y + LINKED_BOX_HEIGHT + 30, "the answer is here",
                           size=16, color_key="pencil"))

    # A dimension line under the right half: one clause found, four arrive through the map
    right_left, right_right = 412, 412 + LINKED_BOX_WIDTH * 2 + 84
    dimension_y = RULE_MAP_HEIGHT - 104
    parts.append(dimension_line(colors, (right_left, dimension_y), (right_right, dimension_y)))
    parts.append(hand_text(colors, (right_left + right_right) / 2, dimension_y - 8,
                           "1 clause found + 7 linked by the books", size=14, color_key="pencil", anchor="middle"))

    parts.append(title_block(colors, SHEET_WIDTH, RULE_MAP_HEIGHT, "RULE MAP", 1))
    title = "One clause, or one clause and the rule map"
    description = ("A wheelchair player asks how high they may serve. Search alone finds Law 9.1.6, the standing limit "
                   "of 1.15 m. With the rule map, seven linked clauses arrive with it: the Alternative service law that "
                   "replaces it, the four clauses that cite it, and two Para Badminton exceptions, one of which says "
                   "wheelchair players serve below the armpit.")
    return wrap_svg(slug, SHEET_WIDTH, RULE_MAP_HEIGHT, title, description, "".join(parts))


# ===== Picture: sheet 2, how it works =====

HOW_IT_WORKS_HEIGHT = 600
STEP_BOX_WIDTH, STEP_BOX_HEIGHT = 136, 60
COLUMN_X = [40, 220, 400, 580, 760]          # five columns, 44 apart
BUILT_ONCE_Y, QUESTION_ROW_Y, ANSWER_ROW_Y = 96, 264, 430


## The key on the kinds sheets: the name of each kind of part
KIND_NAMES = {"model": "model call", "code": "code step", "reply": "reply to the user", "data": "stored data"}


# Draw the key: a small sample of each kind of part the sheet uses, with its name
def drawing_key(colors: dict, x: float, y: float, kinds: list[str]) -> str:
    parts = [mono_text(colors, x, y + 6, "KEY")]
    for row_number, kind in enumerate(kinds):
        row_y = y + 18 + row_number * 20
        style = PART_KINDS[kind]

        # The sample's tint or hatching, then its outline; a sample is too small for the hatching's clear band
        if style["hatched"]:
            parts.append(hatching(colors, x, row_y, 22, 14, spacing=5))
        else:
            parts.append(drawn_box(colors, x, row_y, 22, 14, kind))
        small_corner = style["corner"] / 3
        sample_dash = ' stroke-dasharray="4,2"' if style["dashed"] else ""
        parts.append(f'<rect x="{x}" y="{row_y}" width="22" height="14" rx="{small_corner}" fill="none" '
                     f'stroke="{colors[style["stroke"]]}" stroke-width="1.3"{sample_dash}/>')
        parts.append(mono_text(colors, x + 30, row_y + 11, KIND_NAMES[kind], size=10, spacing="0"))
    return "".join(parts)


# Draw the how-it-works sheet: what is built once, then each question's path through model calls and code steps
def how_it_works_svg(colors: dict, slug: str) -> str:
    parts = [sheet_paper(colors, SHEET_WIDTH, HOW_IT_WORKS_HEIGHT)]
    half_height = STEP_BOX_HEIGHT / 2

    # Built once: a dashed frame around the ingest steps
    parts.append(f'<rect x="28" y="64" width="704" height="112" fill="none" stroke="{colors["soft"]}" '
                 f'stroke-width="1" stroke-dasharray="6,5"/>')
    parts.append(mono_text(colors, 28, 54, "BUILT ONCE"))
    built_once_boxes = [("RULE BOOKS", "3 BWF PDFs", COLUMN_X[0]), ("CLAUSES", "754, one per chunk", COLUMN_X[1]),
                        ("VECTORS", "saved to files", COLUMN_X[2]), ("RULE MAP", "232 links", COLUMN_X[3])]
    for name, sublabel, box_x in built_once_boxes:
        parts.append(labelled_box(colors, box_x, BUILT_ONCE_Y, STEP_BOX_WIDTH, STEP_BOX_HEIGHT, name, sublabel,
                                  kind="data"))
    built_once_middle_y = BUILT_ONCE_Y + half_height
    parts.append(line_arrow(colors, [(COLUMN_X[0] + STEP_BOX_WIDTH, built_once_middle_y), (COLUMN_X[1], built_once_middle_y)]))
    parts.append(line_arrow(colors, [(COLUMN_X[1] + STEP_BOX_WIDTH, built_once_middle_y), (COLUMN_X[2], built_once_middle_y)]))
    clauses_center_x = COLUMN_X[1] + STEP_BOX_WIDTH / 2
    rule_map_center_x = COLUMN_X[3] + STEP_BOX_WIDTH / 2
    parts.append(line_arrow(colors, [(clauses_center_x, BUILT_ONCE_Y), (clauses_center_x, 78), (rule_map_center_x, 78),
                                     (rule_map_center_x, BUILT_ONCE_Y)]))

    # Each question's path, left to right: question, topic check, search, gather call, code gate
    question_row = [("QUESTION", "from the chat", "", "reply"), ("TOPIC CHECK", "about 1 s", "MODEL", "model"),
                    ("SEARCH", "top 5 + linked", "CODE", "code"), ("GATHER CALL", "picks sentences", "MODEL", "model"),
                    ("CODE GATE", "any part answered?", "CODE", "code")]
    for column, (name, sublabel, tag, kind) in enumerate(question_row):
        parts.append(labelled_box(colors, COLUMN_X[column], QUESTION_ROW_Y, STEP_BOX_WIDTH, STEP_BOX_HEIGHT,
                                  name, sublabel, kind=kind, tag=tag))
    question_middle_y = QUESTION_ROW_Y + half_height
    for column in range(4):
        parts.append(line_arrow(colors, [(COLUMN_X[column] + STEP_BOX_WIDTH, question_middle_y),
                                         (COLUMN_X[column + 1], question_middle_y)]))

    # Vectors and the rule map feed the search
    vectors_center_x = COLUMN_X[2] + STEP_BOX_WIDTH / 2
    built_once_bottom = BUILT_ONCE_Y + STEP_BOX_HEIGHT
    parts.append(line_arrow(colors, [(vectors_center_x - 24, built_once_bottom), (vectors_center_x - 24, QUESTION_ROW_Y)]))
    parts.append(line_arrow(colors, [(rule_map_center_x, built_once_bottom), (rule_map_center_x, 214),
                                     (vectors_center_x + 32, 214), (vectors_center_x + 32, QUESTION_ROW_Y)]))

    # The gather call can search again with its tools before it picks sentences: a loop from its bottom back to the
    # search's bottom, below the question row, clear of the off-topic and yes arrows
    gather_loop_x = COLUMN_X[3] + 40
    search_return_x = COLUMN_X[2] + 100
    loop_y = QUESTION_ROW_Y + STEP_BOX_HEIGHT + 40
    parts.append(line_arrow(colors, [(gather_loop_x, QUESTION_ROW_Y + STEP_BOX_HEIGHT), (gather_loop_x, loop_y),
                                     (search_return_x, loop_y), (search_return_x, QUESTION_ROW_Y + STEP_BOX_HEIGHT)]))
    parts.append(mono_text(colors, search_return_x + 12, loop_y + 18, "SEARCHES AGAIN"))

    # Off-topic questions turn away at the topic check
    topic_center_x = COLUMN_X[1] + STEP_BOX_WIDTH / 2
    parts.append(labelled_box(colors, COLUMN_X[1], ANSWER_ROW_Y, STEP_BOX_WIDTH, STEP_BOX_HEIGHT,
                              "POLITE NO", "not badminton", kind="reply"))
    parts.append(line_arrow(colors, [(topic_center_x, QUESTION_ROW_Y + STEP_BOX_HEIGHT), (topic_center_x, ANSWER_ROW_Y)]))
    parts.append(mono_text(colors, topic_center_x + 8, 384, "OFF TOPIC"))

    # The code gate: no answered part goes up to "not covered", any answered part goes down to the write call
    gate_center_x = COLUMN_X[4] + STEP_BOX_WIDTH / 2
    parts.append(labelled_box(colors, COLUMN_X[4], BUILT_ONCE_Y, STEP_BOX_WIDTH, STEP_BOX_HEIGHT,
                              "NOT COVERED", "+ related quotes", kind="reply"))
    parts.append(line_arrow(colors, [(gate_center_x, QUESTION_ROW_Y), (gate_center_x, built_once_bottom)]))
    parts.append(mono_text(colors, gate_center_x + 8, 220, "NO"))
    parts.append(line_arrow(colors, [(gate_center_x, QUESTION_ROW_Y + STEP_BOX_HEIGHT), (gate_center_x, ANSWER_ROW_Y)],
                            color_key="accent"))
    parts.append(mono_text(colors, gate_center_x + 8, 384, "YES"))

    # The answer row, right to left: write call, code checks, answer
    answer_row = [("ANSWER", "with its sources", "", "reply", COLUMN_X[2]),
                  ("CODE CHECKS", "copies each quote", "CODE", "code", COLUMN_X[3]),
                  ("WRITE CALL", "no tools, [n] marks", "MODEL", "model", COLUMN_X[4])]
    for name, sublabel, tag, kind, box_x in answer_row:
        parts.append(labelled_box(colors, box_x, ANSWER_ROW_Y, STEP_BOX_WIDTH, STEP_BOX_HEIGHT, name, sublabel,
                                  kind=kind, tag=tag))
    answer_middle_y = ANSWER_ROW_Y + half_height
    parts.append(line_arrow(colors, [(COLUMN_X[4], answer_middle_y), (COLUMN_X[3] + STEP_BOX_WIDTH, answer_middle_y)]))
    parts.append(line_arrow(colors, [(COLUMN_X[3], answer_middle_y), (COLUMN_X[2] + STEP_BOX_WIDTH, answer_middle_y)],
                            color_key="accent"))

    # A dimension line for the wait, and the pencil note that sums up the design
    dimension_y = 516
    parts.append(dimension_line(colors, (COLUMN_X[2], dimension_y), (COLUMN_X[4] + STEP_BOX_WIDTH, dimension_y)))
    parts.append(hand_text(colors, (COLUMN_X[2] + COLUMN_X[4] + STEP_BOX_WIDTH) / 2, dimension_y - 8,
                           "median 34 s per answer", size=14, color_key="pencil", anchor="middle"))
    parts.append(hand_text(colors, 40, 548, "the model picks and writes,", size=16, color_key="pencil"))
    parts.append(hand_text(colors, 40, 570, "code makes every exact decision", size=16, color_key="pencil"))

    parts.append(drawing_key(colors, 40, ANSWER_ROW_Y - 4, ["model", "code", "reply", "data"]))

    parts.append(title_block(colors, SHEET_WIDTH, HOW_IT_WORKS_HEIGHT, "HOW IT WORKS", 2))
    title = "How the bot answers a question"
    description = ("Built once: 3 BWF rule books become 754 clauses, saved vectors and a rule map of 232 links. For each "
                   "question, a small model checks the topic and turns off-topic questions away. Code searches the top 5 "
                   "clauses plus their linked clauses, a gather call picks sentences and may search again with its tools, "
                   "and a code gate says not covered "
                   "when no part has a sentence. Otherwise a write call with no tools writes the answer with numbered "
                   "markers, and code checks the markers and copies each quote. Model calls are blue and dashed, code steps "
                   "green, replies to the user rounded, and the built-once data hatched.")
    return wrap_svg(slug, SHEET_WIDTH, HOW_IT_WORKS_HEIGHT, title, description, "".join(parts))


# ===== Helpers for the before-and-after sheets =====

# Draw a quiet divider line between the two halves of a sheet
def half_divider(colors: dict, x: float, sheet_height: int) -> str:
    return (f'<line x1="{x}" y1="96" x2="{x}" y2="{sheet_height - 72}" stroke="{colors["grid_major"]}" '
            f'stroke-width="1.4"/>')


# Draw a straight connector from the bottom of one box to the top of the box below it
def arrow_down(colors: dict, center_x: float, from_y: float, to_y: float, color_key: str = "ink") -> str:
    return line_arrow(colors, [(center_x, from_y), (center_x, to_y)], color_key=color_key)


# Draw a straight connector from the right side of one box to the left side of the next
def arrow_right(colors: dict, from_x: float, to_x: float, middle_y: float, color_key: str = "ink") -> str:
    return line_arrow(colors, [(from_x, middle_y), (to_x, middle_y)], color_key=color_key)


# Draw the result under the "after" half: a pencil dimension line with the measured number above it
def result_dimension(colors: dict, left_x: float, right_x: float, line_y: float, result: str) -> str:
    return (dimension_line(colors, (left_x, line_y), (right_x, line_y))
            + hand_text(colors, (left_x + right_x) / 2, line_y - 8, result, size=14, color_key="pencil", anchor="middle"))


# ===== Picture: sheet 3, refusal in code =====

BEFORE_AFTER_HEIGHT = 620
PART_HEIGHT = 64


# Draw the refusal sheet: one call that did every job, then a gather call, a code gate and a write call
def refusal_in_code_svg(colors: dict, slug: str) -> str:
    parts = [sheet_paper(colors, SHEET_WIDTH, BEFORE_AFTER_HEIGHT)]

    # Before: one model call searched, decided and wrote
    parts.append(mono_text(colors, 40, 92, "BEFORE: ONE CALL DID EVERY JOB"))
    before_x, before_width = 40, 300
    before_center_x = before_x + before_width / 2
    parts.append(labelled_box(colors, before_x, 124, before_width, PART_HEIGHT, "QUESTION", "from the chat", kind="reply"))
    parts.append(arrow_down(colors, before_center_x, 124 + PART_HEIGHT, 240))
    parts.append(labelled_box(colors, before_x, 240, before_width, PART_HEIGHT, "ONE CALL", "searches, decides, writes",
                              kind="model", tag="MODEL"))
    parts.append(arrow_down(colors, before_center_x, 240 + PART_HEIGHT, 356))
    parts.append(labelled_box(colors, before_x, 356, before_width, PART_HEIGHT, "ANSWER OR REFUSAL",
                              "the model's own call", kind="reply"))
    parts.append(hand_text(colors, before_x, 456, "refusals flipped between runs", size=16, color_key="pencil"))
    parts.append(hand_text(colors, before_x, 478, "on the same evidence", size=16, color_key="pencil"))

    parts.append(half_divider(colors, 380, BEFORE_AFTER_HEIGHT))

    # After: each part of the work has one owner
    parts.append(mono_text(colors, 420, 92, "AFTER: ONE JOB EACH"))
    left_x, right_x, box_width = 420, 700, 200
    left_center_x = left_x + box_width / 2
    parts.append(labelled_box(colors, left_x, 124, box_width, PART_HEIGHT, "GATHER CALL", "picks sentences per part",
                              kind="model", tag="MODEL"))
    parts.append(arrow_down(colors, left_center_x, 124 + PART_HEIGHT, 240))
    parts.append(labelled_box(colors, left_x, 240, box_width, PART_HEIGHT, "CODE GATE", "any part has a sentence?",
                              kind="code", tag="CODE"))

    # No part answered: code says "not covered"; any part answered: on to the write call
    gate_middle_y = 240 + PART_HEIGHT / 2
    parts.append(arrow_right(colors, left_x + box_width, right_x, gate_middle_y))
    parts.append(mono_text(colors, left_x + box_width + 12, gate_middle_y - 8, "NO"))
    parts.append(labelled_box(colors, right_x, 240, box_width, PART_HEIGHT, "NOT COVERED", "+ related quotes", kind="reply"))
    parts.append(arrow_down(colors, left_center_x, 240 + PART_HEIGHT, 356, color_key="accent"))
    parts.append(mono_text(colors, left_center_x + 8, 336, "YES"))
    parts.append(labelled_box(colors, left_x, 356, box_width, PART_HEIGHT, "WRITE CALL", "no tools, writes from picks",
                              kind="model", tag="MODEL"))
    write_middle_y = 356 + PART_HEIGHT / 2
    parts.append(arrow_right(colors, left_x + box_width, right_x, write_middle_y))
    parts.append(labelled_box(colors, right_x, 356, box_width, PART_HEIGHT, "ANSWER", "gaps said in words", kind="reply"))

    # The measured result (record 0023), the key and the title block
    parts.append(result_dimension(colors, left_x, right_x + box_width, 500,
                                  "0 false refusals in 9 runs, 1 missed in 126"))
    parts.append(drawing_key(colors, 40, 500, ["model", "code", "reply"]))
    parts.append(title_block(colors, SHEET_WIDTH, BEFORE_AFTER_HEIGHT, "REFUSAL IN CODE", 3))
    title = "Refusal decided in code"
    description = ("Before: one model call searched, decided whether to refuse and wrote the answer, and its refusals "
                   "flipped between runs on the same evidence. After: a gather call picks sentences for each part, a "
                   "code gate says not covered when no part has a sentence, and a write call with no tools writes the "
                   "answer. Result: 0 false refusals in 9 runs, and 1 missed refusal in 126.")
    return wrap_svg(slug, SHEET_WIDTH, BEFORE_AFTER_HEIGHT, title, description, "".join(parts))


# ===== Picture: sheet 4, citations by number =====

## The sentence the example cites: Law 9.1.6, as printed in the Laws of Badminton (data/rule_chunks.json)
EXAMPLE_SENTENCE = "[1] the whole shuttle shall be below 1.15 metres from the surface ..."


# Draw the citations sheet: the model typing its own quotes, then the model citing numbers and code copying quotes
def citations_by_number_svg(colors: dict, slug: str) -> str:
    parts = [sheet_paper(colors, SHEET_WIDTH, BEFORE_AFTER_HEIGHT)]

    # Before: the model typed each quote itself
    parts.append(mono_text(colors, 40, 92, "BEFORE: THE MODEL TYPED THE QUOTES"))
    before_x, before_width = 40, 300
    before_center_x = before_x + before_width / 2
    parts.append(labelled_box(colors, before_x, 124, before_width, PART_HEIGHT, "SOURCES", "clauses found by search", kind="data"))
    parts.append(arrow_down(colors, before_center_x, 124 + PART_HEIGHT, 240))
    parts.append(labelled_box(colors, before_x, 240, before_width, PART_HEIGHT, "WRITE CALL",
                              "types the answer and the quotes", kind="model", tag="MODEL"))
    parts.append(arrow_down(colors, before_center_x, 240 + PART_HEIGHT, 356))
    parts.append(labelled_box(colors, before_x, 356, before_width, PART_HEIGHT, "ANSWER",
                              "quotes as the model typed them", kind="reply"))
    parts.append(hand_text(colors, before_x, 456, "a quote could be reworded or cut:", size=16, color_key="pencil"))
    parts.append(hand_text(colors, before_x, 478, "about 1 answer in 30 was", size=16, color_key="pencil"))

    parts.append(half_divider(colors, 380, BEFORE_AFTER_HEIGHT))

    # After: the model points at numbered sentences, and code does the copying and checking
    parts.append(mono_text(colors, 420, 92, "AFTER: THE MODEL CITES, CODE COPIES"))
    full_width = 480
    parts.append(labelled_box(colors, 420, 124, full_width, PART_HEIGHT, "NUMBERED SENTENCES", EXAMPLE_SENTENCE, kind="data"))
    left_x, right_x, box_width = 420, 700, 200
    left_center_x = left_x + box_width / 2
    right_center_x = right_x + box_width / 2
    parts.append(arrow_down(colors, left_center_x, 124 + PART_HEIGHT, 240))
    parts.append(labelled_box(colors, left_x, 240, box_width, PART_HEIGHT, "WRITE CALL", "cites [1], types no quote",
                              kind="model", tag="MODEL"))
    parts.append(arrow_right(colors, left_x + box_width, right_x, 240 + PART_HEIGHT / 2))
    parts.append(labelled_box(colors, right_x, 240, box_width, PART_HEIGHT, "CHECK AND COPY", "checks [n], copies its sentence",
                              kind="code", tag="CODE"))
    parts.append(arrow_down(colors, right_center_x, 240 + PART_HEIGHT, 356, color_key="accent"))
    parts.append(labelled_box(colors, right_x, 356, box_width, PART_HEIGHT, "ANSWER", "[1] as the book prints it", kind="reply"))

    # The measured result (records 0023 and 0027), the key and the title block
    parts.append(result_dimension(colors, left_x, right_x + box_width, 500, "0 citation problems in 369 answers"))
    parts.append(drawing_key(colors, 40, 500, ["model", "code", "reply", "data"]))
    parts.append(title_block(colors, SHEET_WIDTH, BEFORE_AFTER_HEIGHT, "CITATIONS", 4))
    title = "Citations by number"
    description = ("Before: the write call typed each quote itself, and about 1 answer in 30 had a quote reworded or "
                   "cut. After: the model sees numbered sentences and cites them by number, and code checks every "
                   "number and copies each sentence in as the rule book prints it. Result: 0 citation problems in 369 answers.")
    return wrap_svg(slug, SHEET_WIDTH, BEFORE_AFTER_HEIGHT, title, description, "".join(parts))


# ===== Picture: sheet 5, why each part is there =====

## Layout: the assembly row on top, the schedule below it, then the general notes and the key
ASSEMBLY_TOP_Y = 176
ASSEMBLY_STEP_WIDTH, ASSEMBLY_STEP_GAP, ASSEMBLY_STEP_HEIGHT = 112, 15, 60
BALLOON_RADIUS = 12
SCHEDULE_LEFT_X, SCHEDULE_RIGHT_X = 36, 924
SCHEDULE_TOP_Y = 300
RESULT_LEFT_X = 430
SCALE_LEFT_X, SCALE_RIGHT_X = 440, 780

## The bot today, left to right: name, sublabel, kind of part
BOT_TODAY_STEPS = [("TOPIC CHECK", "about 1 s", "model"), ("SEARCH", "top 5 + rule map", "code"),
                   ("GATHER CALL", "may search again", "model"), ("CODE GATE", "any part answered?", "code"),
                   ("WRITE CALL", "no tools", "model"), ("CODE CHECKS", "copies quotes", "code"),
                   ("ANSWER", "quote pop-ups", "reply")]

## Which balloons point at which step, by the step's place in BOT_TODAY_STEPS
BALLOONS_BY_STEP = {0: [6], 1: [1, 2], 2: [3], 3: [4], 5: [4], 6: [5]}

## The schedule: one row per balloon, in the order the tests were run. A row's scale holds its points (value, is the
## winner, label) or its ranges (low, high, is the winner); its gap is the dimension drawn between two values
SCHEDULE_ROWS = [
    {"balloon": 1, "part": "SEARCH", "question": "which search finds the right clause?",
     "measure": "recall@5, 24 questions", "record": "record 0006",
     "results": [("vector search", "0.840", True), ("hybrid (keyword + vector)", "0.771", False),
                 ("keyword (BM25)", "0.576", False)],
     "scale": (0.5, 0.9, "0.5", "0.9"),
     "points": [(0.840, True, "0.840"), (0.771, False, "0.771"), (0.576, False, "0.576")],
     "gap": (0.771, 0.840, "0.069")},
    {"balloon": 2, "part": "SEARCH", "question": "how much should the model read?",
     "measure": "answers passed, of 22", "record": "record 0009",
     "results": [("top 5 + rule map", "16", True), ("top 55 + rule map, at 2.8x the cost", "15", False),
                 ("top 5 alone", "14", False)],
     "scale": (10, 22, "10", "22"),
     "points": [(16, True, "16"), (15, False, "15"), (14, False, "14")],
     "gap": (14, 16, "the rule map: +2")},
    {"balloon": 3, "part": "GATHER CALL", "question": "should the model search by itself?",
     "measure": "answers passed over 3 runs, of 30", "record": "record 0021",
     "results": [("C · RAG first, then tools", "26", True), ("B · agent only", "22", False),
                 ("A · plain RAG", "17", False)],
     "scale": (10, 30, "10", "30"),
     "points": [(26, True, "26"), (22, False, "22"), (17, False, "17")],
     "gap": (22, 26, "+4")},
    # No scale here: these are counts of problems, and the winner's count is zero
    {"balloon": 4, "part": "CODE GATE, CODE CHECKS", "question": "who does the exact work: model or code?",
     "measure": "quote problems, and refusal errors", "record": "record 0023",
     "results": [("code copies the quotes", "0 in 369 answers", True), ("the model typing them", "about 1 in 30", False),
                 ("code decides refusals", "0 false in 9 runs", True),
                 ("the model deciding", "flipped between runs", False)]},
    {"balloon": 5, "part": "ANSWER", "question": "what answer do people want to read?",
     "measure": "score out of 100, range over 3 runs", "record": "record 0027",
     "results": [("one connected answer, inline citations", "89.8 to 92.1", True),
                 ("one line per part of the question", "82.0 to 84.6", False)],
     "scale": (80, 95, "80", "95"),
     "ranges": [(89.8, 92.1, True), (82.0, 84.6, False)],
     "gap": (84.6, 89.8, "5.2 apart: no overlap")},
    {"balloon": 6, "part": "TOPIC CHECK", "question": "how fast can it turn a question away?",
     "measure": "seconds, shorter is better", "record": "docs/specs",
     "results": [("a small model screens first", "about 1 s", True),
                 ("full search, then refuse (slowest 70 s)", "median 23 s", False)],
     "scale": (0, 25, "0 s", "25 s"),
     "points": [(1, True, "1 s"), (23, False, "23 s")],
     "gap": (1, 23, "22 s sooner")},
]

## How every part was measured, as the sheet's general notes
GENERAL_NOTES = [
    "1. start: 39 test questions, 27 to tune on, 12 locked away until the end",
    "2. later sets: 11 unseen questions, then 41 (14 must be refused),",
    "    then 24 topic-check questions (6 must be turned away)",
    "3. a win needs 2 or more questions apart. The same flow scored 31, then 35",
    "    of 41, so from Phase 2 every flow runs 3 times, and the ranges must not overlap",
]


# Draw a balloon: the numbered circle that ties a part to its row in the schedule
def balloon(colors: dict, center_x: float, center_y: float, number: int, radius: float = BALLOON_RADIUS) -> str:
    return (f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="{colors["background"]}" '
            f'stroke="{colors["pencil"]}" stroke-width="1.4"/>'
            + hand_text(colors, center_x, center_y + radius * 0.42, str(number), size=int(radius * 1.25),
                        color_key="pencil", anchor="middle"))


# Return how far below a row's top its scale sits: under the last result line, with room for the dimension line
def scale_axis_offset(row: dict) -> int:
    return 22 + len(row["results"]) * 18 + 24


# Return the x position of a value on a schedule row's scale
def scale_x(value: float, scale: tuple) -> float:
    scale_start, scale_end = scale[0], scale[1]
    return SCALE_LEFT_X + (value - scale_start) / (scale_end - scale_start) * (SCALE_RIGHT_X - SCALE_LEFT_X)


# Draw the assembly row: the bot's steps, joined left to right, with a balloon over each part a test chose
def assembly_row(colors: dict) -> str:
    parts = []
    for step_number, (name, sublabel, kind) in enumerate(BOT_TODAY_STEPS):
        step_x = 40 + step_number * (ASSEMBLY_STEP_WIDTH + ASSEMBLY_STEP_GAP)
        step_center_x = step_x + ASSEMBLY_STEP_WIDTH / 2
        parts.append(labelled_box(colors, step_x, ASSEMBLY_TOP_Y, ASSEMBLY_STEP_WIDTH, ASSEMBLY_STEP_HEIGHT, name,
                                  sublabel, kind=kind, name_size=13))
        if step_number > 0:
            arrow_y = ASSEMBLY_TOP_Y + ASSEMBLY_STEP_HEIGHT / 2
            parts.append(line_arrow(colors, [(step_x - ASSEMBLY_STEP_GAP, arrow_y), (step_x, arrow_y)]))

        # Two balloons on one part sit side by side; each leader runs straight down to the part's top edge
        balloon_numbers = BALLOONS_BY_STEP.get(step_number, [])
        for balloon_index, number in enumerate(balloon_numbers):
            offset = (balloon_index - (len(balloon_numbers) - 1) / 2) * 32
            balloon_x, balloon_y = step_center_x + offset, ASSEMBLY_TOP_Y - 36
            parts.append(f'<line x1="{balloon_x}" y1="{balloon_y + BALLOON_RADIUS}" x2="{balloon_x}" '
                         f'y2="{ASSEMBLY_TOP_Y}" stroke="{colors["pencil"]}" stroke-width="1"/>')
            parts.append(balloon(colors, balloon_x, balloon_y, number))
    return "".join(parts)


# Draw a row's scale: a soft axis with its end labels, the points or ranges on it, and the pencil dimension of the gap
def schedule_scale(colors: dict, row: dict, row_y: float) -> str:
    scale = row["scale"]
    axis_y = row_y + scale_axis_offset(row)
    parts = [f'<line x1="{SCALE_LEFT_X}" y1="{axis_y}" x2="{SCALE_RIGHT_X}" y2="{axis_y}" stroke="{colors["soft"]}" '
             f'stroke-width="0.8"/>']
    point_xs = [scale_x(value, scale) for value, _, _ in row.get("points", [])]
    for end_x, end_label in ((SCALE_LEFT_X, scale[2]), (SCALE_RIGHT_X, scale[3])):
        parts.append(f'<line x1="{end_x}" y1="{axis_y - 3}" x2="{end_x}" y2="{axis_y + 3}" stroke="{colors["soft"]}" '
                     f'stroke-width="0.8"/>')
        is_crowded = any(abs(point_x - end_x) < 30 for point_x in point_xs)
        if not is_crowded:
            parts.append(mono_text(colors, end_x, axis_y + 15, end_label, size=8, anchor="middle", spacing="0"))

    # Points: the winner solid in ink, the others open in soft, each with its value under it
    for value, is_winner, label in row.get("points", []):
        point_x = scale_x(value, scale)
        fill_key = "ink" if is_winner else "background"
        stroke_key = "ink" if is_winner else "soft"
        parts.append(f'<circle cx="{point_x}" cy="{axis_y}" r="4" fill="{colors[fill_key]}" '
                     f'stroke="{colors[stroke_key]}" stroke-width="1.3"/>')
        parts.append(mono_text(colors, point_x, axis_y + 15, label, size=9, color_key=stroke_key, anchor="middle",
                               spacing="0"))

    # Ranges: a thick bar from the lowest to the highest of three runs
    for low, high, is_winner in row.get("ranges", []):
        color_key = "ink" if is_winner else "soft"
        low_x, high_x = scale_x(low, scale), scale_x(high, scale)
        parts.append(f'<rect x="{low_x}" y="{axis_y - 3}" width="{high_x - low_x}" height="6" '
                     f'fill="{colors[color_key]}"/>')

    # The gap between the winner and the value it beat, as a pencil dimension line with its size beside it
    gap_start, gap_end, gap_label = row["gap"]
    start_x, end_x = scale_x(gap_start, scale), scale_x(gap_end, scale)
    dimension_y = axis_y - 16
    parts.append(dimension_line(colors, (start_x, dimension_y), (end_x, dimension_y)))
    parts.append(hand_text(colors, max(start_x, end_x) + 12, dimension_y + 5, gap_label, size=13, color_key="pencil"))
    return "".join(parts)


# Draw one row of the schedule: balloon, part and question, what won and what it beat, the scale, and the record
def schedule_row(colors: dict, row: dict, row_y: float) -> str:
    parts = [balloon(colors, SCHEDULE_LEFT_X + 24, row_y + 26, row["balloon"])]

    # The part, the question it answered, and what was measured
    parts.append(hand_text(colors, SCHEDULE_LEFT_X + 50, row_y + 24, row["part"], size=15))
    parts.append(mono_text(colors, SCHEDULE_LEFT_X + 50, row_y + 44, row["question"], size=10, color_key="ink",
                           spacing="0"))
    parts.append(mono_text(colors, SCHEDULE_LEFT_X + 50, row_y + 60, row["measure"], size=9, spacing="0"))

    # One line per contender: the name in small mono on the left, the score in hand lettering in its own column on
    # the right, so the two never read as one string. The winner is in ink, the rest in soft
    for line_number, (name, score, is_winner) in enumerate(row["results"]):
        line_y = row_y + 22 + line_number * 18
        color_key = "ink" if is_winner else "soft"
        parts.append(mono_text(colors, RESULT_LEFT_X, line_y, name, size=10, color_key=color_key, spacing="0"))
        parts.append(hand_text(colors, SCALE_RIGHT_X, line_y + 1, score, size=15, color_key=color_key, anchor="end"))
    if "scale" in row:
        parts.append(schedule_scale(colors, row, row_y))

    # The record that holds the full result
    parts.append(mono_text(colors, SCHEDULE_RIGHT_X - 10, row_y + 22, row["record"], size=9, anchor="end",
                           spacing="0"))
    return "".join(parts)


# Return the height a schedule row needs: a scale row needs room for its axis, a text row for its lines
def schedule_row_height(row: dict) -> int:
    if "scale" in row:
        return scale_axis_offset(row) + 28
    return 34 + len(row["results"]) * 18


# Draw the key for this sheet: the balloon, the dimension line, and the kinds of part
def assembly_key(colors: dict, x: float, y: float) -> str:
    parts = [mono_text(colors, x, y + 6, "KEY")]
    parts.append(balloon(colors, x + 11, y + 26, 1, radius=9))
    parts.append(mono_text(colors, x + 30, y + 30, "balloon: a test that chose a part", size=10, spacing="0"))
    parts.append(dimension_line(colors, (x + 2, y + 52), (x + 22, y + 52)))
    parts.append(mono_text(colors, x + 34, y + 56, "the winner's lead", size=10, spacing="0"))
    parts.append(drawing_key(colors, x, y + 58, ["model", "code", "reply"]).replace(">KEY<", "><", 1))
    return "".join(parts)


# Draw the sheet: the bot as an assembly, each part's test in the schedule, and how everything was measured
def why_each_part_svg(colors: dict, slug: str) -> str:
    # Work out the schedule's height first, so the sheet knows how tall it is
    row_heights = [schedule_row_height(row) for row in SCHEDULE_ROWS]
    schedule_bottom_y = SCHEDULE_TOP_Y + 26 + sum(row_heights)
    notes_y = schedule_bottom_y + 44
    sheet_height = int(notes_y + len(GENERAL_NOTES) * 22 + 110)

    parts = [sheet_paper(colors, SHEET_WIDTH, sheet_height)]

    # The heading, then the assembly
    parts.append(hand_text(colors, 36, 66, "WHY EACH PART IS THERE", size=26))
    parts.append(mono_text(colors, 36, 92, "assembly of the bot today: each balloon points to the test that chose a part"))
    parts.append(assembly_row(colors))

    # The schedule: a header, then one row per balloon with a soft rule between rows
    parts.append(mono_text(colors, SCHEDULE_LEFT_X, SCHEDULE_TOP_Y, "SCHEDULE · PART AND QUESTION"))
    parts.append(mono_text(colors, RESULT_LEFT_X, SCHEDULE_TOP_Y, "WHAT WON, AND WHAT IT BEAT"))
    parts.append(mono_text(colors, SCHEDULE_RIGHT_X - 10, SCHEDULE_TOP_Y, "RECORD", anchor="end"))
    row_y = SCHEDULE_TOP_Y + 12
    parts.append(f'<line x1="{SCHEDULE_LEFT_X}" y1="{row_y}" x2="{SCHEDULE_RIGHT_X}" y2="{row_y}" '
                 f'stroke="{colors["ink"]}" stroke-width="1.2"/>')
    for row, row_height in zip(SCHEDULE_ROWS, row_heights):
        parts.append(schedule_row(colors, row, row_y + 6))
        row_y += row_height
        parts.append(f'<line x1="{SCHEDULE_LEFT_X}" y1="{row_y}" x2="{SCHEDULE_RIGHT_X}" y2="{row_y}" '
                     f'stroke="{colors["soft"]}" stroke-width="0.8"/>')

    # The general notes: how every part was measured
    parts.append(mono_text(colors, SCHEDULE_LEFT_X, notes_y, "GENERAL NOTES"))
    for line_number, note_line in enumerate(GENERAL_NOTES):
        is_continuation = note_line.startswith(" ")
        indent = 18 if is_continuation else 0
        parts.append(hand_text(colors, SCHEDULE_LEFT_X + indent, notes_y + 24 + line_number * 22, note_line.strip(),
                               size=14))

    # The key on the right, and the title block in the corner
    parts.append(assembly_key(colors, 690, notes_y - 6))
    parts.append(title_block(colors, SHEET_WIDTH, sheet_height, "WHY EACH PART", 5))
    title = "Why each part is there"
    description = ("The bot today as an assembly of seven steps: topic check, search, gather call, code gate, write "
                   "call, code checks and answer. Numbered balloons tie each part to the test that chose it. 1, search: "
                   "vector search won with recall@5 0.840 against hybrid 0.771. 2, search: the top 5 clauses plus the "
                   "rule map passed 16 of 22, against 14 without the map and 15 for the top 55 at 2.8 times the cost. "
                   "3, gather call: RAG first, then tools passed 26 of 30, against 22 for an agent alone. 4, code gate "
                   "and code checks: code copying quotes left 0 problems in 369 answers, and code deciding refusals "
                   "left 0 false refusals in 9 runs. 5, answer: one connected answer scored 89.8 to 92.1 against 82.0 "
                   "to 84.6. 6, topic check: a small model turns off-topic questions away in about 1 s instead of a "
                   "median 23 s. General notes give the test sets and the rule of 3 runs with no overlap.")
    return wrap_svg(slug, SHEET_WIDTH, sheet_height, title, description, "".join(parts))


# ===== Page helpers =====

# Wrap the drawing in an accessible <svg> with a title and a description
def wrap_svg(slug: str, width: int, height: int, title: str, description: str, body: str) -> str:
    return (f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-labelledby="{slug}-title {slug}-desc">'
            f'<title id="{slug}-title">{title}</title><desc id="{slug}-desc">{description}</desc>{body}</svg>')


# Write one HTML page around a drawing, loading the bundled fonts
def page(colors: dict, heading: str, svg: str, width: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{heading} · badminton rules bot</title>
  <style>
    @font-face {{ font-family: 'Architects Daughter'; src: url('fonts/architects-daughter-latin-400-normal.woff2') format('woff2'); }}
    @font-face {{ font-family: 'Geist Mono'; src: url('fonts/geist-mono-latin-400-normal.woff2') format('woff2'); }}
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: {colors["background"]}; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 2rem; }}
    .diagram-container {{ width: 100%; max-width: 1200px; overflow-x: auto; }}
    svg {{ width: 100%; min-width: {width}px; display: block; }}
  </style>
</head>
<body>
  <div class="diagram-container">
{svg}
  </div>
</body>
</html>
"""


# ===== Write every picture, light and dark =====

PICTURES = [  # file name, page heading, drawing function
    ("rule-map", "One clause, or one clause and the rule map", rule_map_svg),
    ("how-it-works", "How the bot answers a question", how_it_works_svg),
    ("refusal-in-code", "Refusal decided in code", refusal_in_code_svg),
    ("citations-by-number", "Citations by number", citations_by_number_svg),
    ("why-each-part", "Why each part is there", why_each_part_svg),
]


# Write each picture as a light and a dark HTML page into the output folder
def write_pictures(output_folder: str) -> None:
    output_path = pathlib.Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    for suffix, colors in (("", PAPER), ("-dark", BLUEPRINT)):
        for name, heading, draw_function in PICTURES:
            slug = f"{name}{suffix}"
            (output_path / f"{slug}.html").write_text(page(colors, heading, draw_function(colors, slug), SHEET_WIDTH))


if __name__ == "__main__":
    write_pictures(sys.argv[1])
