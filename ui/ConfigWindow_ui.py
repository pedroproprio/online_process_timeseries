# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ConfigWindow.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
    QLayout, QLineEdit, QMainWindow, QPushButton,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

class Ui_ConfigWindow(object):
    def setupUi(self, ConfigWindow):
        if not ConfigWindow.objectName():
            ConfigWindow.setObjectName(u"ConfigWindow")
        ConfigWindow.setWindowModality(Qt.WindowModality.NonModal)
        ConfigWindow.resize(501, 228)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(ConfigWindow.sizePolicy().hasHeightForWidth())
        ConfigWindow.setSizePolicy(sizePolicy)
        ConfigWindow.setMinimumSize(QSize(0, 0))
        ConfigWindow.setMaximumSize(QSize(16777215, 16777215))
        icon = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.DocumentProperties))
        ConfigWindow.setWindowIcon(icon)
        ConfigWindow.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.centralwidget = QWidget(ConfigWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.centralwidget.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.centralwidget.setAcceptDrops(False)
        self.centralwidget.setAutoFillBackground(False)
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.main_hlay = QHBoxLayout()
        self.main_hlay.setObjectName(u"main_hlay")
        self.labels_vlay = QVBoxLayout()
        self.labels_vlay.setObjectName(u"labels_vlay")
        self.wave_lbl = QLabel(self.centralwidget)
        self.wave_lbl.setObjectName(u"wave_lbl")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.wave_lbl.sizePolicy().hasHeightForWidth())
        self.wave_lbl.setSizePolicy(sizePolicy1)
        self.wave_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.wave_lbl.setAlignment(Qt.AlignmentFlag.AlignLeading|Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

        self.labels_vlay.addWidget(self.wave_lbl)

        self.inter_lbl = QLabel(self.centralwidget)
        self.inter_lbl.setObjectName(u"inter_lbl")
        sizePolicy1.setHeightForWidth(self.inter_lbl.sizePolicy().hasHeightForWidth())
        self.inter_lbl.setSizePolicy(sizePolicy1)
        self.inter_lbl.setTextFormat(Qt.TextFormat.PlainText)

        self.labels_vlay.addWidget(self.inter_lbl)

        self.com_lbl = QLabel(self.centralwidget)
        self.com_lbl.setObjectName(u"com_lbl")
        sizePolicy1.setHeightForWidth(self.com_lbl.sizePolicy().hasHeightForWidth())
        self.com_lbl.setSizePolicy(sizePolicy1)
        self.com_lbl.setTextFormat(Qt.TextFormat.PlainText)

        self.labels_vlay.addWidget(self.com_lbl)

        self.ip_lbl = QLabel(self.centralwidget)
        self.ip_lbl.setObjectName(u"ip_lbl")
        self.ip_lbl.setEnabled(False)
        sizePolicy1.setHeightForWidth(self.ip_lbl.sizePolicy().hasHeightForWidth())
        self.ip_lbl.setSizePolicy(sizePolicy1)

        self.labels_vlay.addWidget(self.ip_lbl)


        self.main_hlay.addLayout(self.labels_vlay)

        self.combos_vlay = QVBoxLayout()
        self.combos_vlay.setObjectName(u"combos_vlay")
        self.unit_combo = QComboBox(self.centralwidget)
        self.unit_combo.setObjectName(u"unit_combo")
        sizePolicy1.setHeightForWidth(self.unit_combo.sizePolicy().hasHeightForWidth())
        self.unit_combo.setSizePolicy(sizePolicy1)
        self.unit_combo.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.combos_vlay.addWidget(self.unit_combo)

        self.inter_combo = QComboBox(self.centralwidget)
        self.inter_combo.setObjectName(u"inter_combo")
        sizePolicy1.setHeightForWidth(self.inter_combo.sizePolicy().hasHeightForWidth())
        self.inter_combo.setSizePolicy(sizePolicy1)
        self.inter_combo.setMaxVisibleItems(6)

        self.combos_vlay.addWidget(self.inter_combo)

        self.com_hlay = QHBoxLayout()
        self.com_hlay.setObjectName(u"com_hlay")
        self.port_combo = QComboBox(self.centralwidget)
        self.port_combo.setObjectName(u"port_combo")
        self.port_combo.setEnabled(False)
        sizePolicy1.setHeightForWidth(self.port_combo.sizePolicy().hasHeightForWidth())
        self.port_combo.setSizePolicy(sizePolicy1)

        self.com_hlay.addWidget(self.port_combo)

        self.refresh_btn = QPushButton(self.centralwidget)
        self.refresh_btn.setObjectName(u"refresh_btn")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.refresh_btn.sizePolicy().hasHeightForWidth())
        self.refresh_btn.setSizePolicy(sizePolicy2)
        self.refresh_btn.setMinimumSize(QSize(0, 0))
        icon1 = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.SyncSynchronizing))
        self.refresh_btn.setIcon(icon1)

        self.com_hlay.addWidget(self.refresh_btn)


        self.combos_vlay.addLayout(self.com_hlay)

        self.ip_lineEdit = QLineEdit(self.centralwidget)
        self.ip_lineEdit.setObjectName(u"ip_lineEdit")
        self.ip_lineEdit.setEnabled(False)
        sizePolicy1.setHeightForWidth(self.ip_lineEdit.sizePolicy().hasHeightForWidth())
        self.ip_lineEdit.setSizePolicy(sizePolicy1)
        self.ip_lineEdit.setMaxLength(15)
        self.ip_lineEdit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.ip_lineEdit.setCursorMoveStyle(Qt.CursorMoveStyle.LogicalMoveStyle)
        self.ip_lineEdit.setClearButtonEnabled(False)

        self.combos_vlay.addWidget(self.ip_lineEdit)


        self.main_hlay.addLayout(self.combos_vlay)


        self.verticalLayout.addLayout(self.main_hlay)

        self.file_path_lbl = QLabel(self.centralwidget)
        self.file_path_lbl.setObjectName(u"file_path_lbl")
        self.file_path_lbl.setEnabled(False)
        font = QFont()
        font.setPointSize(8)
        self.file_path_lbl.setFont(font)

        self.verticalLayout.addWidget(self.file_path_lbl)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.iniciar_hlay = QHBoxLayout()
        self.iniciar_hlay.setSpacing(10)
        self.iniciar_hlay.setObjectName(u"iniciar_hlay")
        self.iniciar_hlay.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.iniciar_hlay.setContentsMargins(-1, 30, -1, 5)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.iniciar_hlay.addItem(self.horizontalSpacer)

        self.load_btn = QPushButton(self.centralwidget)
        self.load_btn.setObjectName(u"load_btn")

        self.iniciar_hlay.addWidget(self.load_btn)

        self.start_btn = QPushButton(self.centralwidget)
        self.start_btn.setObjectName(u"start_btn")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.start_btn.sizePolicy().hasHeightForWidth())
        self.start_btn.setSizePolicy(sizePolicy3)

        self.iniciar_hlay.addWidget(self.start_btn)


        self.verticalLayout.addLayout(self.iniciar_hlay)

        ConfigWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(ConfigWindow)

        self.inter_combo.setCurrentIndex(-1)
        self.port_combo.setCurrentIndex(-1)


        QMetaObject.connectSlotsByName(ConfigWindow)
    # setupUi

    def retranslateUi(self, ConfigWindow):
        ConfigWindow.setWindowTitle(QCoreApplication.translate("ConfigWindow", u"Configura\u00e7\u00e3o inicial", None))
        self.wave_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Unidade do comprimento de onda:", None))
        self.inter_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Interrogador:", None))
        self.com_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Porta:", None))
        self.ip_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Endere\u00e7o IP:", None))
        self.inter_combo.setCurrentText("")
        self.refresh_btn.setText("")
        self.ip_lineEdit.setText(QCoreApplication.translate("ConfigWindow", u"10.0.0.10", None))
        self.file_path_lbl.setText("")
        self.load_btn.setText(QCoreApplication.translate("ConfigWindow", u"Carregar arquivo", None))
        self.start_btn.setText(QCoreApplication.translate("ConfigWindow", u"Iniciar an\u00e1lise", None))
    # retranslateUi

