
import json
import logging
import os
import re
import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def get_gemini_keys():
    return [
        value.strip()
        for index in range(1, 5)
        if (value := os.getenv(f"GEMINI_API_KEY_{index}", "").strip())
    ]


def generate_note(question, document_text):
    keys = get_gemini_keys()

    if not keys:
        raise RuntimeError(
            "No Gemini API keys are configured. Check your .env file."
        )

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    prompt = f"""
You are EchoRead, an assistant helping users understand PDF documents.

Answer the user's question using the supplied document.
If the document does not contain enough information, say so clearly.
Do not invent facts.

Return ONLY a JSON object with these two string fields:
- "title": a short, descriptive title for the answer
- "text": the complete answer, with readable paragraphs

USER QUESTION:
{question}

DOCUMENT TEXT:
{document_text}
"""


    # Inside generate_note(), after creating the prompt:
    errors = []
    max_attempts_per_key = 2

    for round_number in range(max_attempts_per_key):
        for index, api_key in enumerate(keys, start=1):
            try:
                client = genai.Client(api_key=api_key)

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3,
                    ),
                )

                raw_text = (response.text or "").strip()

                if not raw_text:
                    raise ValueError("Gemini returned an empty answer.")

                raw_text = re.sub(
                    r"^```(?:json)?\s*|\s*```$",
                    "",
                    raw_text,
                    flags=re.IGNORECASE,
                ).strip()

                result = json.loads(raw_text)
                title = str(result.get("title", "")).strip()
                answer = str(result.get("text", "")).strip()

                if not title or not answer:
                    raise ValueError(
                        "Gemini returned an incomplete answer."
                    )

                return {"title": title, "text": answer}

            except Exception as exc:
                logger.warning(
                    "Gemini attempt failed: round=%s, key_slot=%s, "
                    "error=%s: %s",
                    round_number + 1,
                    index,
                    type(exc).__name__,
                    exc,
                )
                errors.append(exc)

                # Pause before retrying temporary server failures.
                if round_number < max_attempts_per_key:
                    time.sleep(2)

    raise RuntimeError(
        "EchoRead couldn't generate an answer: API 503 ServiceUnavailable. "
    )


