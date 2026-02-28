"""
ReviewScheduler — generates adaptive review sessions based on mistake history.

Triggered by the review endpoint (which Unity polls every 15 minutes of active play).
Queries the top recurring mistakes and uses the LLM to generate targeted exercises.
"""
import json
from typing import Dict, Any

from domain.interfaces.ILargeLanguageModel import ILargeLanguageModel
from domain.interfaces.IRepositories import IMistakeRepository
from domain.models import ReviewSession


_REVIEW_GENERATION_PROMPT = """
You are a language learning curriculum designer. Based on a student's recent grammar mistakes,
generate a focused 5-minute review session.

The student's top mistake categories (most frequent first):
{mistake_summary}

Recent mistake examples:
{mistake_examples}

Generate a JSON review session with this structure:
{{
  "title": "Session title",
  "exercises": [
    {{
      "type": "fill_in_blank | multiple_choice | correction | translation",
      "instruction": "Task instruction in English",
      "prompt": "The exercise text (in the target language where applicable)",
      "options": ["option1", "option2", "option3", "option4"],  // for multiple_choice only
      "correct_answer": "The correct answer",
      "explanation": "Why this is correct"
    }}
  ]
}}

- Generate exactly 5 exercises
- Focus on the top 2-3 mistake categories 
- Use contextual examples from the student's actual mistakes where possible
- Make exercises progressively harder (1-5)
- Be encouraging in tone
"""


class ReviewScheduler:
    def __init__(
        self,
        llm_service: ILargeLanguageModel,
        mistake_repo: IMistakeRepository,
    ):
        self._llm = llm_service
        self._mistakes = mistake_repo

    async def generate_review_session(self, player_id: str) -> ReviewSession:
        """
        Core method: fetch recent mistakes, call LLM to generate exercises,
        return a ReviewSession payload to be sent to Unity.
        """
        # 1. Get top recurring categories
        top_mistakes = await self._mistakes.get_top_mistakes(player_id, limit=3)
        recent_mistakes = await self._mistakes.get_recent_mistakes(player_id, since_minutes=15)

        if not top_mistakes:
            # No mistakes yet — return an empty session marker
            return ReviewSession(
                player_id=player_id,
                top_mistake_categories=[],
                exercises=[],
            )

        # 2. Build prompt context
        mistake_summary = json.dumps(top_mistakes, indent=2)
        mistake_examples = json.dumps(
            [{"category": m["category"], "original": m["original"], "correction": m["correction"]}
             for m in recent_mistakes[:10]],
            indent=2,
        )

        # 3. LLM generates the exercises
        prompt = _REVIEW_GENERATION_PROMPT.format(
            mistake_summary=mistake_summary,
            mistake_examples=mistake_examples,
        )
        raw_session = await self._llm.complete(
            system_prompt="You are a language review session generator. Always respond with valid JSON only.",
            user_message=prompt,
        )
        session_data = json.loads(raw_session)

        return ReviewSession(
            player_id=player_id,
            top_mistake_categories=[m["category"] for m in top_mistakes],
            exercises=session_data.get("exercises", []),
        )

    async def should_trigger_review(self, player_id: str, active_minutes: int) -> bool:
        """
        Simple rule: trigger a review every 15 active minutes and if there
        are at least 3 logged mistakes (avoid empty sessions).
        """
        if active_minutes < 15:
            return False
        top = await self._mistakes.get_top_mistakes(player_id, limit=1)
        return len(top) > 0
