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
        tasks.append("Was escalation to a human requested? Answer yes or no and quote the trigger.")
    if flags.enabled("FLAG_POSTCALL_NER_SUMMARY"):
        tasks.append("Extract: customer name, account/order IDs, dates, and amounts mentioned.")

    task_list = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(tasks))
    return (
        "You are an expert call analyst. Given the transcript below, complete these tasks:\n\n"
        f"{task_list}\n\n"
        "Return your response as a JSON object with keys: summary, key_points, action_items,\n"
        "sentiment, escalation, entities. Omit keys that were not requested.\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )
