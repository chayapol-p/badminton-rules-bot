"""
Reads a Mistral reply, for every flow: Mistral Large 4 always thinks before it answers, and sends its reply as
a list of chunks, thinking chunks then text chunks with the answer (Mistral's reasoning docs: there is no
plain-text mode). split_reply_content returns the answer text and the thinking. MAX_ANSWER_TOKENS caps
every call's reply.
"""

from mistralai.client.models import TextChunk, ThinkChunk


# Constants
## An upper bound on the reply's length, thinking included, so one runaway reply can't run up the bill.
## Only used tokens are paid for. 4,096 cut off one long question in most runs (red-card's
## thinking ran to about 3,500 tokens), so the cap is 16,000
MAX_ANSWER_TOKENS = 16_000


# ===== Reading the reply's chunks =====

def split_reply_content(content: str | list | None) -> tuple[str, str]:
    """Returns the reply's answer text and its thinking text."""

    # Models that don't think send plain text; a reply with no content has neither part
    if content is None:
        return "", ""
    if isinstance(content, str):
        return content, ""

    # Large 4 sends thinking chunks, each holding text chunks, then text chunks with the answer
    answer_parts = []
    thinking_parts = []
    for chunk in content:
        if isinstance(chunk, ThinkChunk):
            for thinking_part in chunk.thinking:
                if isinstance(thinking_part, TextChunk):
                    thinking_parts.append(thinking_part.text)
        elif isinstance(chunk, TextChunk):
            answer_parts.append(chunk.text)
    return "".join(answer_parts), "".join(thinking_parts)
