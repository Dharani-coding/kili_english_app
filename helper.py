


def format_learnings_to_json(learnings):
    result = {
        "grammar_mistakes": {},
        "better_vocabulary": {},
        "better_phrases": {},
        "new_words": [],
        "new_phrases": []
    }

    for item in learnings:
        table = item.get("table")
        if table == "GrammarMistakes":
            result["grammar_mistakes"][item["mistake"]] = item["correction"]
        elif table == "BetterVocabulary":
            result["better_vocabulary"][item["original"]] = item["better"]
        elif table == "BetterPhrases":
            result["better_phrases"][item["original"]] = item["better"]
        elif table == "NewWords":
            result["new_words"].append(item["word"])
        elif table == "NewPhrases":
            result["new_phrases"].append(item["phrase"])

    return result


