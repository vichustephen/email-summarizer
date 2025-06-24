"""Shared utilities for interacting with LLM responses used by different processors.

This module centralizes common logic that was duplicated across
`llama_cpp_processor.py` and `llm_processor.py`. Keeping it here avoids code
duplication and makes future maintenance easier.
"""
from __future__ import annotations

import json
import re
from typing import Dict, Optional, Type

from loguru import logger


def extract_json_from_response(response: Dict, model_class: Type) -> Optional[Dict]:
    """Extract JSON content from an LLM response and validate it with a Pydantic model.

    Both the HTTP-based LLM (`llm_processor.py`) and the local llama.cpp based LLM
    (`llama_cpp_processor.py`) return a `choices` list but the exact payload shape
    differs slightly. This helper normalises the structure so the calling code
    does not need to worry about those differences.

    Args:
        response: Raw response dictionary returned by the LLM.
        model_class: A Pydantic model class that exposes ``model_validate_json``
            and ``model_dump`` utility methods.

    Returns:
        A ``dict`` representation of the validated data or ``None`` when the
        response is invalid or could not be parsed/validated.
    """
    try:
        if not response.get("choices"):
            logger.warning("No 'choices' in LLM response.")
            return None

        # Attempt to find the content field which may be either under
        # choices[0]['message']['content'] (OpenAI style) or choices[0]['text']
        choice = response["choices"][0]
        content: Optional[str]
        if isinstance(choice, dict):
            content = (
                choice.get("message", {}).get("content")
                if isinstance(choice.get("message"), dict)
                else None
            )
            if content is None:
                content = choice.get("text")
        else:
            logger.warning("Unexpected format for choice: %s", type(choice))
            return None

        if not content:
            logger.warning("No content found in LLM response choice.")
            return None

        # Remove any <think>...</think> blocks sometimes produced by some models
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # Use the model class to validate and convert to a plain dict
        validated_data = model_class.model_validate_json(content)
        return validated_data.model_dump()

    except json.JSONDecodeError:
        logger.error("Failed to parse JSON from LLM response")
        return None
    except Exception as e:
        logger.error("Error processing LLM response or validating data: %s", str(e))
        return None
