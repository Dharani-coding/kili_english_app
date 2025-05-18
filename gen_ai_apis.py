import openai
import json


client = None
instruction = """You are a scenario adapter who takes on the given role and assists with practice conversations and 
vocabulary building. Your responses should be limited to three lines.
"""
messages = [
    {"role": "system", "content": instruction}
]

def init_openai_client(auth_key_val, system_audio_val, user_audio_val, feedback_json_val, quiz_txt_val, conversation_txt_val):
    global auth_key, system_audio, user_audio, feedback_json, quiz_txt, conversation_txt

    auth_key = auth_key_val
    system_audio = system_audio_val
    user_audio = user_audio_val
    feedback_json = feedback_json_val
    quiz_txt = quiz_txt_val
    conversation_txt = conversation_txt_val
    
    key = ""
    with open(auth_key, "r") as key_file:
        key = key_file.read()

    global client
    client = openai.OpenAI(api_key = key)
    
    
def create_quiz():
    # Load your JSON data
    with open(feedback_json, "r") as file:
        data = json.load(file)

    # Construct a prompt to ask the model to quiz you
    prompt = """
    You are a helpful English tutor. 
    Using the following list of grammar mistakes and corrected phrases, create short one-line quiz questions. 
    Each question should ask the user to choose or correct a phrase to avoid a past mistake. Then provide the correct answer.
    Provide questions such a way to see if I am making use of better pharses.

    Examples:
    Q: Which is correct? "I taked" or "I took"?  
    A: I took.

    Q: Fix this sentence: "I not even start."  
    A: I haven't even started.

    Now generate 3 similar quiz questions and answers based on the data below:

    Grammar Mistakes:
    {}
    Corrected Phrases:
    {}
    """.format(
        "\n".join(data["grammar_mistakes"]),
        "\n".join(data["better_phrases"])
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an English tutor helping the user correct grammar mistakes."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    # Print result
    quiz_content = response.choices[0].message.content

    with open(quiz_txt, "w") as outfile:
        outfile.write(quiz_content)


    
def convo_corrector(fix_json=False, invalid_json=None):
    if fix_json:
        prompt = f"JSON: {invalid_json} I got json.JSONDecodeError please fix the json content for loading and dumping"
    else:

        # Load your JSON data
        with open(conversation_txt, "r") as txt_file:
            conv = txt_file.read()

        # Prompt to extract grammar issues, vocabulary improvements, better phrases, and corrected version
        prompt = f"""
        Analyze the following conversation and provide feedback for improvement in the **You** section only. The output should be a **JSON object** with the following keys:

        1. **grammar_mistakes**: A list of key-value pairs where the **key** is the incorrect sentence and the **value** is the corrected sentence. Focus on grammatical errors such as tense issues, incorrect word order, and prepositions.

        2. **better_vocabulary**: A list of key-value pairs where the **key** is a word/phrase that could be improved and the **value** is the suggested, more fluent or advanced alternative. For example:
        - 'very happy' -> 'delighted'
        - 'nice' -> 'pleasant'
        - 'travelling from office to home' -> 'commute'

        3. **better_phrases**: A list of key-value pairs where the **key** is an expression or sentence that could be improved and the **value** is the improved version. For example:
        - 'I need to go now' -> 'I must leave now'
        - 'I was very tired' -> 'I was exhausted'

        Important: Return **only a valid JSON object**. Do not include any extra text or markdown formatting. do not include array.

        Conversation:
        {conv}

        """

    response = client.chat.completions.create(
        model="gpt-4o",  # or gpt-4
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    # Parse and print structured JSON result
    result_text = response.choices[0].message.content
    try:
        result_json = json.loads(result_text)
        json_object = json.dumps(result_json, indent=2)
        with open("output.json", "w") as outfile:
            outfile.write(json_object)

    except json.JSONDecodeError:
        print("The model didn't return valid JSON:")
        convo_corrector(fix_json=True, invalid_json=result_text)


def convo_builder(user_input):
    global messages

    messages.append({"role": "user", "content": "You: "+ user_input})

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

    reply = response.choices[0].message.content.strip()

    messages.append({"role": "assistant", "content": reply})
    with open(conversation_txt, "a") as f:
        f.write(f"You: {user_input}\nSystem: {reply}\n")

    return reply

def speech_to_text():
    audio_file= open(user_audio, "rb")

    transcription = client.audio.transcriptions.create(
        model="gpt-4o-transcribe", 
        file=audio_file
    )

    return transcription.text

def text_to_speech(input):
    response = client.audio.speech.create(
        model="tts-1",  # or "tts-1-hd"
        voice="alloy",  # other voices: echo, fable, onyx, nova, shimmer
        input=input
        )

    # Save audio to file
    with open(system_audio, "wb") as f:
        f.write(response.content)

def delete_chat_history():
    messages = messages[:1]
    open(conversation_txt, "w").close()