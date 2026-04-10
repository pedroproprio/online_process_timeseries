from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from ui.ConfigWindow import ConfigWindow

from sys import argv, path
import os

import qdarktheme

cur_dir = os.path.dirname(os.path.abspath(__file__))

pyosa_path = os.path.join(cur_dir, "sdk")
path.append(pyosa_path)

os.environ['FTSLIB_PATH'] = os.path.join(cur_dir, "sdk", "FTSLib", "FTSLib.dll")

if __name__ == "__main__":
    app = QApplication(argv)
    app.setStyleSheet(qdarktheme.load_stylesheet())
    
    window = ConfigWindow()
    icon = os.path.join(cur_dir, "img", "logo.png")
    window.setWindowIcon(QIcon(icon))
    window.show()
    
    app.exec()