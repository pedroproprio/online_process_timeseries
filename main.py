from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from ui.ConfigWindow import ConfigWindow

from sys import argv, path
import logging
import os

import qdarktheme

cur_dir = os.path.dirname(os.path.abspath(__file__))

sdk_path = os.path.join(cur_dir, "sdk")
path.append(sdk_path)

os.environ['FTSLIB_PATH'] = os.path.join(cur_dir, "sdk", "FTSLib", "FTSLib.dll")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    app = QApplication(argv)
    app.setStyleSheet(qdarktheme.load_stylesheet())
    
    window = ConfigWindow()
    icon = os.path.join(cur_dir, "img", "litel.png")
    window.setWindowIcon(QIcon(icon))
    window.show()
    
    app.exec()