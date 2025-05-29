"""
AI API integration for Kili English Learning App.

Handles OpenAI client initialization, conversation management, feedback analysis,
quiz generation, speech-to-text, text-to-speech, and chat history operations.
"""

import openai
import json

# Global variables
client = None
messages = []
config = None

# System prompt to guide the assistant
instruction = (
    "You are a scenario adapter who takes on the given role and assists with practice conversations and "
    "vocabulary building. Your responses should be limited to three lines."
)
messages.append({"role": "system", "content": instruction})


def init_openai_client(output_config):
    """
    Initializes the OpenAI client and sets global config.

    Args:
        output_config (dict): Dictionary containing all needed paths/keys.
    """
    global config
    config = output_config

    with open(config["auth_key"], "r") as key_file:
        key = key_file.read().strip()

    global client
    client = openai.OpenAI(api_key=key)


def english_enhancer():
    """
    Wrapper for improve_english to be called from UI.
    """
    improve_english()


def improve_english():
    """
    Improves the user's conversation by rewriting only the "You:" parts
    to enhance grammar, vocabulary, and phrasing. Saves the improved conversation.
    """
    with open(config["feedback_json"], "r") as file:
        feedback = json.load(file)

    with open(config["conversation_txt"], "r") as file:
        conversation = file.read()

    prompt = f"""
    conversation:
    {conversation}

    Please rewrite only the "You:" parts of the conversation to improve grammar, vocabulary, and phrasing. Maintain a natural tone that matches the context — casual, formal, or friendly as appropriate. Use your judgment to rephrase the responses as a fluent, thoughtful speaker would, going beyond just applying the provided feedback. Ensure the meaning stays the same, but make the delivery more native-like, polished, and engaging.

    Output Format:
    Return only the updated conversation (including both “You:” and “System:” lines), with only the “You:” lines modified. Do not include explanations or extra text, so I can directly paste it into this PyQt text box:

    self.chat_display = QTextEdit(readOnly=True)
    
    Feeback received:
    {json.dumps(feedback, indent=2)}
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are an English tutor helping the user improve spoken english",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    data = response.choices[0].message.content

    # Save to txt
    with open(config["improv_conversation_txt"], "w") as outfile:
        outfile.write(data)


def create_quiz(json_file):
    """
    Generates a short grammar and phrasing quiz from feedback JSON content and saves it to a file.

    Args:
        json_file (str): Path to the JSON file containing feedback or learnings.
    """
    with open(json_file, "r") as file:
        data = json.load(file)

    prompt = f"""
    You are an English tutor AI.
    Your task is to generate short quiz-style questions (1-3 lines) using the provided categories: grammar mistakes, better vocabulary, better phrases, new words, and new phrases.

    Goal:
    Help the learner recall and apply their previous mistakes and improved expressions through realistic, varied questions — not just recognize them.

    Instructions:

    Use varied formats like:

    Multiple choice
    Fill in the blank
    Sentence correction

    For Grammar Mistakes:
    Present the incorrect sentence.
    Ask the learner to correct it.

    For Better Vocabulary & Better Phrases:
    Create a short real-life context or conversational sentence.
    Subtly suggest a need for a stronger or more natural expression.
    Do NOT reveal the improved version in the question.
    Present example usage of the phrase or Vocabulary in 1-3 whole sentences

    For New Words and New Phrases:
    Present a situation where the word or phrase could be used.
    Ask the learner to guess or recall it based on the tone, meaning, or context.
    Present example usage of the phrase or word in 1-3 whole sentences

    Tone and Context Sensitivity:
    Match the tone of the original sentence.
    If the original was casual, don't suggest overly formal replacements.
    If the original was formal or professional, suggest appropriate polished alternatives.
    Ensure that improvements feel natural and contextually appropriate.

    Output Format for each quiz item:

    Q: [Your quiz question here]
    A: [Correct answer here]

    Examples:

    Q: Which is correct? "I am in the office" or "I am at the office"?
    A: I am in the office.

    Q: Fix this sentence: "I not even start."
    A: I haven't even started.

    Q: "I'm willing to work to a great extent." — What idiom would elevate this line?
    A: Go above and beyond.

    Q: In a formal email, which sounds better? "I want to talk to you" or "I would like to speak with you"?
    A: I would like to speak with you.

    Now generate quiz questions per item in each section using the structure above.

    Grammar Mistakes:
    {"\n".join(data.get("grammar_mistakes", {}))}

    Corrected Phrases:
    {"\n".join(data.get("better_phrases", {}))}

    Better vocabulary:
    {"\n".join(data.get("better_vocabulary", {}))}

    New words learnt:
    {"\n".join(data.get("new_words", []))}

    New phrases learnt:
    {"\n".join(data.get("new_phrases", []))}
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are an English tutor helping the user correct grammar mistakes.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    quiz_content = response.choices[0].message.content

    # Extract question and answers
    quiz_qa_pairs = []
    question, answer = "", ""
    for line in quiz_content.splitlines():
        if line.strip().startswith("Q:"):
            question = line.strip()[2:].strip()
        elif line.strip().startswith("A:"):
            answer = line.strip()[2:].strip()
            if question and answer:
                quiz_qa_pairs.append({"question": question, "answer": answer})
            question, answer = "", ""

    # Save to JSON
    with open(config["quiz_json"], "w") as outfile:
        json.dump(quiz_qa_pairs, outfile, indent=4)


def conversation_corrector(fix_json=False, invalid_json=None):
    """
    Analyzes the user's conversation for grammar issues and provides suggestions.

    Args:
        fix_json (bool): Whether to fix a broken JSON response.
        invalid_json (str): The invalid JSON text to attempt to correct.
    """
    if fix_json:
        prompt = f"""
        JSON: {invalid_json} I got json.JSONDecodeError, please fix the JSON content for loading and dumping.
        Ensure the output is a **valid JSON object** with no markdown, extra text, or formatting.
        """
    else:
        with open(config["conversation_txt"], "r") as txt_file:
            conv = txt_file.read()

        prompt = f"""
        Analyze the following conversation and provide feedback for improvement in the **You** section only (i.e., the person learning English). Output a single valid **JSON object** with the following exact keys:

        1. "grammar_mistakes":  A dictionary where each key is a sentence spoken by "You" that contains a grammar issue, and the value is the corrected version. Focus on tense, articles, prepositions, and subject-verb agreement.

        2. "better_vocabulary":  A dictionary where each key is a simple, awkward, or repetitive word/phrase used by "You", and the value is a more fluent, natural, or advanced alternative.

        3. "better_phrases":  A dictionary where each key is an unnatural or informal sentence/phrase used by "You", and the value is a more appropriate, fluent, or professional version. This includes:
        - Awkward sentence structures (even if grammatically correct)
        - Redundant expressions
        - Improvements for formality (especially suitable for academic, interview, or visa contexts)

        Instructions:
        - DO NOT duplicate corrections across sections.
        - If no suggestions for a section, return an empty object: {{}}
        - Limit each correction list (1-3) to a maximum of 7 relevant items.
        - Ensure the output is a **valid JSON object** with no markdown, extra text, or formatting.

        Conversation:
        {conv}
        """

    response = client.chat.completions.create(
        model="gpt-4o", messages=[{"role": "user", "content": prompt}], temperature=0.4
    )

    result_text = response.choices[0].message.content

    try:
        result_json = json.loads(result_text)
        json_object = json.dumps(result_json, indent=2)
        with open(config["feedback_json"], "w") as outfile:
            outfile.write(json_object)
    except json.JSONDecodeError:
        print("The model didn't return valid JSON.")
        conversation_corrector(fix_json=True, invalid_json=result_text)


def conversation_builder(user_input):
    """
    Adds user input to the conversation, gets the assistant's response, appends both to log and returns the reply.

    Args:
        user_input (str): The user's message.

    Returns:
        str: Assistant's reply.
    """
    global messages
    messages.append({"role": "user", "content": "You: " + user_input})

    response = client.chat.completions.create(model="gpt-4", messages=messages)

    reply = response.choices[0].message.content.strip()
    messages.append({"role": "assistant", "content": reply})

    with open(config["conversation_txt"], "a") as f:
        f.write(f"You: {user_input}\nSystem: {reply}\n")

    return reply


def speech_to_text():
    """
    Transcribes user audio input using OpenAI's audio transcription.

    Returns:
        str: Transcribed text.
    """
    with open(config["user_audio"], "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="gpt-4o-transcribe", file=audio_file
        )
    return transcription.text


def text_to_speech(input_text):
    """
    Converts input text to speech and saves the audio output.

    Args:
        input_text (str): The text to convert to speech.
    """
    response = client.audio.speech.create(
        model="tts-1", voice="alloy", input=input_text
    )

    with open(config["system_audio"], "wb") as f:
        f.write(response.content)


def delete_chat_history():
    """
    Resets conversation to the system instruction and clears the log file.
    """
    global messages
    messages = messages[:1]  # Keep only the system instruction
    open(config["conversation_txt"], "w").close()


if __name__ == "__main__":
    # Example usage
    config = {
        "auth_key": "openai_auth_key.txt",
        "conversation_txt": "output/conversation.txt",
        "feedback_json": "output/feedback.json",
        "quiz_json": "output/quiz.json",
        "user_audio": "output/user_audio.wav",
        "system_audio": "output/system_audio.wav",
        "improv_conversation_txt": "output/improved_conversation.txt",
    }
    init_openai_client(config)
    # Add more function calls as needed for testing
    english_enhancer()
