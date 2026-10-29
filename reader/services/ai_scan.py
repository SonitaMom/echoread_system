import logging
import os
import io
import time
import json
from google import genai

logger = logging.getLogger(__name__)


def get_scan_keys():
    return [
        value.strip()
        for index in range(1, 5)
        if (
            value := os.getenv(
                f"GEMINI_SCAN_API_KEY_{index}", ""
            ).strip()
        )
    ]


def scan_pdf(pdf_bytes):
    """
    Send the original PDF to Gemini.
    Return generated accessible text without saving it.
    """
    keys = get_scan_keys()

    if not keys:
        raise RuntimeError(
            "No AI Scan API keys are configured."
        )

    import json

    prompt = """
Analyze the entire supplied PDF for EchoRead.

Return a JSON object with this exact structure:
{
  "pages": [
    {
      "page_number": 1,
      "text": "Accessible text for PDF page 1"
    }
  ]
}

Rules:
- Include one entry for every PDF page, in original order.
- page_number must be the actual PDF page number, starting at 1.
- Preserve the original wording, spelling, dialects, idioms,
  punctuation, and Khmer diacritics as faithfully as possible.
- Do not silently correct or replace words.
- Describe meaningful charts, pictures, diagrams, and tables.
- Do not invent content.
- Return valid JSON only.
TABLE ACCESSIBILITY RULES:
- Do not output Markdown tables or pipe-separated tables.
- Convert every table into a screen-reader-friendly,
  row-by-row format using plain text.
- Preserve the original column headings and cell values.
- For each row, repeat the column heading before its value
  so the relationship remains clear when read aloud.
- Keep the original row order.
- Do not merge different rows or move values between columns.
"""

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.8-flash",
    )

    errors = []

    for index, api_key in enumerate(keys, start=1):
        try:
            client = genai.Client(api_key=api_key)

            uploaded_file = client.files.upload(
                file=io.BytesIO(pdf_bytes),
                config={"mime_type": "application/pdf"},
            )

            interaction = client.interactions.create(
                model=model,
                input=[
                    {
                        "type": "document",
                        "uri": uploaded_file.uri,
                        "mime_type": "application/pdf",
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": {
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
                    },
                },
            )

            raw_text = (interaction.output_text or "").strip()

            if not raw_text:
                logger.error(
                    "Gemini returned no output_text. Response type=%s; response=%r",
                    type(interaction).__name__,
                    interaction,
                )
                raise ValueError(
                    "Gemini returned no readable output. Check the server log."
                )

            try:
                result = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                logger.error(
                    "Gemini returned invalid JSON. Output preview=%r",
                    raw_text[:1000],
                )
                raise ValueError(
                    "Gemini did not return valid JSON."
                ) from exc
            
            pages = result.get("pages")

            if not isinstance(pages, list) or not pages:
                raise ValueError("Gemini returned no page results.")

            return pages

        except Exception as exc:
            logger.warning(
                "AI Scan failed for key slot %s: %s: %s",
                index,
                type(exc).__name__,
                exc,
            )
            errors.append(exc)

            if index < len(keys):
                time.sleep(1)

    raise RuntimeError(
        "AI Scan failed: API keys exhausted. "
    ) from errors[-1]




