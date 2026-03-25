from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from ConfigWindow import ConfigWindow

from sys import argv
import os

from lib.PyQtDarkTheme import qdarktheme

if __name__ == "__main__":
    app = QApplication(argv)
    app.setStyleSheet(qdarktheme.load_stylesheet())

    window = ConfigWindow()
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    icon = os.path.join(cur_dir, "img", "logo.png")
    window.setWindowIcon(QIcon(icon))
    window.show()
    
    app.exec()