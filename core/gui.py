"""NEXORA desktop shell. Qt owns widgets; the engine owns audio and commands."""
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRectF, QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QFont, QFontDatabase, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
                              QHBoxLayout, QGridLayout, QScrollArea, QLineEdit, QDialog, QComboBox,
                              QSlider, QCheckBox, QSizePolicy)

from core import config, tts
from core.events import set_event_handler
from core.service import AssistantService
from core.text import normalize_text
from core.ui_visuals import CoreVisual, ScenePanel

ASSETS = config.RESOURCE_DIR / "assets" / "nexora"
BLUE = "#426bff"
MUTED = "#969ca8"
STYLES = """
QWidget { color: #e6ebf5; font-family: 'Vazirmatn'; font-size: 14px; }
QMainWindow, QDialog { background: #090c12; }
QLabel { background: transparent; }
QFrame#panel { background: #0f141e; border: 1px solid #263044; border-radius: 24px; }
QFrame#compose { background: #171e2c; border: 1px solid #303d55; border-radius: 18px; }
QFrame#tabs { background: #101620; border: 1px solid #242e3f; border-radius: 15px; }
QLabel#eyebrow { color: #8e9bb6; font-family: 'Manrope'; font-size: 10px; letter-spacing: 2px; }
QLabel#muted { color: #96a4bf; font-size: 12px; }
QLabel#title { color: #edf2fc; font-size: 34px; font-weight: 500; }
QLabel#section { color: #e6edfb; font-size: 17px; font-weight: 600; }
QLabel#badge { background: #1a2540; color: #b8cbfb; border: 1px solid #344971; border-radius: 12px; padding: 4px 12px; font-size: 11px; }
QPushButton { background: #131a26; border: 1px solid #303c52; border-radius: 14px; padding: 9px 17px; color: #c7d2e6; min-height: 22px; }
QPushButton:hover { background: #202d44; border-color: #617cb3; color: white; }
QPushButton:pressed { background: #293e67; }
QPushButton:disabled { color: #64728b; border-color: #252e3e; background: #111722; }
QPushButton:focus { border: 1px solid #9ab4ff; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #eef4ff,stop:1 #c4d3f5); border: 1px solid #f1f5ff; color: #111c33; border-radius: 24px; min-height: 24px; padding: 13px 32px; font-size: 14px; font-weight: 600; }
QPushButton#primary:hover { background: #ffffff; border-color: white; }
QPushButton#primary:disabled { background: #29344a; border-color: #374560; color: #8b9ab7; }
QPushButton#nav { border: 0; background: transparent; color: #9eacc6; border-radius: 11px; padding: 7px 19px; }
QPushButton#nav:hover { color: white; background: #1c2940; }
QPushButton#activeNav { border: 1px solid #3a4a69; border-radius: 11px; background: #24324c; color: #e6eeff; padding: 7px 19px; }
QPushButton#round { border-radius: 21px; padding: 0; background: #151c29; }
QPushButton#ghost { border: 0; background: transparent; color: #a9badb; padding: 8px 12px; }
QPushButton#ghost:hover { color: white; background: #1c2940; }
QPushButton#quickCard { background: #131d2d; border: 1px solid #293b58; border-radius: 16px; padding: 0; min-height:80px; max-height:80px; }
QPushButton#quickCard:hover { background: #203252; border-color: #6f91d3; }
QPushButton#quickCard:disabled { background: #101722; border-color: #242e40; }
QPushButton#quickCard QLabel { background: transparent; border: 0; }
QPushButton#quick { border: 1px solid #2d3b55; border-radius: 14px; text-align: right; padding: 14px 18px; background: #151e2e; }
QPushButton#quick:hover { background: #223454; border-color: #607fb7; }
QLineEdit, QComboBox { background: #171f2d; border: 1px solid #35445e; border-radius: 12px; padding: 12px; color: #e5edff; selection-background-color: #426bff; }
QLineEdit:focus, QComboBox:focus { border-color: #8faeff; }
QLineEdit#commandInput { border: 0; border-radius: 0; background: transparent; padding: 4px 2px; font-size: 14px; }
QComboBox QAbstractItemView { background: #172234; selection-background-color: #304a78; padding: 6px; }
QComboBox::drop-down { border: 0; width: 25px; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: transparent; width: 4px; margin: 0; }
QScrollBar::handle:vertical { background: #3b4c6c; min-height: 35px; border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSlider::groove:horizontal { height: 4px; background: #2a3954; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #7198ff; border-radius: 2px; }
QSlider::handle:horizontal { background: #e3e9f8; width: 16px; margin: -6px 0; border-radius: 8px; }
QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #657da6; border-radius: 5px; background: #131e31; }
QCheckBox::indicator:checked { background: #426bff; border: 3px solid #a4baff; }
"""


def label(text, name=None, align=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        widget.setObjectName(name)
    if align is not None:
        widget.setAlignment(align | Qt.AlignmentFlag.AlignAbsolute)
    return widget


def icon(name, color="#c8cfdf"):
    paths = {
        "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M6 11v1a6 6 0 0012 0v-1M12 18v4m-3 0h6"/>',
        "send": '<path d="M5 12h14m-6-6 6 6-6 6"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "calendar": '<rect x="4" y="5" width="16" height="16" rx="3"/><path d="M8 3v4m8-4v4M4 10h16m-11 4h.01m3.99 0h.01M9 17h.01"/>',
        "browser": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
        "calculator": '<rect x="5" y="2" width="14" height="20" rx="3"/><path d="M8 6h8M8 11h1m6 0h1m-8 4h1m6 0h1m-8 4h1m6 0h1"/>',
        "sound": '<path d="M11 5 6 9H3v6h3l5 4zM15 8a6 6 0 010 8m3-11a10 10 0 010 14"/>',
        "muted": '<path d="M11 5 6 9H3v6h3l5 4zM16 9l6 6m0-6-6 6"/>',
        "settings": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="#0d0f12"/><circle cx="16" cy="17" r="3" fill="#0d0f12"/>',
        "spark": '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
        "arrow": '<path d="M12 19V5m-5 5 5-5 5 5"/>',
    }
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode()).render(painter)
    painter.end()
    return QIcon(pixmap)


class EventBridge(QObject):
    event = Signal(str, object)


class LevelMeter(QWidget):
    def __init__(self):
        super().__init__()
        self.level = 0.0
        self.clipping = False
        self.setFixedHeight(26)
        self.setMinimumWidth(100)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        count = max(12, self.width() // 8)
        for index in range(count):
            active = index / count < self.level
            color = "#e69679" if self.clipping else BLUE
            painter.setBrush(QColor(color if active else "#252b36"))
            painter.setPen(Qt.PenStyle.NoPen)
            height = 5 + (index % 4) * 3 if active else 4
            painter.drawRoundedRect(QRectF(index * self.width() / count, (26 - height) / 2, 3, height), 1.5, 1.5)

    def set_level(self, value, clipping=False):
        self.level, self.clipping = value, clipping
        self.update()


class QuickAction(QPushButton):
    def __init__(self, text, glyph, command):
        super().__init__()
        self.setObjectName("quickCard")
        self.setAccessibleName(command)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(82)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 12)
        layout.setSpacing(7)
        image = label("", align=Qt.AlignmentFlag.AlignCenter)
        image.setPixmap(icon(glyph, "#a8bdec").pixmap(23, 23))
        caption = label(text, align=Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet("font-size:12px;color:#ced8ec;")
        for widget in (image, caption):
            widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(widget)


class SoundDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.testing = False
        self.setWindowTitle("تنظیم صدا · NEXORA")
        self.setMinimumWidth(520)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(17)
        layout.addWidget(label("صدایت را واضح‌تر بشنوم.", "section"))
        description = label("میکروفون درست را انتخاب کن و شدت ورودی را بررسی کن.", "muted")
        description.setWordWrap(True)
        layout.addWidget(description)
        layout.addWidget(label("میکروفون"))
        self.devices = QComboBox()
        self.devices.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.devices.addItem("پیش‌فرض ویندوز", None)
        try:
            import sounddevice as sd
            hosts = sd.query_hostapis()
            for index, device in enumerate(sd.query_devices()):
                if device["max_input_channels"] > 0:
                    self.devices.addItem(f'{device["name"]} · {hosts[device["hostapi"]]["name"]}', index)
        except Exception as error:
            window.add_message("system", f"فهرست میکروفون‌ها در دسترس نیست: {error}")
        self.devices.setCurrentIndex(max(0, self.devices.findData(window.audio_settings["device"])))
        layout.addWidget(self.devices)
        self.gain_label = label("")
        layout.addWidget(self.gain_label)
        self.gain = QSlider(Qt.Orientation.Horizontal)
        self.gain.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.gain.setRange(10, 30)
        self.gain.setValue(round(window.audio_settings["gain"] * 10))
        self.gain.valueChanged.connect(lambda value: self.gain_label.setText(f"تقویت ورودی: {value / 10:.1f}×"))
        self.gain.valueChanged.emit(self.gain.value())
        self.gain.setAccessibleName("تقویت ورودی میکروفون")
        layout.addWidget(self.gain)
        hint = label("تقویت زیاد ممکن است نویز را بیشتر کند. با مقدار ۱ شروع کن.", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.grammar = QCheckBox("کمک از فهرست فرمان‌ها در تشخیص گفتار")
        self.grammar.setChecked(window.audio_settings["grammar"])
        layout.addWidget(self.grammar)
        layout.addWidget(label("گفتار آزاد بررسی می‌شود. فهرست فرمان‌ها به تشخیص جمله‌های کوتاه کمک می‌کند.", "muted"))
        self.meter = LevelMeter()
        layout.addWidget(self.meter)
        self.test_text = label("هنگام تست، هیچ فرمانی اجرا نمی‌شود.", "muted")
        self.test_text.setWordWrap(True)
        layout.addWidget(self.test_text)
        self.test_button = QPushButton("تست میکروفون")
        self.test_button.setIcon(icon("mic"))
        self.test_button.clicked.connect(self.toggle_test)
        layout.addWidget(self.test_button)
        row = QHBoxLayout()
        save = QPushButton("ذخیره تنظیمات")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        cancel = QPushButton("بستن")
        cancel.clicked.connect(self.reject)
        row.addWidget(save)
        row.addWidget(cancel)
        layout.addLayout(row)

    def values(self):
        return {"device": self.devices.currentData(), "gain": self.gain.value() / 10, "grammar": self.grammar.isChecked()}

    def toggle_test(self):
        self.testing = not self.testing
        self.window.service.submit("test_microphone", enabled=self.testing, **self.values())
        self.test_button.setText("پایان تست" if self.testing else "تست میکروفون")
        self.devices.setEnabled(not self.testing)
        self.gain.setEnabled(not self.testing)
        self.grammar.setEnabled(not self.testing)

    def save(self):
        if self.testing:
            self.toggle_test()
        if self.window.service.submit("settings", **self.values()):
            self.accept()

    def done(self, result):
        if self.testing:
            self.toggle_test()
        super().done(result)


class JarvisWindow(QMainWindow):
    def __init__(self, start_service=True):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("NEXORA · JARVIS")
        self.setWindowIcon(QIcon(str(ASSETS / "mark.svg")))
        self.setMinimumSize(1000, 740)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1280, available.width() - 50), min(860, available.height() - 70))
        self.service = AssistantService()
        self.bridge = EventBridge(self)
        self.bridge.event.connect(self.on_event)
        self.ready = False
        self.voice_available = False
        self.command_groups = ()
        self.listening = False
        self.muted = False
        self.closing = False
        self.state = "loading"
        self.sound_dialog = None
        self.heard_text = ""
        self.audio_settings = {"device": config.MICROPHONE_INDEX, "gain": config.INPUT_GAIN, "grammar": config.COMMAND_GRAMMAR}
        self.messages = []
        self._build()
        if start_service:
            set_event_handler(self.bridge.event.emit)
            self.service.start()
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 20, 26, 14)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(12)
        mark = label("")
        mark.setPixmap(QIcon(str(ASSETS / "mark.svg")).pixmap(36, 32))
        header.addWidget(mark)
        brand = QVBoxLayout()
        brand.setSpacing(1)
        wordmark = label("N E X O R A")
        wordmark.setFont(QFont("Manrope", 12, QFont.Weight.DemiBold))
        brand.addWidget(wordmark)
        brand.addWidget(label("BEYOND WHAT EXISTS.", "eyebrow"))
        header.addLayout(brand)
        header.addStretch()
        tabs = QFrame()
        tabs.setObjectName("tabs")
        tab_layout = QHBoxLayout(tabs)
        tab_layout.setContentsMargins(4, 4, 4, 4)
        tab_layout.setSpacing(3)
        commands = QPushButton("فرمان‌ها")
        commands.setObjectName("nav")
        commands.clicked.connect(self.show_commands)
        tab_layout.addWidget(commands)
        nav = QPushButton("دستیار")
        nav.setObjectName("activeNav")
        nav.setIcon(icon("spark", "#cfddff"))
        nav.clicked.connect(lambda: self.entry.setFocus())
        tab_layout.addWidget(nav)
        header.addWidget(tabs)
        header.addStretch()
        self.status_pill = label("در حال آماده‌سازی", "muted")
        header.addWidget(self.status_pill)
        header.addSpacing(6)
        self.mute_button = QPushButton()
        self.mute_button.setObjectName("round")
        self.mute_button.setIcon(icon("sound"))
        self.mute_button.setFixedSize(42, 42)
        self.mute_button.setToolTip("خاموش‌کردن صدای پاسخ‌ها")
        self.mute_button.setAccessibleName("روشن یا خاموش‌کردن صدای پاسخ‌ها")
        self.mute_button.clicked.connect(self.toggle_mute)
        header.addWidget(self.mute_button)
        self.settings_button = QPushButton()
        self.settings_button.setObjectName("round")
        self.settings_button.setFixedSize(42, 42)
        self.settings_button.setIcon(icon("settings"))
        self.settings_button.setAccessibleName("تنظیم صدا")
        self.settings_button.setToolTip("تنظیم صدا و میکروفون")
        self.settings_button.setEnabled(False)
        self.settings_button.clicked.connect(self.show_sound)
        header.addWidget(self.settings_button)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(20)
        conversation = QFrame()
        conversation.setObjectName("panel")
        conversation.setMinimumWidth(310)
        conversation.setMaximumWidth(410)
        chat = QVBoxLayout(conversation)
        chat.setContentsMargins(22, 23, 22, 18)
        chat.setSpacing(12)
        chat_heading = QHBoxLayout()
        self.confidence_label = label("این جلسه", "muted")
        chat_heading.addWidget(self.confidence_label)
        chat_heading.addStretch()
        chat_heading.addWidget(label("گفت‌وگوی ما", "section"))
        chat.addLayout(chat_heading)
        chat.addWidget(label("هر کاری، از یک جمله شروع می‌شه.", "muted", Qt.AlignmentFlag.AlignRight))
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background:#293347;")
        chat.addWidget(line)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.chat_content = QWidget()
        self.chat_content.setStyleSheet("background:transparent;")
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(0, 5, 3, 8)
        self.chat_layout.setSpacing(16)
        self.conversation_intro = QWidget()
        intro = QVBoxLayout(self.conversation_intro)
        intro.setContentsMargins(9, 30, 9, 16)
        intro.setSpacing(12)
        intro_mark = label("", align=Qt.AlignmentFlag.AlignCenter)
        intro_mark.setPixmap(QIcon(str(ASSETS / "mark.svg")).pixmap(43, 38))
        intro.addWidget(intro_mark)
        intro.addWidget(label("از همین‌جا شروع کن.", "section", Qt.AlignmentFlag.AlignCenter))
        intro_text = label("با صدات یا یک پیام کوتاه،\nکارهای روزمره‌ات رو جلو ببر.", "muted", Qt.AlignmentFlag.AlignCenter)
        intro_text.setWordWrap(True)
        intro.addWidget(intro_text)
        self.chat_layout.addWidget(self.conversation_intro)
        self.chat_layout.addStretch(1)
        self.scroll.setWidget(self.chat_content)
        chat.addWidget(self.scroll, 1)
        compose = QFrame()
        compose.setObjectName("compose")
        compose_layout = QVBoxLayout(compose)
        compose_layout.setContentsMargins(12, 12, 12, 10)
        compose_layout.setSpacing(9)
        self.entry = QLineEdit()
        self.entry.setObjectName("commandInput")
        self.entry.setPlaceholderText("تسکت رو بنویس…")
        self.entry.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        self.entry.setMaxLength(2000)
        self.entry.setAccessibleName("متن فرمان")
        self.entry.setEnabled(False)
        self.entry.returnPressed.connect(lambda: self.submit_text())
        compose_layout.addWidget(self.entry)
        compose_bottom = QHBoxLayout()
        self.send_button = QPushButton()
        self.send_button.setObjectName("send")
        self.send_button.setStyleSheet("QPushButton#send { background:#426bff; border:1px solid #7192ff; border-radius:16px; padding:0; min-width:32px; min-height:32px; max-width:32px; max-height:32px; } QPushButton#send:hover { background:#6387ff; } QPushButton#send:disabled { background:#293957; border-color:#364766; }")
        self.send_button.setIcon(icon("arrow", "#ffffff"))
        self.send_button.setFixedSize(34, 34)
        self.send_button.setAccessibleName("ارسال فرمان")
        self.send_button.setToolTip("ارسال فرمان · Enter")
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(lambda: self.submit_text())
        compose_bottom.addWidget(self.send_button)
        self.edit_heard_button = QPushButton("ویرایش متن شنیده‌شده")
        self.edit_heard_button.setObjectName("ghost")
        self.edit_heard_button.hide()
        self.edit_heard_button.clicked.connect(self.edit_heard)
        compose_bottom.addWidget(self.edit_heard_button)
        compose_bottom.addStretch()
        compose_bottom.addWidget(label("Enter برای ارسال", "muted"))
        compose_layout.addLayout(compose_bottom)
        chat.addWidget(compose)
        note = label("برای پیام تایپی، صدا زدن «جارویس» لازم نیست.", "muted", Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)
        chat.addWidget(note)
        body.addWidget(conversation, 4)

        self.workspace = ScenePanel(ASSETS)
        hero_layout = QVBoxLayout(self.workspace)
        hero_layout.setContentsMargins(28, 22, 28, 22)
        hero_layout.setSpacing(8)
        self.hero_eyebrow = QWidget()
        eyebrow = QHBoxLayout(self.hero_eyebrow)
        eyebrow.setContentsMargins(0, 0, 0, 0)
        eyebrow.addWidget(label("J A R V I S", "eyebrow"))
        eyebrow.addStretch()
        self.mode_badge = label("فرمان‌های فارسی", "badge")
        eyebrow.addWidget(self.mode_badge)
        hero_layout.addWidget(self.hero_eyebrow)
        hero_layout.addSpacing(5)
        self.hero_title = label("با صدای تو، یک قدم جلوتر.", "title", Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.hero_title)
        self.hero_subtitle = label("دستیار شخصی تو، برای کارهای هر روز.", "muted", Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.hero_subtitle)
        self.visual = CoreVisual(ASSETS)
        hero_layout.addWidget(self.visual, 1)
        self.state_label = label("در حال آماده‌سازی…", "section", Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.state_label)
        self.partial = label("مدل فارسی در حال بارگذاری است.", "muted", Qt.AlignmentFlag.AlignCenter)
        self.partial.setWordWrap(True)
        self.partial.setMinimumHeight(27)
        self.partial.setMaximumHeight(46)
        hero_layout.addWidget(self.partial)
        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addStretch()
        self.mic_button = QPushButton("شروع شنیدن")
        self.mic_button.setObjectName("primary")
        self.mic_button.setIcon(icon("mic", "#14213a"))
        self.mic_button.setIconSize(QSize(20, 20))
        self.mic_button.setEnabled(False)
        self.mic_button.clicked.connect(self.toggle_listening)
        controls.addWidget(self.mic_button)
        self.wake_button = QPushButton("بیدار شو")
        self.wake_button.setObjectName("ghost")
        self.wake_button.setToolTip("فعال‌کردن جارویس بدون گفتن نام او")
        self.wake_button.setEnabled(False)
        self.wake_button.clicked.connect(lambda: self.send_control("activate"))
        controls.addWidget(self.wake_button)
        controls.addStretch()
        hero_layout.addLayout(controls)
        audio_row = QHBoxLayout()
        audio_row.addStretch()
        self.meter = LevelMeter()
        self.meter.setFixedWidth(120)
        audio_row.addWidget(self.meter)
        audio_row.addSpacing(8)
        self.level_label = label("میکروفون خاموش", "muted")
        audio_row.addWidget(self.level_label)
        audio_row.addStretch()
        hero_layout.addLayout(audio_row)
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background:#28364e;")
        hero_layout.addWidget(separator)
        quick_title = QHBoxLayout()
        all_commands = QPushButton("همه فرمان‌ها ←")
        all_commands.setObjectName("ghost")
        all_commands.setStyleSheet("font-size:11px;padding:0;min-height:22px;")
        all_commands.clicked.connect(self.show_commands)
        quick_title.addWidget(all_commands)
        quick_title.addStretch()
        quick_title.addWidget(label("یک اشاره، یک کار کمتر", "muted"))
        hero_layout.addLayout(quick_title)
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.quick_buttons = []
        quick_commands = (("ماشین‌حساب", "calculator", "ماشین حساب رو باز کن"),
                          ("مرورگر", "browser", "مرورگر رو باز کن"),
                          ("تقویم امروز", "calendar", "امروز چندمه"),
                          ("ساعت", "clock", "ساعت چنده"))
        for text, glyph, phrase in quick_commands:
            button = QuickAction(text, glyph, phrase)
            button.clicked.connect(lambda checked=False, command=phrase: self.submit_text(command))
            button.setEnabled(False)
            cards.addWidget(button, 1)
            self.quick_buttons.append(button)
        hero_layout.addLayout(cards)
        body.addWidget(self.workspace, 7)
        layout.addLayout(body, 1)
        footer = QHBoxLayout()
        self.engine_label = label("●  تشخیص صدا روی همین دستگاه", "muted")
        footer.addWidget(self.engine_label)
        footer.addStretch()
        self.clock = label("", "eyebrow")
        footer.addWidget(self.clock)
        footer.addStretch()
        footer.addWidget(label("NEXORA  /  PERSONAL INTELLIGENCE", "eyebrow"))
        layout.addLayout(footer)
        for button in root.findChildren(QPushButton):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_clock(self):
        self.clock.setText(datetime.now().strftime("%H:%M"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "hero_eyebrow"):
            compact = self.height() < 810
            self.hero_eyebrow.setVisible(not compact)
            self.hero_subtitle.setVisible(not compact)

    def send_control(self, kind, **data):
        if self.ready and not self.closing:
            if not self.service.submit(kind, **data):
                self.add_message("system", "کمی صبر کن؛ یک فرمان دیگر در حال پردازش است.")

    def toggle_listening(self):
        self.send_control("listening", enabled=not self.listening)
        self.mic_button.setEnabled(False)

    def toggle_mute(self):
        self.muted = not self.muted
        tts.set_muted(self.muted)
        self.mute_button.setIcon(icon("muted" if self.muted else "sound"))
        self.mute_button.setToolTip("روشن‌کردن صدای پاسخ‌ها" if self.muted else "خاموش‌کردن صدای پاسخ‌ها")

    def submit_text(self, text=None):
        text = text if isinstance(text, str) else self.entry.text().strip()
        if not text or not self.ready or self.closing:
            return
        if self.service.submit("text", text=text):
            self.entry.clear()
            self.set_state("processing")
        else:
            self.add_message("system", "فرمان ارسال نشد. چند لحظه دیگر دوباره امتحان کن.")

    def edit_heard(self):
        self.entry.setText(self.heard_text)
        self.entry.setFocus()

    def offer_correction(self, text):
        self.heard_text = text
        self.edit_heard_button.setVisible(bool(text.strip(" …")))

    def set_state(self, state):
        self.state = state
        names = {"loading": "در حال آماده‌سازی…", "paused": "آماده‌ام؛ از کجا شروع کنیم؟",
                 "waiting": "اسمم را صدا بزن.", "listening": "گوش می‌کنم…", "processing": "در حال انجام…",
                 "speaking": "در حال پاسخ…", "testing": "تست میکروفون", "closing": "در حال بستن…", "error": "نیاز به بررسی"}
        self.state_label.setText(names.get(state, state))
        self.visual.active = state in ("listening", "speaking", "processing", "testing")
        self.visual.state = state
        status_names = {"loading": "آماده‌سازی", "paused": "آماده", "waiting": "منتظر صدای تو", "listening": "در حال شنیدن",
                        "processing": "در حال انجام", "speaking": "در حال پاسخ", "testing": "تست میکروفون", "closing": "در حال بستن", "error": "نیاز به بررسی"}
        self.status_pill.setText("●  " + status_names.get(state, state))
        status_color = "#94ddc0" if state == "paused" else "#d9ae86" if state == "error" else "#a8c3ff"
        self.status_pill.setStyleSheet(f"color:{status_color};background:#141f2d;border:1px solid #2b3b53;border-radius:12px;padding:4px 10px;font-size:11px;")
        if state in ("paused", "waiting", "listening", "testing"):
            self.listening = state != "paused"
            self.mic_button.setText("توقف شنیدن" if self.listening else "شروع شنیدن")
            if not self.listening:
                self.meter.set_level(0)
                self.level_label.setText("میکروفون خاموش" if self.voice_available else "تشخیص گفتار در دسترس نیست")
            else:
                self.level_label.setText("ورودی زنده")
        idle = state in ("paused", "waiting", "listening") and self.ready and not self.closing
        for button in self.quick_buttons:
            button.setEnabled(idle)
        self.send_button.setEnabled(idle)
        self.entry.setEnabled(idle)
        self.edit_heard_button.setEnabled(idle)
        voice_idle = idle and self.voice_available
        can_stop = self.voice_available and self.ready and self.listening and not self.closing
        self.mic_button.setEnabled(voice_idle or can_stop)
        self.settings_button.setEnabled(voice_idle)
        self.wake_button.setEnabled(voice_idle)

    def add_message(self, role, text):
        bubble = QFrame()
        user = role == "user"
        system = role == "system"
        color = "#213659" if user else "#151e2d" if not system else "#29221f"
        border = "#3b5785" if user else "#2b3b54" if not system else "#5b4638"
        bubble.setStyleSheet(f"QFrame {{ background: {color}; border: 1px solid {border}; border-radius: 16px; }} QLabel {{ border:0; background:transparent; }}")
        box = QVBoxLayout(bubble)
        box.setContentsMargins(15, 12, 15, 16)
        box.setSpacing(8)
        top = QHBoxLayout()
        stamp = label(datetime.now().strftime("%H:%M"), "muted")
        stamp.setStyleSheet("color:#899bb9;font-family:Manrope;font-size:10px;")
        top.addWidget(stamp)
        top.addStretch()
        title = label("شما" if user else "اطلاع‌رسانی" if system else "JARVIS")
        title.setStyleSheet("color:#c5d6f6;font-size:11px;font-weight:600;")
        top.addWidget(title)
        box.addLayout(top)
        content = label(text, align=Qt.AlignmentFlag.AlignRight)
        content.setWordWrap(True)
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.setStyleSheet("font-size:14px;color:#e1eafb;")
        box.addWidget(content)
        self.chat_layout.addWidget(bubble)
        self.messages.append(bubble)
        if len(self.messages) > 80:
            self.chat_layout.removeWidget(self.messages[0])
            self.messages.pop(0).deleteLater()
        QTimer.singleShot(20, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def on_event(self, kind, data):
        if kind == "ready":
            self.ready = True
            self.voice_available = data["voice_available"]
            self.command_groups = data["command_groups"]
            if self.voice_available:
                self.partial.setText("میکروفون را روشن کن؛ یا همین‌جا یک فرمان بنویس.")
            else:
                self.partial.setText("تشخیص گفتار در دسترس نیست. همین‌جا یک فرمان بنویس.")
                self.engine_label.setText("●  ورودی تایپی")
            QTimer.singleShot(0, self.entry.setFocus)
        elif kind == "state" and not self.closing:
            self.set_state(data["value"])
        elif kind == "transcript":
            self.conversation_intro.hide()
            self.offer_correction("")
            self.add_message("user", data["text"])
            self.partial.setText(data["text"])
        elif kind == "response":
            self.add_message("assistant", data["text"])
        elif kind in ("error", "notice"):
            self.add_message("system", data["text"])
            if data.get("fatal"):
                self.ready = False
                self.set_state("error")
                self.partial.setText("برنامه را ببند و تنظیمات یا مدل فارسی را بررسی کن.")
        elif kind == "partial" and data["text"]:
            self.partial.setText(data["text"])
        elif kind == "audio_level":
            self.meter.set_level(data["level"], data["clipping"])
            self.visual.level = max(self.visual.level, data["level"])
            self.level_label.setText("ورودی بیش از حد بلند" if data["clipping"] else "ورودی زنده")
            if self.sound_dialog is not None:
                self.sound_dialog.meter.set_level(data["level"], data["clipping"])
        elif kind == "uncertain":
            text = data["text"]
            if self.sound_dialog is not None and self.sound_dialog.testing:
                self.sound_dialog.test_text.setText(f"با اطمینان کم شنیدم: «{text}»")
            else:
                self.partial.setText(f"با اطمینان کم شنیدم: «{text}»")
                self.offer_correction(text)
        elif kind == "unrecognized":
            self.partial.setText("فرمان قابل اجرا پیدا نکردم. متن را دقیق‌تر کن یا نمونه‌های «فرمان‌ها» را ببین.")
            if data["voice"]:
                self.offer_correction(data["text"])
        elif kind == "confidence":
            self.confidence_label.setText(f'اطمینان {round(data["value"] * 100)}٪')
        elif kind == "recognition_mode":
            self.engine_label.setText("●  تشخیص محلی · گفتار آزاد و فرمان‌ها" if data["constrained"] else "●  تشخیص محلی · گفتار آزاد")
        elif kind == "mode":
            self.mode_badge.setText("گفت‌وگوی هوشمند" if data["value"] == "AI" else "فرمان‌های فارسی")
        elif kind == "command":
            if data["name"] not in ("say_time", "say_date"):
                progress = f'مرحلهٔ {data["index"]} از {data["total"]} · ' if data.get("total", 1) > 1 else ""
                self.partial.setText(progress + data["phrase"])
        elif kind == "planning":
            self.partial.setText("مدل محلی در حال آماده‌کردن مراحل است…")
        elif kind == "test_transcript" and self.sound_dialog is not None:
            self.sound_dialog.test_text.setText("شنیدم: " + data["text"])
        elif kind == "settings_saved":
            self.audio_settings = dict(data)
        elif kind == "closed":
            if not self.closing and self.ready:
                self.closing = True
                self.close()

    def show_sound(self):
        if not self.ready or not self.voice_available:
            return
        self.sound_dialog = SoundDialog(self)
        self.sound_dialog.exec()
        self.sound_dialog.deleteLater()
        self.sound_dialog = None

    def show_commands(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("فرمان‌های جارویس")
        dialog.resize(620, 600)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.addWidget(label("فرمان‌ها و نمونه‌های تسک", "section", Qt.AlignmentFlag.AlignRight))
        hint = label("برای اجرا، روی یک فرمان کلیک کن. فرمان‌های حساس تأیید جدا می‌خواهند.", "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        search = QLineEdit()
        search.setPlaceholderText("جست‌وجوی فرمان…")
        search.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        rows = QVBoxLayout(content)
        items = []
        for phrases in self.command_groups:
            button = QPushButton(phrases[0])
            button.setObjectName("quick")
            button.setAutoDefault(False)
            button.setEnabled(self.ready and self.state in ("paused", "waiting", "listening"))
            button.clicked.connect(lambda checked=False, row=button: (dialog.accept(), self.submit_text(row.text())))
            rows.addWidget(button)
            items.append(([(phrase, normalize_text(phrase)) for phrase in phrases], button))
        empty = label("فرمانی با این عبارت پیدا نشد.", "muted", Qt.AlignmentFlag.AlignRight)
        rows.addWidget(empty)
        rows.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        def filter_commands(value):
            query = normalize_text(value)
            found = False
            for phrases, button in items:
                match = next((phrase for phrase, normalized in phrases if query in normalized), None)
                button.setVisible(match is not None)
                if match is not None:
                    button.setText(match)
                    found = True
            empty.setVisible(not found)
            scroll.verticalScrollBar().setValue(0)

        search.textChanged.connect(filter_commands)
        filter_commands("")
        close = QPushButton("بستن")
        close.setAutoDefault(False)
        close.clicked.connect(dialog.reject)
        layout.addWidget(close)
        search.setFocus()
        dialog.exec()
        dialog.deleteLater()

    def closeEvent(self, event):
        self.closing = True
        self.service.shutdown()
        if self.service.is_alive():
            event.ignore()
            self.set_state("closing")
            self.mic_button.setEnabled(False)
            QTimer.singleShot(100, self.close)
        else:
            set_event_handler(None)
            tts.set_muted(False)
            self.visual.timer.stop()
            event.accept()


def create_application():
    if sys.platform == "win32":
        # comtypes registers main-thread cleanup at import time. Import it here
        # so the audio worker can balance its own COM initialization separately.
        import comtypes  # noqa: F401
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("NEXORA JARVIS")
    app.setOrganizationName("NEXORA")
    for filename in ("Manrope-Variable.ttf", "Vazirmatn-Variable.ttf"):
        QFontDatabase.addApplicationFont(str(ASSETS / filename))
    app.setFont(QFont("Vazirmatn", 10))
    app.setStyleSheet(STYLES)
    return app


def launch_gui():
    app = create_application()
    window = JarvisWindow()
    window.show()
    return app.exec()
