from app.core.flags import FlagResolver


def build_postcall_prompt(transcript: str, flags: FlagResolver) -> str:
    tasks = ["Write a concise summary of the call (3-5 sentences)."]

    if flags.enabled("FLAG_POSTCALL_KEYPOINTS_EXTRACT"):
        tasks.append("List the main topics and decisions as bullet points.")
    if flags.enabled("FLAG_POSTCALL_ACTION_ITEMS"):
        tasks.append("List any action items with the responsible party if mentioned.")
    if flags.enabled("FLAG_POSTCALL_SENTIMENT_REPORT"):
        tasks.append("Rate overall customer sentiment: Positive / Neutral / Negative and explain.")
    if flags.enabled("FLAG_POSTCALL_ESCALATION_DETECT"):
        tasks.append(
            "Was escalation to a human requested or did the customer express buying intent? "
            "Answer yes or no and quote the exact trigger phrase."
        )
    if flags.enabled("FLAG_POSTCALL_NER_SUMMARY"):
        tasks.append("Extract: customer name, account/order IDs, dates, and amounts mentioned.")

    # Interest score is always requested — core metric for lead scoring
    tasks.append(
        "Rate the customer's interest level as an integer from 1 to 10 using this scale:\n"
        "  9-10: Explicitly asked for pricing, said 'I want to buy', or requested immediate callback\n"
        "  7-8:  Asked follow-up questions, expressed genuine curiosity, asked for more details\n"
        "  5-6:  Listened politely, did not object strongly, asked one general question\n"
        "  3-4:  Polite but disengaged, gave short answers, showed little interest\n"
        "  1-2:  Objected clearly, expressed no interest, or asked to be removed from the list"
    )

    task_list = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(tasks))
    return (
        "You are an expert call analyst. Given the transcript below, complete these tasks:\n\n"
        f"{task_list}\n\n"
        "Return your response as a JSON object with these keys:\n"
        "  summary (string), key_points (array), action_items (array),\n"
        "  sentiment (string: Positive|Neutral|Negative),\n"
        "  escalation (object: {requested: bool, trigger: string}),\n"
        "  entities (object), interest_score (integer 1-10)\n"
        "Omit keys that were not requested. Return ONLY the JSON object, no preamble.\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )