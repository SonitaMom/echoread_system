import json
import os
import time

from google import genai


def get_helper_keys():
    return [
        value.strip()
        for index in range(1, 5)
        if (
            value := os.getenv(
                f"GEMINI_NOTE_API_KEY_{index}", ""
            ).strip()
        )
    ]


def clean_editor_pages(pages):
    """
    Clean all editor pages in one Gemini request.
    Returns validated page dictionaries without saving them.
    """
    if not isinstance(pages, list) or not pages:
        raise ValueError("There are no pages to clean.")

    expected_pages = {}

    for item in pages:
        if not isinstance(item, dict):
            raise ValueError("Invalid page data.")

        number = item.get("page_number")
        text = item.get("text")

        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or number < 1
            or number in expected_pages
            or not isinstance(text, str)
        ):
            raise ValueError("Invalid or duplicate page data.")

        expected_pages[number] = text

    keys = get_helper_keys()

    if not keys:
        raise RuntimeError("No AI Helper API keys are configured.")

    prompt = """
You are EchoRead's conservative text-formatting assistant.

The input is JSON containing multiple PDF pages.
Clean formatting across all pages in ONE operation.

RULES:
- Return every page exactly once, with its original page_number.
- Preserve the original page order and page boundaries.
- Fix accidental line breaks within sentences and paragraphs.
- Fix excessive spaces and awkward spacing.
- Preserve intentional paragraphs, lists, and readable table structure.
- Do not rewrite, paraphrase, summarize, translate, or expand text.
- Do not correct spelling, grammar, or punctuation.
- Preserve every word, including dialect words and idioms.
- Preserve diacritics, subscript characters, digits, punctuation, and the original language.
- Do not add explanations or Markdown code fences.
- Return cleaned text for every page, even if a page needs no changes.
- Never move text from one page to another.
- Output must follow the provided JSON schema.

Clean the text while changing as little as possible.
"""

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    payload = json.dumps(
        {"pages": pages},
        ensure_ascii=False,
    )

    schema = {
        "type": "object",
        "properties": {
            "pages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page_number": {"type": "integer"},
                        "text": {"type": "string"},
                    },
                    "required": ["page_number", "text"],
                },
            },
        },
        "required": ["pages"],
    }

    errors = []

    for index, api_key in enumerate(keys):
        try:
            client = genai.Client(api_key=api_key)

            response = client.interactions.create(
                model=model,
                input=prompt + "\n\nINPUT JSON:\n" + payload,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema,
                },
            )

            raw_text = (response.output_text or "").strip()

            if not raw_text:
                raise ValueError("AI Helper returned empty output.")

            result = json.loads(raw_text)
            cleaned_pages = result.get("pages")

            if not isinstance(cleaned_pages, list):
                raise ValueError("AI Helper returned invalid page data.")

            cleaned_map = {}

            for item in cleaned_pages:
                if not isinstance(item, dict):
                    raise ValueError("Invalid page result.")

                number = item.get("page_number")
                text = item.get("text")

                if (
                    not isinstance(number, int)
                    or isinstance(number, bool)
                    or number not in expected_pages
                    or number in cleaned_map
                    or not isinstance(text, str)
                ):
                    raise ValueError(
                        "AI Helper returned an invalid or duplicate page."
                    )

                cleaned_map[number] = text

            if set(cleaned_map) != set(expected_pages):
                raise ValueError(
                    "AI Helper missed one or more pages."
                )

            # Return in original page order.
            return [
                {
                    "page_number": number,
                    "text": cleaned_map[number],
                }
                for number in expected_pages
            ]

        except Exception as exc:
            errors.append(exc)

            if index < len(keys) - 1:
                time.sleep(1)

    raise RuntimeError(
        "AI Helper failed. Please try again later."
    ) from errors[-1]

