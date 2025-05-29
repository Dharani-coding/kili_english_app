"""
Helper utilities for the Kili English Learning App.

Includes:
- Formatting learnings from the database into JSON for quiz/report generation.
- UI-specific helpers for formatting conversation text for display.
"""

def format_learnings_to_json(learnings):
    """
    Converts a list of learning items from the database into a structured JSON object.

    Args:
        learnings (list): List of dicts, each representing a learning item with a 'table' key.

    Returns:
        dict: Structured JSON with grammar mistakes, vocabulary, phrases, new words, and new phrases.
    """
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
            _add_grammar_mistake(result, item)
        elif table == "BetterVocabulary":
            _add_better_vocabulary(result, item)
        elif table == "BetterPhrases":
            _add_better_phrase(result, item)
        elif table == "NewWords":
            _add_new_word(result, item)
        elif table == "NewPhrases":
            _add_new_phrase(result, item)

    return result

def _add_grammar_mistake(result, item):
    result["grammar_mistakes"][item["mistake"]] = item["correction"]

def _add_better_vocabulary(result, item):
    better_word = item.get("better_word") or item.get("better")
    word = item.get("word") or item.get("original")
    if word and better_word:
        result["better_vocabulary"][word] = better_word

def _add_better_phrase(result, item):
    original = item.get("original")
    better = item.get("better")
    if original and better:
        result["better_phrases"][original] = better

def _add_new_word(result, item):
    word = item.get("word")
    if word:
        result["new_words"].append(word)

def _add_new_phrase(result, item):
    phrase = item.get("phrase")
    if phrase:
        result["new_phrases"].append(phrase)

def parse_conversation_for_display(text):
    """
    Formats conversation text for display in the UI.
    Adds newlines before each 'You:' or 'System:' and replaces with icons.

    Args:
        text (str): The conversation text.

    Returns:
        str: Formatted conversation string for display.
    """
    import re
    content = re.sub(r'(You:|System:)', r'\n\1', text).strip()
    content = content.replace('You:', '👩🏽:')
    content = content.replace('System:', '🤖:')
    return content


