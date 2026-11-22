"""Vector artwork for the NEXORA desktop interface."""
import math

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QLinearGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QWidget, QSizePolicy


class ScenePanel(QFrame):
    def __init__(self, assets):
        super().__init__()
        self.horizon = QPixmap(str(assets / "horizon.webp"))
        self.setObjectName("workspace")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 26, 26)
        painter.setClipPath(shape)
        painter.fillRect(self.rect(), QColor("#0c1019"))
        if not self.horizon.isNull():
            image = self.horizon.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
            painter.setOpacity(.13)
            painter.drawPixmap((self.width() - image.width()) // 2, (self.height() - image.height()) // 2, image)
            painter.setOpacity(1)
        glow = QRadialGradient(QPointF(self.width() * .5, self.height() * .40), self.width() * .7)
        glow.setColorAt(0, QColor(49, 80, 160, 36))
        glow.setColorAt(.65, QColor(10, 14, 23, 120))
        glow.setColorAt(1, QColor(10, 13, 20, 235))
        painter.fillRect(self.rect(), glow)
        fade = QLinearGradient(0, self.height() * .55, 0, self.height())
        fade.setColorAt(0, QColor(10, 14, 22, 0))
        fade.setColorAt(1, QColor("#0c1018"))
        painter.fillRect(self.rect(), fade)
        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#242d40"), 1))
        painter.drawPath(shape)


class CoreVisual(QWidget):
    """A silver, rotating filament sphere driven by the actual audio level."""
    def __init__(self, assets):
        super().__init__()
        self.renderer = QSvgRenderer(str(assets / "mark.svg"))
        self.phase = 0.0
        self.level = 0.0
        self.active = False
        self.state = "loading"
        self.setMinimumHeight(135)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)

    def tick(self):
        interval = 40 if self.active else 90
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        if self.isVisible() and not self.window().isMinimized():
            self.phase += .018 if self.active else .004
            self.level *= .90
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * .5, h * .46
        radius = min(w * .27, h * .43, 162) * (1 + self.level * .035)
        center = QPointF(cx, cy)
        accent = QColor("#7a9eff" if self.active else "#9aafd8")
        halo = QRadialGradient(center, radius * 1.75)
        halo.setColorAt(0, QColor(79, 112, 210, 42 + int(self.level * 40)))
        halo.setColorAt(.50, QColor(57, 90, 184, 20))
        halo.setColorAt(1, QColor(45, 72, 150, 0))
        painter.fillRect(self.rect(), halo)
        # Tiny, deterministic points add depth without an image or a busy HUD.
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(22):
            x = (index * 137.71 + 29) % max(1, w)
            y = (index * 83.29 + 17) % max(1, h)
            if math.hypot(x - cx, y - cy) > radius * 1.35:
                painter.setBrush(QColor(161, 184, 232, 25 + index % 4 * 12))
                painter.drawEllipse(QPointF(x, y), .8, .8)
        # A soft, grounded reflection under the sphere.
        painter.save()
        painter.translate(cx, cy + radius * 1.12)
        painter.scale(1, .11)
        reflection = QRadialGradient(QPointF(), radius)
        reflection.setColorAt(0, QColor(92, 125, 231, 80 if self.active else 42))
        reflection.setColorAt(1, QColor(70, 100, 210, 0))
        painter.setBrush(reflection)
        painter.drawEllipse(QPointF(), radius, radius)
        painter.restore()
        sphere = QRadialGradient(QPointF(cx - radius * .35, cy - radius * .45), radius * 1.7)
        sphere.setColorAt(0, QColor(112, 135, 181, 100))
        sphere.setColorAt(.35, QColor(32, 49, 83, 150))
        sphere.setColorAt(.74, QColor(13, 23, 44, 215))
        sphere.setColorAt(1, QColor(7, 12, 25, 230))
        painter.setBrush(sphere)
        painter.setPen(QPen(QColor(130, 158, 213, 75), 1))
        painter.drawEllipse(center, radius, radius)
        # Project twisted circles onto the sphere. Bright front-facing filaments
        # and dim back-facing filaments give the mark a sculptural surround.
        tilt = .42 + math.sin(self.phase * .4) * .12
        for band in range(18):
            latitude = -1.36 + band * 2.72 / 17
            path = QPainterPath()
            for step in range(81):
                phi = step * math.tau / 80
                twist = self.phase * .35 + latitude * 1.2
                x = math.cos(latitude) * math.cos(phi + twist)
                y = math.sin(latitude)
                z = math.cos(latitude) * math.sin(phi + twist)
                yy = y * math.cos(tilt) - z * math.sin(tilt)
                xx = x * math.cos(-.45) - yy * math.sin(-.45)
                yy = x * math.sin(-.45) + yy * math.cos(-.45)
                point = QPointF(cx + xx * radius, cy + yy * radius)
                if step == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            alpha = 45 + int(75 * (1 - abs(latitude) / 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(163, 189, 244, alpha), .85))
            painter.drawPath(path)
        # An oblique orbit references the NEXORA site's planetary identity.
        painter.save()
        painter.translate(center)
        painter.rotate(-26)
        ellipse = QRectF(-radius * 1.32, -radius * .31, radius * 2.64, radius * .62)
        painter.setPen(QPen(QColor(150, 176, 227, 56), .9))
        painter.drawEllipse(ellipse)
        angle = self.phase * .65
        particle = QPointF(math.cos(angle) * radius * 1.32, math.sin(angle) * radius * .31)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(particle, 2.5, 2.5)
        painter.restore()
        # The central vignette keeps the original silver mark legible.
        vignette = QRadialGradient(center, radius * .82)
        vignette.setColorAt(0, QColor(10, 17, 30, 240))
        vignette.setColorAt(.48, QColor(13, 22, 38, 225))
        vignette.setColorAt(1, QColor(12, 20, 35, 0))
        painter.setBrush(vignette)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius * .82, radius * .82)
        mark_width = radius * .90
        self.renderer.render(painter, QRectF(cx - mark_width / 2, cy - mark_width * .84375 / 2,
                                             mark_width, mark_width * .84375))
