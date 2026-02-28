"""
GrammarManager — application-layer manager for explicit grammar correction queries.

Used by the REST endpoint (if Unity wants to explicitly query corrections
outside the live conversation loop e.g. for a dedicated feedback UI).
"""
import json

from domain.interfaces.ILargeLanguageModel import ILargeLanguageModel
from domain.interfaces.IRepositories import IMistakeRepository
from domain.models import GrammarCorrectionResult


_CORRECTION_SYSTEM_PROMPT = """
You are a strict {target_language} grammar expert. Analyze the student's utterance.

Return ONLY a JSON object with this exact schema:
{{
  "mistake_found": bool,
  "category": "verb_conjugation | gender_agreement | tense | vocabulary | pronunciation_flag | none",
  "original": "the incorrect phrase",
  "correction": "the corrected version",
  "explanation": "1-sentence explanation in English",
  "severity": 1-5
}}

Do not include any other text. Be precise and pedagogically accurate.
"""


class GrammarManager:
    def __init__(
        self,
        llm_service: ILargeLanguageModel,
        mistake_repo: IMistakeRepository,
    ):
        self._llm = llm_service
        self._mistakes = mistake_repo

    async def correct(
        self, player_id: str, utterance: str, target_language: str = "French"
    ) -> GrammarCorrectionResult:
        """
        Analyze a player's utterance for grammar mistakes.
        Returns a structured GrammarCorrectionResult and persists the mistake if found.
        """
        system_prompt = _CORRECTION_SYSTEM_PROMPT.format(target_language=target_language)
        raw = await self._llm.complete(system_prompt, utterance)
        data = json.loads(raw)

        result = GrammarCorrectionResult(
            mistake_found=data.get("mistake_found", False),
            category=data.get("category", "none"),
            original=data.get("original", ""),
            correction=data.get("correction", ""),
            explanation=data.get("explanation", ""),
            severity=data.get("severity", 0),
        )

        if result.mistake_found:
            await self._mistakes.log_mistake(
                player_id=player_id,
                category=result.category,
                original=result.original,
                correction=result.correction,
                explanation=result.explanation,
            )

        return result

    async def get_mistake_summary(self, player_id: str) -> list:
        """Return the top recurring mistake categories for the given player."""
        return await self._mistakes.get_top_mistakes(player_id, limit=5)
