"""Language Validation Service for expert response language consistency."""

import logging
from typing import Dict, Any, Optional, Callable
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..utils.language_utils import detect_query_language
from .translation_service import TranslationService

logger = logging.getLogger(__name__)


class LanguageValidationService:
    """Service for validating and ensuring language consistency of expert responses."""

    def __init__(self, model: str = None):
        """Initialize LanguageValidationService.

        Args:
            model: Model to use (Gemini). Defaults to MODEL_ANALYSIS from config.
        """
        if model is None:
            from .. import config
            model = config.MODEL_ANALYSIS
        self.model = model
        # Initialize internal translation service
        self.translation_service = TranslationService(
            model=model
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, ValueError)),
        reraise=True
    )
    async def _translate_response(self, response_text: str, expert_id: str) -> str:
        """Translate response from Russian to English.

        Args:
            response_text: Russian response text to translate
            expert_id: Expert identifier for logging

        Returns:
            Translated English response
        """
        try:
            # Use existing translation service for consistency
            translated_text = await self.translation_service.translate_single_post(
                post_text=response_text,
                author_name=expert_id
            )

            logger.debug(f"[{expert_id}] Translated response: {response_text[:100]}... -> {translated_text[:100]}...")
            return translated_text

        except Exception as e:
            logger.error(f"[{expert_id}] Translation failed: {str(e)}")
            # Return original text if translation fails
            return response_text

    async def process(
        self,
        answer: str,
        query: str,
        expert_id: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Validate and potentially translate expert response.

        Args:
            answer: Expert's response to validate
            query: Original user query for language comparison
            expert_id: Expert identifier for logging
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with validation results and processed response
        """
        start_time = asyncio.get_event_loop().time()

        try:
            if progress_callback:
                await progress_callback({
                    "phase": "language_validation",
                    "status": "starting",
                    "message": f"[{expert_id}] Language validation starting"
                })

            if not answer or not answer.strip():
                logger.warning(f"[{expert_id}] Empty answer received, returning as-is")
                return {
                    "answer": answer,
                    "original_answer": answer,
                    "language": "Unknown",
                    "validation_applied": False,
                    "translation_applied": False,
                    "original_detected_language": "Unknown"
                }

            # Detect languages
            query_language = detect_query_language(query)
            answer_language = detect_query_language(answer)

            if progress_callback:
                await progress_callback({
                    "phase": "language_validation",
                    "status": "processing",
                    "message": f"[{expert_id}] Query language: {query_language}, Answer language: {answer_language}",
                    "data": {
                        "query_language": query_language,
                        "answer_language": answer_language,
                        "expert_id": expert_id
                    }
                })

            # Determine if translation is needed
            validation_applied = False
            translation_applied = False
            final_answer = answer

            # Only translate Russian -> English when mismatch detected
            if query_language == "English" and answer_language == "Russian":
                if progress_callback:
                    await progress_callback({
                        "phase": "language_validation",
                        "status": "processing",
                        "message": f"[{expert_id}] Language mismatch detected - translating Russian to English"
                    })

                final_answer = await self._translate_response(answer, expert_id)
                validation_applied = True
                translation_applied = True

                if progress_callback:
                    await progress_callback({
                        "phase": "language_validation",
                        "status": "processing",
                        "message": f"[{expert_id}] Translation completed"
                    })

            else:
                # Languages match or no translation needed
                if progress_callback:
                    await progress_callback({
                        "phase": "language_validation",
                        "status": "processing",
                        "message": f"[{expert_id}] Language validation passed - no translation needed"
                    })

            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

            if progress_callback:
                await progress_callback({
                    "phase": "language_validation",
                    "status": "completed",
                    "message": f"[{expert_id}] Language validation completed",
                    "data": {
                        "expert_id": expert_id,
                        "original_language": answer_language,
                        "validation_result": "mismatch_detected" if validation_applied else "match",
                        "translation_applied": translation_applied,
                        "original_answer": answer,
                        "validated_answer": final_answer
                    }
                })

            logger.info(f"[{expert_id}] Language validation completed: {answer_language} -> {query_language if validation_applied else answer_language} (translation: {translation_applied})")

            return {
                "answer": final_answer,
                "original_answer": answer,
                "language": query_language if validation_applied else answer_language,
                "validation_applied": validation_applied,
                "translation_applied": translation_applied,
                "original_detected_language": answer_language
            }

        except Exception as e:
            error_msg = f"Language validation failed: {str(e)}"
            logger.error(f"[{expert_id}] {error_msg}")

            if progress_callback:
                await progress_callback({
                    "phase": "language_validation",
                    "status": "error",
                    "message": f"[{expert_id}] {error_msg}",
                    "data": {
                        "expert_id": expert_id,
                        "error": str(e)
                    }
                })

            # Return original answer on error (graceful degradation)
            return {
                "answer": answer,
                "original_answer": answer,
                "language": "Unknown",
                "validation_applied": False,
                "translation_applied": False,
                "original_detected_language": "Error"
            }