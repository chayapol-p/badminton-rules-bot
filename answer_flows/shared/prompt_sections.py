"""
Builds a system prompt in the sections every answer flow uses: the task, the steps in order and the limits.
The flows with tools add a tools section after them (answer_flows/shared/tool_loop.py build_tools_section).

Why this layout (record 0024):
- Steps as a numbered list, because the order matters: list the parts, find sentences, search, then reply
  (Anthropic prompting best practices: sequential steps when order or completeness matters).
- Limits apart from the steps, each with its reason, so the model can apply a limit to cases it doesn't name
  (Anthropic: Claude generalizes from the explanation), instead of one numbered list that mixes both.
- Each section in its own tag (Mistral prompting guide: clear sections; Anthropic: XML tags).

Use:
    system_prompt = build_system_prompt(task, steps, limits)
"""


# ===== One section =====

def wrap_section(tag: str, body: str) -> str:
    """Returns the body inside its tag, each on its own line."""
    return f"<{tag}>\n{body}\n</{tag}>"


def number_lines(lines: list[str]) -> str:
    """Returns the lines as a numbered list, in order, starting at 1."""
    numbered_lines = []
    for line_number, line in enumerate(lines, start=1):
        numbered_lines.append(f"{line_number}. {line}")
    return "\n".join(numbered_lines)


def bullet_lines(lines: list[str]) -> str:
    """Returns the lines as a bulleted list."""
    return "\n".join(f"- {line}" for line in lines)


# ===== The whole prompt =====

def build_system_prompt(task: str, steps: list[str], limits: list[str]) -> str:
    """Returns the system prompt: the task, then the numbered steps, then the limits."""
    sections = [wrap_section("task", task), wrap_section("steps", number_lines(steps)),
                wrap_section("limits", bullet_lines(limits))]
    return "\n\n".join(sections)
