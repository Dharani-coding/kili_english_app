"""
Kili - English Learning App (PyQt5)
Main application UI and logic for chat, reports, quizzes, and English enhancement.
"""

import sys
import asyncio
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from pydub import AudioSegment
import tempfile
import os
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QTextEdit,
    QLineEdit,
    QTabWidget,
    QMessageBox,
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl
import json

from qasync import QEventLoop
import gen_ai_apis
import database_manager
import helper

auth_key = "openai_auth_key.txt"
system_audio = "output/system_audio.mp3"
user_audio = "output/user_audio.mp3"
feedback_json = "output/feedback.json"
learnings_json = "output/learnings.json"
quiz_json = "output/quiz.json"
conversation_txt = "output/conversation.txt"
improv_conversation_txt = "output/improv_conversation.txt"
db_file = "database/english_learnings.db"


class RecorderThread(QThread):
    """
    Thread for recording audio from the microphone.
    """
    finished = pyqtSignal()

    def __init__(self, samplerate=44100):
        super().__init__()
        self.samplerate = samplerate
        self.recording = []
        self.running = False

    def run(self):
        self.running = True
        with sd.InputStream(
            samplerate=self.samplerate, channels=1, callback=self.callback
        ):
            while self.running:
                sd.sleep(100)
        self.finished.emit()

    def callback(self, indata, frames, time, status):
        if self.running:
            self.recording.append(indata.copy())

    def stop(self):
        self.running = False

    def save_to_mp3(self):
        """
        Save the recorded audio to an MP3 file.
        """
        audio = np.concatenate(self.recording, axis=0)
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_wav.close()
        write(temp_wav.name, self.samplerate, audio)
        sound = AudioSegment.from_wav(temp_wav.name)
        sound.export(user_audio, format="mp3")
        os.remove(temp_wav.name)
        return user_audio


class EnglishTutorApp(QWidget):
    """
    Main application window for the Kili English Learning App.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kili - English Learning App")
        self.recorder_thread = None
        self.qa_pairs = []
        self.current_index = 0
        self.showing_question = True
        self.system_audio_enabled = True
        self.init_ui()
        self.db = database_manager.DBManager(db_file)

    def init_ui(self):
        """
        Initialize the UI with all tabs and widgets.
        """
        main_layout = QVBoxLayout()
        tab_widget = QTabWidget()

        # === Tab 1: Chat ===
        chat_tab = QWidget()
        chat_layout = QVBoxLayout()

        # Toggle buttons
        toggle_layout = QHBoxLayout()
        self.toggle_audio = QPushButton("🔊 System Audio")
        self.toggle_audio.setCheckable(True)
        self.toggle_audio.setChecked(True)
        self.toggle_audio.toggled.connect(
            lambda checked: setattr(self, "system_audio_enabled", checked)
        )

        # self.toggle_hints = QPushButton("💡 Hints")
        # self.toggle_hints.setCheckable(True)

        toggle_layout.addWidget(self.toggle_audio)
        # toggle_layout.addWidget(self.toggle_hints)
        chat_layout.addLayout(toggle_layout)

        self.chat_display = QTextEdit(readOnly=True)
        chat_layout.addWidget(self.chat_display)

        # Chat buttons
        btn_layout = QHBoxLayout()
        self.record_btn = QPushButton("Record", checkable=True)
        self.record_btn.toggled.connect(self.toggle_recording)
        self.clear_chat_btn = QPushButton("Clear chat")
        self.clear_chat_btn.clicked.connect(self.chat_display.clear)
        self.del_history_btn = QPushButton("Delete History")
        self.del_history_btn.clicked.connect(gen_ai_apis.delete_chat_history)

        btn_layout.addWidget(self.record_btn)
        btn_layout.addWidget(self.clear_chat_btn)
        btn_layout.addWidget(self.del_history_btn)
        chat_layout.addLayout(btn_layout)

        msg_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(
            lambda: asyncio.create_task(self.send_text_message())
        )
        msg_layout.addWidget(self.msg_input)
        msg_layout.addWidget(self.send_btn)

        chat_layout.addLayout(msg_layout)
        chat_tab.setLayout(chat_layout)

        # === Tab 2: Report ===
        report_tab = QWidget()
        report_layout = QVBoxLayout()

        report_header = QHBoxLayout()
        report_title = QLabel("<b>Conversation Report and Storage</b>")
        self.gen_btn = QPushButton("Generate")
        self.gen_btn.clicked.connect(self.get_report)
        self.feedback_btn = QPushButton("View Feedback")
        self.feedback_btn.clicked.connect(self.show_feedback)
        self.clear_all_btn = QPushButton("Clear")
        self.clear_all_btn.clicked.connect(self.clear_report)

        report_header.addWidget(report_title)
        report_header.addStretch()
        report_header.addWidget(self.gen_btn)
        report_header.addWidget(self.feedback_btn)
        report_header.addWidget(self.clear_all_btn)

        # Input for new memory
        memory_layout = QHBoxLayout()
        self.memory_input = QLineEdit()
        self.memory_dropdown = QComboBox()
        self.memory_dropdown.addItems(["New Word", "New Phrase"])
        self.remember_btn = QPushButton("Remember")
        self.remember_btn.clicked.connect(self.remember_input)
        memory_layout.addWidget(self.memory_input)
        memory_layout.addWidget(self.memory_dropdown)
        memory_layout.addWidget(self.remember_btn)

        # === Grammar section ===
        grammar_layout = QHBoxLayout()
        grammar_label = QLabel("📝 Grammar")
        self.grammar_text = QTextEdit(readOnly=True)
        self.grammar_remember_btn = QPushButton("Remember Grammar")
        self.grammar_remember_btn.clicked.connect(self.remember_grammar)

        grammar_layout.addWidget(grammar_label)
        grammar_layout.addStretch()
        grammar_layout.addWidget(self.grammar_remember_btn)

        # === Vocabulary section ===
        vocab_layout = QHBoxLayout()
        vocab_label = QLabel("📚 Vocabulary")
        self.vocab_text = QTextEdit(readOnly=True)
        self.vocab_remember_btn = QPushButton("Remember Vocabulary")
        self.vocab_remember_btn.clicked.connect(self.remember_vocabulary)

        vocab_layout.addWidget(vocab_label)
        vocab_layout.addStretch()
        vocab_layout.addWidget(self.vocab_remember_btn)

        # === Phrases section ===
        phrase_layout = QHBoxLayout()
        phrase_label = QLabel("💬 Phrases")
        self.phrase_text = QTextEdit(readOnly=True)
        self.phrase_remember_btn = QPushButton("Remember Phrases")
        self.phrase_remember_btn.clicked.connect(self.remember_phrases)

        phrase_layout.addWidget(phrase_label)
        phrase_layout.addStretch()
        phrase_layout.addWidget(self.phrase_remember_btn)

        self.grammar_remember_btn.setEnabled(False)
        self.vocab_remember_btn.setEnabled(False)
        self.phrase_remember_btn.setEnabled(False)

        report_layout.addLayout(report_header)
        report_layout.addLayout(grammar_layout)
        report_layout.addWidget(self.grammar_text)
        report_layout.addLayout(vocab_layout)
        report_layout.addWidget(self.vocab_text)
        report_layout.addLayout(phrase_layout)
        report_layout.addWidget(self.phrase_text)
        report_layout.addLayout(memory_layout)

        report_tab.setLayout(report_layout)

        # === Tab 3: Quiz ===
        quiz_tab = QWidget()
        quiz_layout = QVBoxLayout()

        quiz_header = QHBoxLayout()
        quiz_title = QLabel("<b>Quiz Generator</b>")
        self.quiz_btn = QPushButton("Generate from conversation")
        self.quiz_btn.clicked.connect(self.generate_quiz)
        self.quiz_memory_btn = QPushButton("Generate from memory")
        self.quiz_memory_btn.clicked.connect(self.generate_memory_quiz)
        self.start_quiz_btn = QPushButton("Start Quiz")
        self.start_quiz_btn.clicked.connect(self.start_quiz)

        quiz_header.addWidget(quiz_title)
        quiz_header.addStretch()
        quiz_header.addWidget(self.quiz_btn)
        quiz_header.addWidget(self.quiz_memory_btn)
        quiz_header.addWidget(self.start_quiz_btn)

        self.quiz_display = QTextEdit(readOnly=True)

        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self.prev_flashcard)
        self.prev_btn.setEnabled(False)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.next_flashcard)
        self.next_btn.setEnabled(False)

        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.next_btn)

        quiz_layout.addLayout(quiz_header)
        quiz_layout.addWidget(self.quiz_display)
        quiz_layout.addLayout(nav_layout)
        quiz_tab.setLayout(quiz_layout)

        # === Tab 4: English Enhancer ===
        enhancer_tab = QWidget()
        enhancer_layout = QVBoxLayout()

        # Top buttons
        enhancer_btn_layout = QHBoxLayout()
        self.improve_btn = QPushButton("Improve conversation")
        self.improve_btn.clicked.connect(self.improve_conversation)
        self.show_diff_btn = QPushButton("Show diff")
        self.show_diff_btn.clicked.connect(self.show_conversation_diff)
        self.clear_enhancer_btn = QPushButton("Clear")
        self.clear_enhancer_btn.clicked.connect(self.clear_enhancer_texts)
        enhancer_btn_layout.addWidget(self.improve_btn)
        enhancer_btn_layout.addWidget(self.show_diff_btn)
        enhancer_btn_layout.addWidget(self.clear_enhancer_btn)
        enhancer_layout.addLayout(enhancer_btn_layout)

        # Conversation and Improved Conversation text boxes
        enhancer_texts_layout = QHBoxLayout()

        conv_layout = QVBoxLayout()
        conv_label = QLabel("Conversation")
        self.conv_text = QTextEdit(readOnly=True)
        conv_layout.addWidget(conv_label)
        conv_layout.addWidget(self.conv_text)

        improved_layout = QVBoxLayout()
        improved_label = QLabel("Improved Conversation")
        self.improved_text = QTextEdit(readOnly=True)
        improved_layout.addWidget(improved_label)
        improved_layout.addWidget(self.improved_text)

        enhancer_texts_layout.addLayout(conv_layout)
        enhancer_texts_layout.addLayout(improved_layout)
        enhancer_layout.addLayout(enhancer_texts_layout)

        enhancer_tab.setLayout(enhancer_layout)

        # Add all tabs
        tab_widget.addTab(chat_tab, "🗨️ Chat")
        tab_widget.addTab(report_tab, "📄 Report")
        tab_widget.addTab(quiz_tab, "🧠 Quiz")
        tab_widget.addTab(enhancer_tab, "✨ English Enhancer")

        main_layout.addWidget(tab_widget)
        self.setLayout(main_layout)

    def toggle_recording(self, checked):
        """
        Start or stop audio recording.
        """
        self.record_btn.setText("Stop" if checked else "Record")
        if checked:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """
        Start the audio recording thread.
        """
        print("[System] Recording started...")
        self.recorder_thread = RecorderThread()
        self.recorder_thread.finished.connect(
            lambda: asyncio.create_task(self.on_recording_finished())
        )
        self.recorder_thread.start()

    def stop_recording(self):
        """
        Stop the audio recording thread.
        """
        if self.recorder_thread:
            self.recorder_thread.stop()

    def del_audio(self):
        """
        Delete the current audio player instance.
        """
        if hasattr(self, "audio_player"):
            self.audio_player.stop()
            self.audio_player.setMedia(QMediaContent())
            self.audio_player.deleteLater()
            del self.audio_player

    def play_audio(self):
        """
        Play the system audio file.
        """
        self.audio_player = QMediaPlayer()
        self.audio_player.setMedia(QMediaContent(
            QUrl.fromLocalFile(system_audio)))
        self.audio_player.play()

    async def send_and_receive_response(self, user_text):
        """
        Send user text to the AI and display the response.
        """
        self.del_audio()
        self.display_message(user_text, "You")

        system_reply = await asyncio.to_thread(
            gen_ai_apis.conversation_builder, user_text
        )
        if self.system_audio_enabled:
            await asyncio.to_thread(gen_ai_apis.text_to_speech, system_reply)
            await asyncio.to_thread(self.play_audio)

        self.display_message(system_reply, "System")

    async def on_recording_finished(self):
        """
        Handle actions after audio recording is finished.
        """
        path = await asyncio.to_thread(self.recorder_thread.save_to_mp3)
        print(f"[System] Audio saved to: {path}")
        user_text = await asyncio.to_thread(gen_ai_apis.speech_to_text)
        await self.send_and_receive_response(user_text)

    def display_message(self, text=None, sender="You"):
        """
        Display a message in the chat display.
        """
        if text.strip():
            sender = "🤖" if sender == "System" else "👩🏽"
            self.chat_display.append(f"{sender}: {text}\n")
        self.msg_input.clear()

    async def send_text_message(self):
        """
        Send the text message from the input box.
        """
        user_text = self.msg_input.text()
        await self.send_and_receive_response(user_text)

    def get_report(self):
        """
        Generate a conversation report.
        """
        gen_ai_apis.conversation_corrector()

    def show_feedback(self):
        """
        Display feedback from the feedback JSON.
        """
        global feedback
        with open(feedback_json, "r") as file:
            feedback = json.load(file)

        # Format Grammar: original + bold correction
        grammar_entries = [
            f"{mistake}<br><b>{correction}</b><br>"
            for mistake, correction in feedback.get("grammar_mistakes", {}).items()
        ]
        grammar_html = "<br>".join(grammar_entries)

        # Format Vocabulary: original + bold suggestion
        vocab_entries = [
            f"{word}<br><b>{suggestion}</b><br>"
            for word, suggestion in feedback.get("better_vocabulary", {}).items()
        ]
        vocab_html = "<br>".join(vocab_entries)

        # Format Phrases: original + bold rewrite
        phrase_entries = [
            f"{phrase}<br><b>{improved}</b><br>"
            for phrase, improved in feedback.get("better_phrases", {}).items()
        ]
        phrase_html = "<br>".join(phrase_entries)

        # Set all outputs
        self.grammar_text.setHtml(grammar_html)
        self.vocab_text.setHtml(vocab_html)
        self.phrase_text.setHtml(phrase_html)

        self.grammar_remember_btn.setEnabled(True)
        self.vocab_remember_btn.setEnabled(True)
        self.phrase_remember_btn.setEnabled(True)

    def remember_grammar(self):
        """
        Store grammar mistakes to the database.
        """
        try:
            for mistake, correction in feedback.get("grammar_mistakes", {}).items():
                self.db.add_grammar_mistake(mistake, correction)
            print("Grammar mistakes remembered.")
        except Exception as e:
            print("Error remembering grammar:", e)

    def remember_vocabulary(self):
        """
        Store vocabulary improvements to the database.
        """
        try:
            for word, suggestion in feedback.get("better_vocabulary", {}).items():
                self.db.add_better_vocabulary(word, suggestion)
            print("Vocabulary remembered.")
        except Exception as e:
            print("Error remembering vocabulary:", e)

    def remember_phrases(self):
        """
        Store better phrases to the database.
        """
        try:
            for phrase, improved in feedback.get("better_phrases", {}).items():
                self.db.add_better_phrase(phrase, improved)
            print("Phrases remembered.")
        except Exception as e:
            print("Error remembering phrases:", e)

    def remember_input(self):
        """
        Store a new word or phrase to the database from user input.
        """
        text = self.memory_input.text().strip()
        category = self.memory_dropdown.currentText()

        if not text:
            QMessageBox.warning(
                self, "Empty Input", "Please enter a word or phrase to remember."
            )
            return

        try:
            if category == "New Word":
                self.db.add_new_word(text)
            elif category == "New Phrase":
                self.db.add_new_phrase(text)
            else:
                QMessageBox.warning(
                    self, "Invalid Selection", f"Unsupported category: {category}"
                )
                return
            print(f"{category} remembered.")
            self.memory_input.clear()

        except Exception as e:
            print(f"Error remembering input: {e}")
            QMessageBox.critical(
                self, "Error", "Failed to remember input. Check logs for details."
            )

    def clear_report(self):
        """
        Clear the report and feedback UI.
        """
        global feedback
        feedback = None
        self.grammar_text.clear()
        self.vocab_text.clear()
        self.phrase_text.clear()
        self.grammar_remember_btn.setEnabled(False)
        self.vocab_remember_btn.setEnabled(False)
        self.phrase_remember_btn.setEnabled(False)

    def generate_quiz(self):
        """
        Generate a quiz from feedback.
        """
        gen_ai_apis.create_quiz(feedback_json)

    def generate_memory_quiz(self):
        """
        Generate a quiz from memory (learnings).
        """
        learnings = self.db.get_random_from_tables(
            ["GrammarMistakes", "BetterPhrases", "BetterVocabulary", "NewWords", "NewPhrases"], total_limit=10)
        formatted_json = helper.format_learnings_to_json(learnings)
        json_object = json.dumps(formatted_json, indent=2)
        print(json_object)
        with open(learnings_json, "w") as outfile:
            outfile.write(json_object)

        gen_ai_apis.create_quiz(learnings_json)

    def start_quiz(self):
        """
        Start the quiz and show the first flashcard.
        """
        try:
            with open(quiz_json, "r") as infile:
                self.qa_pairs = json.load(infile)
        except Exception:
            self.qa_pairs = []

        if not self.qa_pairs:
            self.quiz_display.setPlainText("No quiz content found.")
            return

        self.current_index = 0
        self.showing_question = True
        self.next_btn.setEnabled(True)
        self.prev_btn.setEnabled(False)
        self.show_flashcard()

    def show_flashcard(self):
        """
        Show the current flashcard (question/answer).
        """
        q = self.qa_pairs[self.current_index]["question"]
        a = self.qa_pairs[self.current_index]["answer"]
        if self.showing_question:
            self.quiz_display.setHtml(f"<b>Question:</b><br>{q}")
        else:
            self.quiz_display.setHtml(
                f"<b>Question:</b><br>{q}<br><br><b>Answer:</b><br>{a}"
            )

    def next_flashcard(self):
        """
        Show the next flashcard or answer.
        """
        if self.showing_question:
            self.showing_question = False
        else:
            self.showing_question = True
            self.current_index += 1
            if self.current_index >= len(self.qa_pairs):
                self.quiz_display.setHtml(
                    '<div style="color: green;"><b>🎉 End of Quiz!</b></div>'
                )
                self.next_btn.setEnabled(False)
                return
        self.prev_btn.setEnabled(self.current_index > 0)
        self.show_flashcard()

    def prev_flashcard(self):
        """
        Show the previous flashcard.
        """
        if self.showing_question:
            self.current_index = max(0, self.current_index - 1)
        self.showing_question = True
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(True)
        self.show_flashcard()

    def improve_conversation(self):
        """
        Call the English enhancer to improve the conversation.
        """
        gen_ai_apis.improve_english()

    def show_conversation_diff(self):
        """
        Load and display the original and improved conversation.
        """
        with open(conversation_txt, "r") as f:
            conv = f.read()
        with open(improv_conversation_txt, "r") as f:
            improved = f.read()

        # Use helper to format for display
        self.conv_text.setPlainText(helper.parse_conversation_for_display(conv))
        self.improved_text.setPlainText(helper.parse_conversation_for_display(improved))

    def clear_enhancer_texts(self):
        """
        Clear the enhancer text boxes.
        """
        self.conv_text.clear()
        self.improved_text.clear()


# Run app with qasync event loop
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("images/kili_logo.png"))
    app.setApplicationName("Kili - English Learning App")
    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI', 'Arial', sans-serif;
            font-size: 15px;
            background-color: #f9fafb;
            color: #333;
        }
        QTabWidget::pane {
            border: none;
            background: transparent;
            padding: 8px;
        }
        QTabBar::tab {
            background: #e2e8f0;
            border: none;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            padding: 8px 20px;
            margin-right: 4px;
            color: #334155;
        }
        QTabBar::tab:selected {
            background: #ffffff;
            font-weight: 600;
            color: #1e3a8a;
            border-bottom: 2px solid #1e3a8a;
        }
        QTabBar::tab:hover {
            background: #f1f5f9;
        }
        QTextEdit, QLineEdit {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 8px;
            font-size: 15px;
        }
        QPushButton {
            background-color: #14b8a6;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #0d9488;
        }
        QPushButton:pressed {
            background-color: #0f766e;
        }
        QComboBox {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 6px 12px;
        }
        QScrollBar:vertical, QScrollBar:horizontal {
            background: #f1f5f9;
            border: none;
            width: 10px;
        }
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
            background: #cbd5e1;
            border-radius: 5px;
        }
    """)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = EnglishTutorApp()
    window.resize(800, 800)
    window.show()
    openai_config = {
        "auth_key": auth_key,
        "system_audio": system_audio,
        "user_audio": user_audio,
        "feedback_json": feedback_json,
        "quiz_json": quiz_json,
        "conversation_txt": conversation_txt,
        "improv_conversation_txt": improv_conversation_txt,
    }
    gen_ai_apis.init_openai_client(openai_config)

    with loop:
        loop.run_forever()
