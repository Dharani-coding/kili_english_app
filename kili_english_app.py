import sys
import asyncio
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from pydub import AudioSegment
import tempfile
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QLineEdit, QTabWidget
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl

from qasync import QEventLoop
import gen_ai_apis

auth_key = "openai_auth_key.txt"
system_audio = "output/system_audio.mp3"
user_audio = "output/user_audio.mp3"
feedback_json = "output/feedback.json"
quiz_txt = "output/quiz.txt"
conversation_txt = "output/conversation.txt"
db_file = "database/english_learnings.db"

# Recording Thread
class RecorderThread(QThread):
    finished = pyqtSignal()

    def __init__(self, samplerate=44100):
        super().__init__()
        self.samplerate = samplerate
        self.recording = []
        self.running = False

    def run(self):
        self.running = True
        with sd.InputStream(samplerate=self.samplerate, channels=1, callback=self.callback):
            while self.running:
                sd.sleep(100)
        self.finished.emit()

    def callback(self, indata, frames, time, status):
        if self.running:
            self.recording.append(indata.copy())

    def stop(self):
        self.running = False

    def save_to_mp3(self):
        audio = np.concatenate(self.recording, axis=0)
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_wav.close()
        write(temp_wav.name, self.samplerate, audio)
        sound = AudioSegment.from_wav(temp_wav.name)
        sound.export(user_audio, format="mp3")
        os.remove(temp_wav.name)
        return user_audio


# Main Application
class EnglishTutorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kili - English Learning App")
        self.recorder_thread = None
        self.init_ui()

    def init_ui(self):
        # Create the main layout
        main_layout = QVBoxLayout()

        # Create tab widget
        tab_widget = QTabWidget()

        # === 1. Chat Tab ===
        chat_tab = QWidget()
        chat_layout = QVBoxLayout()

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet(
            "font-size: 16px; background-color: #fffbe6; border: 2px solid #f0ad4e; border-radius: 10px; padding: 10px;"
        )

        chat_layout.addWidget(self.chat_display)

        btn_layout = QHBoxLayout()
        self.record_btn = QPushButton("Record")
        self.record_btn.setCheckable(True)
        self.record_btn.setChecked(False)
        self.record_btn.toggled.connect(self.toggle_recording)

        self.clear_chat_btn = QPushButton("Clear chat")
        self.clear_chat_btn.clicked.connect(self.clear_chat)

        self.del_history_btn = QPushButton("Delete History")
        self.del_history_btn.clicked.connect(gen_ai_apis.delete_chat_history)

        btn_layout.addWidget(self.record_btn)
        btn_layout.addWidget(self.clear_chat_btn)
        btn_layout.addWidget(self.del_history_btn)
        chat_layout.addLayout(btn_layout)

        msg_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.send_message)
        msg_layout.addWidget(self.msg_input)
        msg_layout.addWidget(self.send_btn)

        chat_layout.addLayout(msg_layout)
        chat_tab.setLayout(chat_layout)

        # === 2. Report Tab ===
        report_tab = QWidget()
        report_layout = QVBoxLayout()

        report_header = QHBoxLayout()
        report_title = QLabel("<b>Conversation Report and storage</b>")
        self.gen_btn = QPushButton("Generate")
        self.gen_btn.clicked.connect(self.get_report)
        report_header.addWidget(report_title)
        report_header.addStretch()
        report_header.addWidget(self.gen_btn)

        self.report_display = QTextEdit()
        self.report_display.setReadOnly(True)
        self.report_display.setStyleSheet(
            "font-size: 16px; background-color: #fffbe6; border: 2px solid #f0ad4e; border-radius: 10px; padding: 10px;"
        )

        report_layout.addLayout(report_header)
        report_layout.addWidget(self.report_display)
        report_tab.setLayout(report_layout)

        # === 3. Quiz Tab ===
        quiz_tab = QWidget()
        quiz_layout = QVBoxLayout()

        quiz_header = QHBoxLayout()
        quiz_title = QLabel("<b>Quiz Generator</b>")
        self.quiz_btn = QPushButton("Generate")
        self.quiz_btn.clicked.connect(self.generate_quiz)

        self.start_quiz_btn = QPushButton("Start Quiz")
        self.start_quiz_btn.clicked.connect(self.start_quiz)

        quiz_header.addWidget(quiz_title)
        quiz_header.addStretch()
        quiz_header.addWidget(self.quiz_btn)
        quiz_header.addWidget(self.start_quiz_btn)

        self.quiz_display = QTextEdit()
        self.quiz_display.setReadOnly(True)
        self.quiz_display.setStyleSheet(
            "font-size: 16px; background-color: #fffbe6; border: 2px solid #f0ad4e; border-radius: 10px; padding: 10px;"
        )

        self.next_btn = QPushButton("Next")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.next_flashcard)

        quiz_layout.addLayout(quiz_header)
        quiz_layout.addWidget(self.quiz_display)
        quiz_layout.addWidget(self.next_btn)
        quiz_tab.setLayout(quiz_layout)

        # Add tabs to tab widget
        tab_widget.addTab(chat_tab, "🗨️ Chat")
        tab_widget.addTab(report_tab, "📄 Report")
        tab_widget.addTab(quiz_tab, "🧠 Quiz")

        # Add tab widget to the main layout
        main_layout.addWidget(tab_widget)
        self.setLayout(main_layout)


    def toggle_recording(self, checked):
        if checked:
            self.record_btn.setText("Stop")  # Optional visual feedback
            self.start_recording()
        else:
            self.record_btn.setText("Record")
            self.stop_recording()
    
    def clear_chat(self):
        self.chat_display.clear()


    def start_recording(self):
        print("[System] Recording started...")
        self.recorder_thread = RecorderThread()
        self.recorder_thread.finished.connect(lambda: asyncio.create_task(self.on_recording_finished()))
        self.recorder_thread.start()

    def stop_recording(self):
        if self.recorder_thread:
            self.recorder_thread.stop()

    def play_audio(self, filename="system_audio.mp3"):
        self.audio_player = QMediaPlayer()
        self.audio_player.setMedia(QMediaContent(QUrl.fromLocalFile(filename)))
        self.audio_player.play()

    def del_audio(self):
        if hasattr(self, "audio_player"):
            self.audio_player.stop()
            self.audio_player.setMedia(QMediaContent())  # clears the file
            self.audio_player.deleteLater()  # deletes QMediaPlayer safely
            del self.audio_player

    async def on_recording_finished(self):
        self.del_audio()
        path = await asyncio.to_thread(self.recorder_thread.save_to_mp3)
        print(f"[System] Audio saved to: {path}")

        user_text = await asyncio.to_thread(gen_ai_apis.speech_to_text)
        self.send_message(user_text, "You")

        system_reply = await asyncio.to_thread(gen_ai_apis.convo_builder, user_text)
        await asyncio.to_thread(gen_ai_apis.text_to_speech, input=system_reply)

        await asyncio.to_thread(self.play_audio)
        self.send_message(system_reply, "System")


    def send_message(self, text=None, sender="You"):
        if text is None:
            text = self.msg_input.text()
        self.chat_display.append(f"{sender}: {text}")
        self.msg_input.clear()

    def get_report(self):
        gen_ai_apis.convo_corrector()

    def generate_quiz(self):
        gen_ai_apis.create_quiz()

    def start_quiz(self):
        try:
            with open(quiz_txt, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            self.quiz_display.setPlainText("Quiz file not found.")
            return

        # Parse Q-A pairs
        self.qa_pairs = []
        question, answer = "", ""
        for line in lines:
            if line.strip().startswith("Q:"):
                question = line.strip()[2:].strip()
            elif line.strip().startswith("A:"):
                answer = line.strip()[2:].strip()
                if question and answer:
                    self.qa_pairs.append((question, answer))
                    question, answer = "", ""

        if not self.qa_pairs:
            self.quiz_display.setPlainText("No valid quiz content found.")
            return

        self.current_index = 0
        self.showing_question = True
        self.next_btn.setEnabled(True)
        self.show_flashcard()

    def next_flashcard(self):
        if self.current_index >= len(self.qa_pairs):
            self.quiz_display.setHtml('<div style="color: green; font-size: 18px;"><b>🎉 End of the quiz!</b></div>')
            self.next_btn.setEnabled(False)
            return

        self.show_flashcard()

    def show_flashcard(self):
        question, answer = self.qa_pairs[self.current_index]
        if self.showing_question:
            self.quiz_display.setHtml(f"""
            <div style='padding:10px; border-radius:10px; font-size:16px;'>
                <b>Question:</b><br>{question}
            </div>
            """)
            self.showing_question = False
        else:
            self.quiz_display.setHtml(f"""
            <div style='background-color:#dff0d8; padding:10px; border-radius:10px; font-size:16px; color:#3c763d;'>
                <b>Answer:</b><br>{answer}
            </div>
            """)
            self.showing_question = True
            self.current_index += 1


# Run app with qasync event loop
if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = EnglishTutorApp()
    window.resize(600, 700)
    window.show()
    gen_ai_apis.init_openai_client(auth_key, system_audio, user_audio, feedback_json, quiz_txt, conversation_txt)

    with loop:
        loop.run_forever()
