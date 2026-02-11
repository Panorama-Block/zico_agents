"""
Shared markdown formatting instructions appended to all agent system prompts.

Ensures LLMs produce clean, well-structured markdown that the frontend
react-markdown renderer can display properly.
"""

MARKDOWN_INSTRUCTIONS = """

## Response Formatting Rules

Format ALL responses using clean Markdown so they render well in the chat UI:

- Use `##` or `###` for section headers, with a **blank line before and after** each header.
- Use `**bold**` for important values (prices, amounts, token names, network names, percentages). Never use single `*` for emphasis.
- Use bullet lists (`- item`) or numbered lists (`1. item`), each item on its **own line**.
- Add a **blank line** between paragraphs and before/after lists.
- Use tables (`| col1 | col2 |`) for structured comparisons when appropriate.
- Keep responses concise and well-organized. Avoid walls of text.
- Never use raw HTML tags.
"""
