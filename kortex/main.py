import sys
import os
import pythoncom
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QEventLoop, pyqtSlot, QTimer

from kortex.gui import KortexGUI, AppState
from kortex.stt import SpeechToText
from kortex.tts import TextToSpeech
from kortex.llm import LLMClient
from kortex.tools import web, system, productivity, communication
from kortex import database
import yaml


class AssistantWorker(QObject):
    state_changed = pyqtSignal(int)
    volume_updated = pyqtSignal(float)
    show_ui_signal = pyqtSignal()
    hide_ui_signal = pyqtSignal()
    show_selection_signal = pyqtSignal(list)
    show_email_preview_signal = pyqtSignal(dict)
    show_notification_signal = pyqtSignal(str, str)
    timer_started_signal = pyqtSignal(int)
    timer_cancelled_signal = pyqtSignal()

    def __init__(self, config_path="kortex/config.yaml"):
        super().__init__()
        self.config_path = config_path
        self._is_running = True
        self.stt = None
        self.applications = {}
        self.timer_is_active = False
        
        self.current_mode = "wake_word"
        self.pending_action = None
        
        self.task_checker_timer = QTimer(self)
        self.task_checker_timer.timeout.connect(self.check_scheduled_tasks)

    def stop(self):
        print("Shutdown signal received.")
        self._is_running = False
        if self.stt: self.stt.close()

    @pyqtSlot(str)
    def handle_user_selection(self, selection):
        if self.current_mode == "awaiting_selection" and self.pending_action:
            action = self.pending_action
            self.pending_action = None
            
            final_response = ""
            if selection:
                if action['type'] == 'open_application':
                    final_response = system.open_application_internal(self.applications[selection])
            else:
                final_response = "Okay, cancelled."
            
            self.state_changed.emit(AppState.SPEAKING)
            self.tts.speak(final_response)
            self.state_changed.emit(AppState.IDLE)
            self.hide_ui_signal.emit()
            self.current_mode = "wake_word"

    @pyqtSlot(dict)
    def handle_email_send_confirmed(self, email_details):
        self.state_changed.emit(AppState.PROCESSING)
        result = communication.send_email_final(
            email_details['recipient'],
            email_details['subject'],
            email_details['body'],
            self.config_path
        )
        self.state_changed.emit(AppState.SPEAKING)
        self.tts.speak(result)
        self.state_changed.emit(AppState.IDLE)
        self.hide_ui_signal.emit()
        self.current_mode = "wake_word"

    @pyqtSlot()
    def on_timer_finished(self):
        self.timer_is_active = False
        print("Backend notified: Timer finished.")

    def check_scheduled_tasks(self):
        reminders = database.get_due_tasks("reminders")
        for r in reminders:
            message = f"Here is your reminder: {r['reminder_text']}"
            self.show_notification_signal.emit("Kortex Reminder", message)
            self.tts.speak(message)
            database.mark_task_triggered(r['id'], "reminders")

        alarms = database.get_due_tasks("alarms")
        for a in alarms:
            message = f"Alarm! It's time for your alarm."
            self.show_notification_signal.emit("Kortex Alarm", message)
            self.tts.speak(message)
            database.mark_task_triggered(a['id'], "alarms")

    def run(self):
        pythoncom.CoInitialize()
        try:
            database.init_db()
            self.applications = system.scan_applications()
            with open(self.config_path, 'r') as f: config = yaml.safe_load(f)
            wake_words = config['wake_words']
            
            tool_registry = {
                "search_web": web.search_web, "get_weather": web.get_weather, "find_location": web.find_location,
                "convert_currency": web.convert_currency,
                "open_website": system.open_website, "create_folder": system.create_folder,
                "find_application": system.find_application, "set_system_volume": system.set_system_volume,
                "set_screen_brightness": system.set_screen_brightness,
                "set_timer": productivity.set_timer, "cancel_timer": productivity.cancel_timer,
                "write_text": productivity.write_text, "get_current_time": productivity.get_current_time,
                "get_current_date": productivity.get_current_date, "calculate_future_date": productivity.calculate_future_date,
                "calculate_days_between": productivity.calculate_days_between,
                "calculate": productivity.calculate, "convert_units": productivity.convert_units,
                "tell_joke": productivity.tell_joke, "flip_coin": productivity.flip_coin,
                "create_note": productivity.create_note, "read_notes": productivity.read_notes,
                "set_reminder": productivity.set_reminder, "set_alarm": productivity.set_alarm,
                "prepare_email": communication.prepare_email
            }
            
            self.stt = SpeechToText(self.config_path)
            self.tts = TextToSpeech(self.config_path)
            self.llm = LLMClient(tool_registry, self.config_path)
            self.task_checker_timer.start(30000)
            self.tts.speak("Kortex is now running.")
            
            while self._is_running:
                if self.current_mode in ["wake_word", "command"]:
                    text = self.stt.process_chunk(
                        is_wake_word_detection=(self.current_mode == "wake_word"),
                        volume_callback=self.volume_updated.emit if self.current_mode == "command" else None
                    )
                    if not text:
                        QThread.msleep(10)
                        continue

                    if self.current_mode == "wake_word" and text in wake_words:
                        self.show_ui_signal.emit()
                        self.state_changed.emit(AppState.SPEAKING); self.tts.speak("Yes?")
                        self.state_changed.emit(AppState.LISTENING); self.current_mode = "command"
                    
                    elif self.current_mode == "command":
                        if len(text.strip().split()) <= 1: continue

                        self.state_changed.emit(AppState.PROCESSING)
                        llm_response = self.llm.get_response(text)
                        final_response = ""
                        
                        if llm_response['type'] == 'tool_call':
                            data = llm_response['data']; name = data.get('tool_name'); params = data.get('parameters', {})
                            
                            if name == 'find_application':
                                matches = system.find_application(app_query=params.get('app_query'), apps_cache=self.applications)
                                if len(matches) == 1:
                                    final_response = system.open_application_internal(self.applications[matches[0]])
                                elif len(matches) > 1:
                                    self.state_changed.emit(AppState.AWAITING_SELECTION)
                                    self.show_selection_signal.emit(matches)
                                    self.current_mode = "awaiting_selection"
                                    self.pending_action = {'type': 'open_application', 'matches': matches}
                                    continue
                                else:
                                    final_response = f"Sorry, I couldn't find an application like '{params.get('app_query')}'."
                            
                            elif name == 'prepare_email':
                                self.show_email_preview_signal.emit(params)
                                final_response = "I've drafted that email for you to review."
                                self.current_mode = "awaiting_input"

                            elif name == 'set_timer':
                                duration_str = params.get('duration_str', '')
                                total_seconds = productivity.parse_duration(duration_str)
                                if total_seconds > 0:
                                    self.timer_started_signal.emit(total_seconds); self.timer_is_active = True
                                    final_response = f"Okay, timer set for {duration_str}."
                                else: final_response = f"Sorry, I couldn't understand the duration '{duration_str}'."
                            
                            elif name == 'cancel_timer':
                                if self.timer_is_active:
                                    self.timer_cancelled_signal.emit(); self.timer_is_active = False
                                    final_response = "Okay, I've cancelled the timer."
                                else: final_response = "There is no timer running."

                            elif name in ['write_text', 'set_system_volume', 'set_screen_brightness']:
                                tool_registry[name](**params)
                                final_response = "Done."
                            
                            elif name in tool_registry:
                                result = tool_registry[name](**params)
                                summary_prompt = f"Given the user's original request '{text}', provide a concise, natural language answer based on the following tool output: '{result}'"
                                summary = self.llm.get_response(summary_prompt, use_tools=False)
                                final_response = summary.get('data', "Task complete.")
                            
                            else: final_response = f"Tool '{name}' not found."
                        
                        else:
                            final_response = llm_response.get('data', "I'm not sure how to respond.")
                        
                        if self.current_mode != "awaiting_input":
                            self.state_changed.emit(AppState.SPEAKING); self.tts.speak(final_response)
                            self.state_changed.emit(AppState.IDLE); self.hide_ui_signal.emit()
                            self.current_mode = "wake_word"

                else:
                    QThread.msleep(100)

        except (IOError, AttributeError) as e:
            print(f"Main loop interrupted: {e}")
        finally:
            pythoncom.CoUninitialize()
        
        print("Worker thread has finished.")


def start_assistant():
    restart_manager = {'should_restart': False}
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    gui = KortexGUI()
    thread = QThread()
    worker = AssistantWorker()
    worker.moveToThread(thread)
    
    worker.state_changed.connect(gui.update_state)
    worker.volume_updated.connect(gui.update_volume)
    worker.show_ui_signal.connect(gui.fade_in)
    worker.hide_ui_signal.connect(gui.fade_out)
    worker.show_selection_signal.connect(gui.show_selection_ui)
    worker.show_email_preview_signal.connect(gui.show_email_preview)
    worker.show_notification_signal.connect(gui.show_notification)
    worker.timer_started_signal.connect(gui.start_timer)
    worker.timer_cancelled_signal.connect(gui.cancel_timer_ui)
    
    gui.selection_confirmed.connect(worker.handle_user_selection)
    gui.email_send_confirmed.connect(worker.handle_email_send_confirmed)
    gui.timer_finished.connect(worker.on_timer_finished)
    
    def on_restart(): restart_manager['should_restart'] = True
    gui.restart_triggered.connect(on_restart)
    
    def clean_shutdown():
        if thread.isRunning():
            print("Initiating clean shutdown...")
            worker.stop(); thread.quit(); thread.wait()
        print("Shutdown complete.")

    app.aboutToQuit.connect(clean_shutdown)
    thread.started.connect(worker.run); thread.start()
    app.exec_()

    if restart_manager['should_restart']:
        print("Restarting application...")
        os.execv(sys.executable, [sys.executable, '-m', 'kortex.main'])


if __name__ == "__main__":
    start_assistant()