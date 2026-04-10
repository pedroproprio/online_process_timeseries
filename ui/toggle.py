from PySide6.QtWidgets import QCheckBox, QLayout
from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QPainter, QColor

class ToggleSwitch(QCheckBox):
    def __init__(self, parent: QLayout, width=40, height=20, accent_color='#0078d4'):
        super().__init__()

        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)

        self._width = width
        self._height = height
        self._accent_color = QColor(accent_color)

        parent.addWidget(self)

    def paintEvent(self, e):
        p = QPainter(self)

        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        rect = QRect(0, 0, self._width, self._height)
        p.setBrush(QColor(255, 255, 255, 20) if not self.isChecked() else self._accent_color)
        p.drawRoundedRect(0, 0, rect.width(), self._height, self._height / 2, self._height / 2)

        p.setBrush(QColor(255, 255, 255) if self.isEnabled() else QColor(255, 255, 255, 128))
        p.drawEllipse((0 if not self.isChecked() else self._width - self._height), 0, self._height, self._height)

        p.end()


    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout

    app = QApplication([])
    window = QWidget()
    layout = QHBoxLayout(window)

    toggle = ToggleSwitch(layout)

    window.show()
    app.exec()