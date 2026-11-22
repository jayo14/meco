"""
Social Traction Dimension Evaluator.
Evaluates organic social momentum, mention velocity, author diversity,
sentiment, spam penalty, and specialist social agent findings.
"""
from datetime import datetime, timezone
from typing import Any

from app.agents.base import EvidenceItem
from app.decision.config import DecisionEngineConfig
from app.decision.dimensions.base import BaseDimensionEvaluator
from app.decision.models import DecisionDimension, DimensionScore, TokenDecisionInput


class SocialTractionEvaluator(BaseDimensionEvaluator):
    """
    Evaluates genuine social traction:
    - Mention count and velocity
    - Author diversity (penalizes single-shill spam)
    - Sentiment and organic engagement
    - Spam score penalty
    - Specialist social agent output
    """

    def evaluate(
        self,
        input_data: TokenDecisionInput,
        config: DecisionEngineConfig,
        as_of: datetime,
    ) -> DimensionScore:
        components: dict[str, float] = {}
        evidence: list[EvidenceItem] = []
        confidences: list[float] = []

        soc = input_data.social_intelligence or {}
        agent_out = input_data.social_agent_output

        # 1. Mention Velocity Component (0-100)
        mention_count = int(soc.get("mention_count") or 0)
        mention_velocity = float(soc.get("mention_velocity") or (mention_count / 1.0 if mention_count > 0 else 0.0))

        if mention_velocity <= 0:
            velocity_score = 15.0  # zero social presence
            confidences.append(0.6)
        elif mention_velocity < 2.0:
            velocity_score = 35.0  # trickle
            confidences.append(0.7)
        elif 2.0 <= mention_velocity < 10.0:
            velocity_score = 65.0  # healthy organic conversation
            confidences.append(0.85)
        elif 10.0 <= mention_velocity <= 50.0:
            velocity_score = 90.0  # strong viral traction
            confidences.append(0.85)
        else:
            velocity_score = 75.0  # extreme flood (often bot spam attack)
            confidences.append(0.75)
        components["mention_velocity"] = round(velocity_score, 2)

        if mention_count > 0:
            evidence.append(
                EvidenceItem(
                    source="social_metrics",
                    timestamp=as_of,
                    reference=f"mint:{input_data.mint_address}",
                    details={"mention_count": mention_count, "mention_velocity": mention_velocity},
                )
            )

        # 2. Author Diversity & Sybil Resistance (0-100)
        # High author concentration (> 0.70 means one person posting everything)
        unique_authors = int(soc.get("unique_authors_count") or 0)
        author_concentration = float(soc.get("author_concentration") or 0.0)

        if unique_authors == 0:
            diversity_score = 25.0
            confidences.append(0.5)
        elif author_concentration > 0.60:
            diversity_score = 20.0  # bot shill raid
            confidences.append(0.8)
        elif unique_authors >= 15 and author_concentration < 0.20:
            diversity_score = 95.0  # broad decentralised community interest
            confidences.append(0.85)
        elif unique_authors >= 5:
            diversity_score = 70.0
            confidences.append(0.8)
        else:
            diversity_score = 45.0
            confidences.append(0.6)
        components["author_diversity"] = round(diversity_score, 2)

        # 3. Sentiment & Spam Penalty Component (0-100)
        sent_pos = float(soc.get("sentiment_positive") or 0.33)
        sent_neg = float(soc.get("sentiment_negative") or 0.33)
        spam_score = float(soc.get("spam_score") or 0.0)  # 0.0 to 1.0

        sentiment_base = 50.0 + (sent_pos - sent_neg) * 40.0
        # Heavily deduct for spam
        spam_deduction = spam_score * 50.0
        sentiment_score = min(100.0, max(0.0, sentiment_base - spam_deduction))
        components["sentiment_cleanliness"] = round(sentiment_score, 2)
        confidences.append(0.75)

        # 4. Social Intelligence Specialist Agent (0-100)
        if agent_out and agent_out.status.value == "completed":
            agent_base = agent_out.confidence * 85.0
            facts = len(agent_out.facts())
            agent_score = min(100.0, max(15.0, agent_base + min(15.0, facts * 5.0)))
            confidences.append(agent_out.confidence)
            evidence.extend(agent_out.evidence_references[:2])
        else:
            agent_score = 40.0
            confidences.append(0.4)
        components["social_agent_conviction"] = round(agent_score, 2)

        # Total composite
        total_score = round(
            0.30 * components["mention_velocity"]
            + 0.25 * components["author_diversity"]
            + 0.20 * components["sentiment_cleanliness"]
            + 0.25 * components["social_agent_conviction"],
            2,
        )

        overall_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.5
        rationale = (
            f"Social traction score {total_score:.1f}/100. Mention velocity ({components['mention_velocity']:.1f}), "
            f"author diversity ({components['author_diversity']:.1f}), sentiment cleanliness ({components['sentiment_cleanliness']:.1f}), "
            f"and social agent conviction ({components['social_agent_conviction']:.1f})."
        )

        return DimensionScore(
            dimension=DecisionDimension.SOCIAL_TRACTION,
            score=total_score,
            confidence=overall_conf,
            components=components,
            rationale=rationale,
            evidence_sources=evidence,
        )
