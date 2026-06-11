from __future__ import annotations

from typing import TYPE_CHECKING

from app.utils.logging import get_logger

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.contact import Contact
    from app.models.tenant import Tenant

log = get_logger(__name__)

_FALLBACK_PERSONA = (
    "You are a professional AI voice assistant. "
    "Be helpful, concise, and polite. "
    "Keep every response under three sentences."
)


class PromptBuilder:
    """Assembles the complete system prompt from up to 4 static layers.

    Layer 1 — Base persona          (tenant.persona_prompt)
    Layer 2 — Business knowledge    (tenant name / industry / products / USPs)
    Layer 3 — Campaign context      (objective / opening line / questions / triggers)
    Layer 4 — Contact personalisation (customer name / CRM context)

    Layer 5 (RAG chunks) is NOT added here — it is appended per-turn inside
    VoicePipeline._build_system_prompt() because it changes every turn.
    """

    def build(
        self,
        tenant: "Tenant",
        campaign: "Campaign | None" = None,
        contact: "Contact | None" = None,
    ) -> str:
        sections = [
            self._layer_1_persona(tenant),
            self._layer_2_business(tenant),
            self._layer_3_campaign(campaign),
            self._layer_4_contact(contact),
        ]
        prompt = "\n\n".join(s for s in sections if s.strip())
        log.info(
            "prompt_built",
            tenant_id=str(tenant.id),
            campaign_id=str(campaign.id) if campaign else None,
            contact_id=str(contact.id) if contact else None,
            prompt_len=len(prompt),
        )
        return prompt

    # ── Layer 1 ──────────────────────────────────────────────────────

    def _layer_1_persona(self, tenant: "Tenant") -> str:
        prompt = (tenant.persona_prompt or "").strip()
        if not prompt:
            return _FALLBACK_PERSONA
        return prompt

    # ── Layer 2 ──────────────────────────────────────────────────────

    def _layer_2_business(self, tenant: "Tenant") -> str:
        parts: list[str] = []

        name = getattr(tenant, "business_name", None) or tenant.name
        industry = getattr(tenant, "industry", None)
        products: list[str] = getattr(tenant, "products", None) or []
        usp: list[str] = getattr(tenant, "usp", None) or []

        if not any([name, industry, products, usp]):
            return ""

        if name:
            line = f"COMPANY: {name}"
            if industry:
                line += f" | INDUSTRY: {industry}"
            parts.append(line)

        if products:
            items = ", ".join(products) if isinstance(products, list) else str(products)
            parts.append(f"PRODUCTS/SERVICES: {items}")

        if usp:
            items = ", ".join(usp) if isinstance(usp, list) else str(usp)
            parts.append(f"KEY SELLING POINTS: {items}")

        return "\n".join(parts) if parts else ""

    # ── Layer 3 ──────────────────────────────────────────────────────

    def _layer_3_campaign(self, campaign: "Campaign | None") -> str:
        if campaign is None:
            return ""

        lines: list[str] = []

        if campaign.objective:
            lines.append(f"CAMPAIGN OBJECTIVE: {campaign.objective}")

        if campaign.opening_line:
            lines.append(
                f'OPENING LINE: When the customer picks up, say exactly:\n'
                f'"{campaign.opening_line}"'
            )

        questions: list = campaign.qualification_questions or []
        if questions:
            lines.append("QUALIFICATION GOALS: During the call, try to discover:")
            for i, q in enumerate(questions, 1):
                text = q.get("question", q) if isinstance(q, dict) else str(q)
                lines.append(f"  {i}. {text}")

        triggers: list = campaign.escalation_triggers or []
        if triggers:
            trigger_bullets = "\n".join(f"  • {t}" for t in triggers)
            lines.append(
                "HOT LEAD DETECTION: If the customer says or implies any of the following, "
                "this is a HOT LEAD. Respond enthusiastically and tell them a specialist will "
                "contact them shortly:\n" + trigger_bullets
            )

        max_sec = getattr(campaign, "max_call_duration_sec", None) or 300
        lines.append(
            "CALL RULES:\n"
            f"  - Maximum call duration: {max_sec} seconds\n"
            "  - After 2 objections, thank the customer politely and close the call\n"
            "  - Never quote specific pricing — say a specialist will provide a custom quote\n"
            "  - If the customer asks to be removed from the list, say you will note it and end the call"
        )

        return "\n".join(lines)

    # ── Layer 4 ──────────────────────────────────────────────────────

    def _layer_4_contact(self, contact: "Contact | None") -> str:
        if contact is None:
            return ""

        name = getattr(contact, "name", None)
        context = getattr(contact, "context", None)

        if not name and not context:
            return ""

        lines = ["CUSTOMER PROFILE:"]
        if name:
            lines.append(
                f"Name: {name} — use their name naturally once or twice during the conversation"
            )
        if context:
            lines.append(f"Background: {context}")

        return "\n".join(lines)