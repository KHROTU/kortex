import sys
import math
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, QRectF, QPointF, QPoint, QRect
from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QBrush, QIcon, QPixmap, QFont, QPainterPath, QPen
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QSystemTrayIcon, QMenu, QPushButton, 
                             QVBoxLayout, QDialog, QLineEdit, QTextEdit, QFormLayout, QHBoxLayout,
                             QMessageBox)
from opensimplex import OpenSimplex
from kortex.settings_ui import SettingsWindow


class AppState:
    IDLE = 0
    LISTENING = 1
    PROCESSING = 2
    SPEAKING = 3
    AWAITING_SELECTION = 4


class EmailPreviewDialog(QDialog):
    send_confirmed = pyqtSignal(dict)

    def __init__(self, recipient, subject, body, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Email")
        self.setMinimumSize(450, 350)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.recipient_input = QLineEdit(recipient)
        self.subject_input = QLineEdit(subject)
        self.body_input = QTextEdit(body)
        self.body_input.setMinimumHeight(150)

        form_layout.addRow("To:", self.recipient_input)
        form_layout.addRow("Subject:", self.subject_input)
        layout.addLayout(form_layout)
        layout.addWidget(self.body_input)

        button_layout = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("background-color: #6c757d;")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.send_button)

        layout.addLayout(button_layout)
        
        self.send_button.clicked.connect(self.confirm_send)
        self.cancel_button.clicked.connect(self.reject)

    def confirm_send(self):
        email_details = {
            "recipient": self.recipient_input.text(),
            "subject": self.subject_input.text(),
            "body": self.body_input.toPlainText()
        }
        self.send_confirmed.emit(email_details)
        self.accept()


class SelectionWidget(QWidget):
    selection_made = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(8)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.setDuration(300)

        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(200)

    def populate_options(self, options):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for option in options[:5]:
            btn = QPushButton(option.title())
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.15);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.25);
                    border-radius: 8px;
                    padding: 10px;
                    font-size: 14px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.25);
                    border: 1px solid rgba(255, 255, 255, 0.4);
                }
                QPushButton:pressed {
                    background-color: rgba(0, 0, 0, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                }
            """)
            btn.clicked.connect(lambda _, o=option: self.selection_made.emit(o))
            self.layout.addWidget(btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.6);
                border: none;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
                margin-top: 5px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
            QPushButton:pressed { background-color: rgba(0, 0, 0, 0.1); }
        """)
        cancel_btn.clicked.connect(lambda: self.selection_made.emit(""))
        self.layout.addWidget(cancel_btn)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(40, 40, 40, 230))
        painter.setPen(QPen(QColor(120, 120, 120, 150), 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 16, 16)

    def animate_show(self, target_geometry):
        self.setWindowOpacity(1.0)
        self.setGeometry(target_geometry.x(), target_geometry.y() + 50, target_geometry.width(), 0)
        self.show()
        self.animation.setEndValue(target_geometry)
        self.animation.start()
        
    def animate_hide(self):
        try: self.opacity_animation.finished.disconnect()
        except TypeError: pass
        self.opacity_animation.setStartValue(self.windowOpacity())
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.finished.connect(self.hide)
        self.opacity_animation.start()


class TimerWidget(QWidget):
    dismiss_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(140, 140)

        self.total_seconds = 1
        self.seconds_left = 0
        
        self.time_font = QFont("Segoe UI", 26, QFont.Bold)
        self.label_font = QFont("Segoe UI", 9, QFont.Medium)
        
        self.close_button = QPushButton("×", self)
        self.close_button.setGeometry(self.width() - 34, 10, 24, 24)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.2);
                color: rgba(255, 255, 255, 0.7);
                border-radius: 12px;
                font-size: 18px; font-weight: bold; padding-bottom: 2px;
            }
            QPushButton:hover { background-color: rgba(0, 0, 0, 0.4); }
        """)
        self.close_button.clicked.connect(self.dismiss_requested.emit)

        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(300)

    def update_display(self, seconds_left, total_seconds):
        self.seconds_left = seconds_left
        self.total_seconds = max(1, total_seconds)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bg_gradient = QRadialGradient(self.width() / 2, self.height() / 2, self.width() / 2)
        bg_gradient.setColorAt(0, QColor(45, 45, 45, 230))
        bg_gradient.setColorAt(1, QColor(25, 25, 25, 230))
        painter.setBrush(bg_gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.rect())

        progress_rect = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        painter.setPen(QPen(QColor(255, 255, 255, 25), 4))
        painter.drawArc(progress_rect, 0 * 16, 360 * 16)

        progress_angle = (self.seconds_left / self.total_seconds) * 360
        pen_progress = QPen(QColor(10, 132, 255), 5)
        pen_progress.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_progress)
        painter.drawArc(progress_rect, 90 * 16, -int(progress_angle * 16))

        minutes = self.seconds_left // 60
        seconds = self.seconds_left % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        main_text_rect = QRect(0, 0, self.width(), self.height() - 25)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(self.time_font)
        painter.drawText(main_text_rect, Qt.AlignCenter, time_str)
        
        label_text_rect = QRect(0, main_text_rect.height() - 15, self.width(), 20)
        painter.setPen(QColor(255, 255, 255, 150))
        painter.setFont(self.label_font)
        painter.drawText(label_text_rect, Qt.AlignCenter, "REMAINING")

    def fade_in(self):
        self.show()
        self.opacity_animation.setStartValue(0.0); self.opacity_animation.setEndValue(1.0); self.opacity_animation.start()

    def fade_out(self):
        try: self.opacity_animation.finished.disconnect()
        except TypeError: pass
        self.opacity_animation.setStartValue(self.windowOpacity()); self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.finished.connect(self.hide); self.opacity_animation.start()


class KortexGUI(QWidget):
    selection_confirmed = pyqtSignal(str)
    restart_triggered = pyqtSignal()
    timer_finished = pyqtSignal()
    email_send_confirmed = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.state = AppState.IDLE
        self.volume_level = 0
        self.drag_position = None
        self.noise = OpenSimplex(seed=1234)
        self.noise_offset = 0
        self.settings_window = None
        self.email_dialog = None

        self.num_points = 80
        self.precomputed_angles = [(i / self.num_points) * 2 * math.pi for i in range(self.num_points + 1)]
        self.precomputed_cos = [math.cos(angle) for angle in self.precomputed_angles]
        self.precomputed_sin = [math.sin(angle) for angle in self.precomputed_angles]

        self.state_params = {
            AppState.IDLE: {'noise_amount': 0.15, 'base_radius': 50, 'noise_speed': 0.005},
            AppState.LISTENING: {'noise_amount': 0.1, 'base_radius': 50, 'noise_speed': 0.02},
            AppState.PROCESSING: {'noise_amount': 0.3, 'base_radius': 50, 'noise_speed': 0.03},
            AppState.SPEAKING: {'noise_amount': 0.3, 'base_radius': 50, 'noise_speed': 0.03},
            AppState.AWAITING_SELECTION: {'noise_amount': 0.1, 'base_radius': 50, 'noise_speed': 0.02}
        }
        self.current_params = self.state_params[AppState.IDLE].copy()
        
        self.timer_widget = None
        self.countdown_timer = QTimer(self)
        self.seconds_remaining = 0
        self.total_duration = 1
        
        self.show_timer_action = None
        self.timer_separator = None

        self.initUI()
        self.init_animations()
        self.init_tray_icon()
        
        self.countdown_timer.timeout.connect(self.update_countdown)

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, 300, 300)

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.start_pos = QPoint(
            screen_geometry.width() - self.width() - 50,
            screen_geometry.height() - self.height() - 50
        )
        self.move(self.start_pos)
        
        self.selection_ui = SelectionWidget(self)
        self.selection_ui.selection_made.connect(self._handle_selection_made)
        self.selection_ui.hide()
        
        self.timer_widget = TimerWidget(self)
        self.timer_widget.dismiss_requested.connect(self.hide_timer_ui)
        self.timer_widget.hide()
        
        self.setWindowOpacity(0.0)
        self.hide()

    def init_animations(self):
        self.animation_timer = QTimer(self); self.animation_timer.timeout.connect(self.update); self.animation_timer.start(16)
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity"); self.opacity_animation.setDuration(300); self.opacity_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.snap_animation = QPropertyAnimation(self, b"pos"); self.snap_animation.setDuration(400); self.snap_animation.setEasingCurve(QEasingCurve.OutExpo)

    def fade_in(self):
        self.opacity_animation.stop()
        try: self.opacity_animation.finished.disconnect()
        except TypeError: pass
        self.show()
        self.opacity_animation.setStartValue(self.windowOpacity()); self.opacity_animation.setEndValue(1.0); self.opacity_animation.start()

    def fade_out(self):
        self.opacity_animation.stop()
        try: self.opacity_animation.finished.disconnect()
        except TypeError: pass
        self.opacity_animation.setStartValue(self.windowOpacity()); self.opacity_animation.setEndValue(0.0); self.opacity_animation.finished.connect(self.hide); self.opacity_animation.start()

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        pixmap = QPixmap(64, 64); pixmap.fill(Qt.transparent); painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing); gradient = QRadialGradient(32, 32, 32)
        gradient.setColorAt(0, QColor(150, 100, 255)); gradient.setColorAt(1, QColor(120, 80, 255))
        painter.setBrush(QBrush(gradient)); painter.setPen(Qt.NoPen); painter.drawEllipse(4, 4, 56, 56); painter.end()
        self.tray_icon.setIcon(QIcon(pixmap)); self.tray_icon.setToolTip("Kortex Assistant")
        
        tray_menu = QMenu()
        self.show_timer_action = tray_menu.addAction("Show Timer")
        self.show_timer_action.triggered.connect(self.show_timer_ui)
        self.show_timer_action.setVisible(False)
        self.timer_separator = tray_menu.addSeparator()
        self.timer_separator.setVisible(False)

        settings_action = tray_menu.addAction("Settings"); settings_action.triggered.connect(self.open_settings)
        restart_action = tray_menu.addAction("Restart Kortex"); restart_action.triggered.connect(self.handle_restart)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Quit Kortex"); quit_action.triggered.connect(QApplication.instance().quit)
        
        self.tray_icon.setContextMenu(tray_menu); self.tray_icon.show()

    def open_settings(self):
        if self.settings_window is None: self.settings_window = SettingsWindow()
        self.settings_window.show(); self.settings_window.activateWindow()

    def handle_restart(self):
        self.restart_triggered.emit()
        QApplication.instance().quit()
        
    def _handle_selection_made(self, selection):
        self.hide_selection_ui()
        self.selection_confirmed.emit(selection)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft(); event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position); event.accept()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.timer_widget and self.timer_widget.isVisible():
            self.reposition_timer_widget()

    def mouseReleaseEvent(self, event):
        self.drag_position = None; self.snap_to_edge(); event.accept()

    def contextMenuEvent(self, event):
        context_menu = QMenu(self); quit_action = context_menu.addAction("Quit Kortex")
        quit_action.triggered.connect(QApplication.instance().quit); context_menu.exec_(self.mapToGlobal(event.pos()))

    def reposition_timer_widget(self):
        widget_size = self.timer_widget.size()
        self.timer_widget.move(self.x()+(self.width()//2)-(widget_size.width()//2), self.y()-widget_size.height()-10)

    def start_timer(self, duration_seconds):
        self.total_duration = duration_seconds
        self.seconds_remaining = duration_seconds
        self.timer_widget.update_display(self.seconds_remaining, self.total_duration)
        
        self.show_timer_ui()
        self.countdown_timer.start(1000)

        if self.show_timer_action: self.show_timer_action.setVisible(True)
        if self.timer_separator: self.timer_separator.setVisible(True)

    def update_countdown(self):
        self.seconds_remaining -= 1
        if self.seconds_remaining >= 0:
            self.timer_widget.update_display(self.seconds_remaining, self.total_duration)
        else:
            self.cancel_timer_ui(is_finished=True)

    def hide_timer_ui(self):
        self.timer_widget.fade_out()

    def show_timer_ui(self):
        if self.countdown_timer.isActive() or self.seconds_remaining > 0:
            self.reposition_timer_widget()
            self.timer_widget.fade_in()

    def cancel_timer_ui(self, is_finished=False):
        if self.countdown_timer.isActive():
            self.countdown_timer.stop()
            self.timer_widget.fade_out()
            self.timer_finished.emit()
            if is_finished:
                for _ in range(3): QApplication.beep()

        if self.show_timer_action: self.show_timer_action.setVisible(False)
        if self.timer_separator: self.timer_separator.setVisible(False)

    def update_volume(self, volume_level):
        self.volume_level = volume_level

    def show_selection_ui(self, options):
        height = len(options[:5]) * 48 + 48 + 30 
        local_rect = QRectF(self.width()/2 - 125, self.height()/2 - height - 30, 250, height)
        global_top_left = self.mapToGlobal(local_rect.topLeft().toPoint())
        global_geo = QRect(global_top_left, local_rect.size().toSize())

        self.selection_ui.populate_options(options)
        self.selection_ui.animate_show(global_geo)

    def hide_selection_ui(self):
        self.selection_ui.animate_hide()
    
    def show_email_preview(self, email_details):
        if self.email_dialog is None:
            self.email_dialog = EmailPreviewDialog(
                email_details.get('recipient', ''),
                email_details.get('subject', ''),
                email_details.get('body', ''),
                self
            )
            self.email_dialog.send_confirmed.connect(self.email_send_confirmed)
            self.email_dialog.finished.connect(self._on_email_dialog_closed)
            self.email_dialog.show()
        else:
            self.email_dialog.activateWindow()

    def _on_email_dialog_closed(self):
        self.email_dialog = None
        
    def show_notification(self, title, message):
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        center_x, center_y = self.width() / 2, self.height() / 2

        target_params = self.state_params[self.state]
        target_noise_amount = target_params['noise_amount']
        target_base_radius = target_params['base_radius']

        if self.state == AppState.LISTENING:
            normalized_volume = min(self.volume_level / 1500.0, 1.0)
            target_noise_amount = 0.1 + normalized_volume * 0.8
            target_base_radius = 50 + normalized_volume * 20
        elif self.state == AppState.AWAITING_SELECTION:
            target_noise_amount = self.state_params[AppState.LISTENING]['noise_amount']
            target_base_radius = self.state_params[AppState.LISTENING]['base_radius']

        lerp_factor = 0.1
        self.current_params['noise_amount'] += (target_noise_amount - self.current_params['noise_amount']) * lerp_factor
        self.current_params['base_radius'] += (target_base_radius - self.current_params['base_radius']) * lerp_factor
        self.current_params['noise_speed'] += (target_params['noise_speed'] - self.current_params['noise_speed']) * lerp_factor
        
        path = QPainterPath()
        for i in range(self.num_points + 1):
            cos_angle = self.precomputed_cos[i]
            sin_angle = self.precomputed_sin[i]
            noise_val = self.noise.noise3(cos_angle, sin_angle, self.noise_offset)
            
            radius = self.current_params['base_radius'] + (noise_val * self.current_params['base_radius'] * self.current_params['noise_amount'])
            x, y = center_x + radius * cos_angle, center_y + radius * sin_angle
            if i == 0: path.moveTo(x, y)
            else: path.lineTo(x, y)

        gradient = QRadialGradient(center_x, center_y, self.current_params['base_radius'] * 1.5)
        if self.state in [AppState.LISTENING, AppState.AWAITING_SELECTION]:
            gradient.setColorAt(0, QColor(100, 200, 255, 230)); gradient.setColorAt(0.7, QColor(80, 150, 255, 180)); gradient.setColorAt(1, QColor(0, 0, 255, 0))
        else:
            gradient.setColorAt(0, QColor(150, 100, 255, 230)); gradient.setColorAt(0.7, QColor(120, 80, 255, 180)); gradient.setColorAt(1, QColor(100, 0, 255, 0))
        
        painter.setBrush(QBrush(gradient)); painter.setPen(Qt.NoPen); painter.drawPath(path)
        self.noise_offset += self.current_params['noise_speed']

    def update_state(self, new_state):
        self.state = new_state
        if new_state == AppState.IDLE: self.hide_selection_ui()

    def snap_to_edge(self):
        screen_rect = QApplication.primaryScreen().availableGeometry(); win_rect = self.frameGeometry(); margin = 50
        snap_points = [
            QPoint(margin, margin), QPoint(screen_rect.width() // 2 - win_rect.width() // 2, margin),
            QPoint(screen_rect.width() - win_rect.width() - margin, margin),
            QPoint(margin, screen_rect.height() // 2 - win_rect.height() // 2),
            QPoint(screen_rect.width() - win_rect.width() - margin, screen_rect.height() // 2 - win_rect.height() // 2),
            QPoint(margin, screen_rect.height() - win_rect.height() - margin),
            QPoint(screen_rect.width() // 2 - win_rect.width() // 2, screen_rect.height() - win_rect.height() - margin),
            QPoint(screen_rect.width() - win_rect.width() - margin, screen_rect.height() - win_rect.height() - margin)
        ]
        closest_point = min(snap_points, key=lambda p: (p.x() - self.pos().x())**2 + (p.y() - self.pos().y())**2)
        self.snap_animation.setStartValue(self.pos()); self.snap_animation.setEndValue(closest_point); self.snap_animation.start()