import json
import logging
import httpx
from typing import Optional
from app.config import settings
from app.schemas.generation import GenerationResult

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1.0"

def get_system_prompt() -> str:
    return (
        "You are an expert technical writer and test creator. "
        "Your task is to generate exactly 3 Question and Answer pairs based on the provided text. "
        "Return the result ONLY as a valid JSON object matching this schema: "
        '{"items": [{"question": "...", "answer": "..."}]}. '
        "Do NOT wrap the JSON in Markdown formatting (no ```json ... ```) or include any extra text."
    )

def _call_groq_api(text_content: str) -> str:
    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("GROQ_API_KEY is not set. Returning mock LLM data for testing.")
        return '{"items": [{"question": "Mock Q?", "answer": "Mock A."}]}'

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": f"Generate QA pairs for the following text:\n\n{text_content}"}
        ],
        "temperature": 0.2,
        "max_tokens": 1024
    }

    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
        raise ValueError(f"LLM API Call failed: {str(e)}")

def generate_qa(text_content: str, max_retries: int = 3) -> GenerationResult:
    """
    Generates QA pairs from the given text using Groq.
    Implements a retry loop to gracefully handle malformed JSON from the LLM.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            raw_response = _call_groq_api(text_content)
            
            # Simple clean up just in case the LLM ignored instructions
            raw_response = raw_response.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response[7:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
                
            return GenerationResult.model_validate_json(raw_response)
        
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Attempt {attempt} failed due to malformed output or API error: {e}")
            last_error = e

    logger.error("Max retries exceeded for LLM generation.")
    raise RuntimeError(f"Failed to generate valid QA after {max_retries} attempts. Last error: {last_error}")
