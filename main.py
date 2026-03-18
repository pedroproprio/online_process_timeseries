from PySide6.QtWidgets import QApplication
from ConfigWindow import ConfigWindow
from sys import argv

if __name__ == "__main__":
    app = QApplication(argv)

    window = ConfigWindow()
    window.show()
    
    app.exec()