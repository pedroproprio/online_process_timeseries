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
from PySide6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox, QHBoxLayout,
    QLabel, QLayout, QLineEdit, QMainWindow,
    QPushButton, QSizePolicy, QSpacerItem, QSpinBox,
    QVBoxLayout, QWidget)

class Ui_ConfigWindow(object):
    def setupUi(self, ConfigWindow):
        if not ConfigWindow.objectName():
            ConfigWindow.setObjectName(u"ConfigWindow")
        ConfigWindow.setWindowModality(Qt.WindowModality.NonModal)
        ConfigWindow.resize(501, 252)
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
        self.inter_lbl = QLabel(self.centralwidget)
        self.inter_lbl.setObjectName(u"inter_lbl")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.inter_lbl.sizePolicy().hasHeightForWidth())
        self.inter_lbl.setSizePolicy(sizePolicy1)
        self.inter_lbl.setTextFormat(Qt.TextFormat.PlainText)

        self.labels_vlay.addWidget(self.inter_lbl)

        self.range_lbl = QLabel(self.centralwidget)
        self.range_lbl.setObjectName(u"range_lbl")
        sizePolicy1.setHeightForWidth(self.range_lbl.sizePolicy().hasHeightForWidth())
        self.range_lbl.setSizePolicy(sizePolicy1)
        self.range_lbl.setTextFormat(Qt.TextFormat.PlainText)

        self.labels_vlay.addWidget(self.range_lbl)

        self.res_lbl = QLabel(self.centralwidget)
        self.res_lbl.setObjectName(u"res_lbl")
        sizePolicy1.setHeightForWidth(self.res_lbl.sizePolicy().hasHeightForWidth())
        self.res_lbl.setSizePolicy(sizePolicy1)
        self.res_lbl.setTextFormat(Qt.TextFormat.PlainText)

        self.labels_vlay.addWidget(self.res_lbl)

        self.ip_lbl = QLabel(self.centralwidget)
        self.ip_lbl.setObjectName(u"ip_lbl")
        self.ip_lbl.setEnabled(False)
        sizePolicy1.setHeightForWidth(self.ip_lbl.sizePolicy().hasHeightForWidth())
        self.ip_lbl.setSizePolicy(sizePolicy1)

        self.labels_vlay.addWidget(self.ip_lbl)

        self.com_lbl = QLabel(self.centralwidget)
        self.com_lbl.setObjectName(u"com_lbl")
        sizePolicy1.setHeightForWidth(self.com_lbl.sizePolicy().hasHeightForWidth())
        self.com_lbl.setSizePolicy(sizePolicy1)
        self.com_lbl.setTextFormat(Qt.TextFormat.PlainText)

        self.labels_vlay.addWidget(self.com_lbl)


        self.main_hlay.addLayout(self.labels_vlay)

        self.combos_vlay = QVBoxLayout()
        self.combos_vlay.setObjectName(u"combos_vlay")
        self.inter_combo = QComboBox(self.centralwidget)
        self.inter_combo.setObjectName(u"inter_combo")
        sizePolicy1.setHeightForWidth(self.inter_combo.sizePolicy().hasHeightForWidth())
        self.inter_combo.setSizePolicy(sizePolicy1)
        self.inter_combo.setMaxVisibleItems(6)

        self.combos_vlay.addWidget(self.inter_combo)

        self.com_hlay = QHBoxLayout()
        self.com_hlay.setObjectName(u"com_hlay")
        self.minNm_spin = QSpinBox(self.centralwidget)
        self.minNm_spin.setObjectName(u"minNm_spin")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.minNm_spin.sizePolicy().hasHeightForWidth())
        self.minNm_spin.setSizePolicy(sizePolicy2)
        self.minNm_spin.setSingleStep(50)

        self.com_hlay.addWidget(self.minNm_spin)

        self.label_5 = QLabel(self.centralwidget)
        self.label_5.setObjectName(u"label_5")
        sizePolicy.setHeightForWidth(self.label_5.sizePolicy().hasHeightForWidth())
        self.label_5.setSizePolicy(sizePolicy)
        self.label_5.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignTrailing|Qt.AlignmentFlag.AlignVCenter)

        self.com_hlay.addWidget(self.label_5)

        self.maxNm_spin = QSpinBox(self.centralwidget)
        self.maxNm_spin.setObjectName(u"maxNm_spin")
        sizePolicy2.setHeightForWidth(self.maxNm_spin.sizePolicy().hasHeightForWidth())
        self.maxNm_spin.setSizePolicy(sizePolicy2)
        self.maxNm_spin.setSingleStep(50)

        self.com_hlay.addWidget(self.maxNm_spin)

        self.label_6 = QLabel(self.centralwidget)
        self.label_6.setObjectName(u"label_6")

        self.com_hlay.addWidget(self.label_6)


        self.combos_vlay.addLayout(self.com_hlay)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.resPm_spin = QDoubleSpinBox(self.centralwidget)
        self.resPm_spin.setObjectName(u"resPm_spin")
        self.resPm_spin.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
        self.resPm_spin.setDecimals(1)
        self.resPm_spin.setMinimum(1.000000000000000)
        self.resPm_spin.setSingleStep(0.100000000000000)
        self.resPm_spin.setValue(100.000000000000000)

        self.horizontalLayout.addWidget(self.resPm_spin)

        self.label_7 = QLabel(self.centralwidget)
        self.label_7.setObjectName(u"label_7")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.label_7.sizePolicy().hasHeightForWidth())
        self.label_7.setSizePolicy(sizePolicy3)

        self.horizontalLayout.addWidget(self.label_7)


        self.combos_vlay.addLayout(self.horizontalLayout)

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

        self.port_combo = QComboBox(self.centralwidget)
        self.port_combo.setObjectName(u"port_combo")
        self.port_combo.setEnabled(False)
        sizePolicy1.setHeightForWidth(self.port_combo.sizePolicy().hasHeightForWidth())
        self.port_combo.setSizePolicy(sizePolicy1)

        self.combos_vlay.addWidget(self.port_combo)


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

        self.start_btn = QPushButton(self.centralwidget)
        self.start_btn.setObjectName(u"start_btn")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.start_btn.sizePolicy().hasHeightForWidth())
        self.start_btn.setSizePolicy(sizePolicy4)

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
        self.inter_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Interrogador:", None))
        self.range_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Intervalo do comprimento de onda:", None))
        self.res_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Resolu\u00e7\u00e3o do comprimento de onda:", None))
        self.ip_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Endere\u00e7o IP:", None))
        self.com_lbl.setText(QCoreApplication.translate("ConfigWindow", u"Porta:", None))
        self.inter_combo.setCurrentText("")
        self.label_5.setText(QCoreApplication.translate("ConfigWindow", u"-", None))
        self.label_6.setText(QCoreApplication.translate("ConfigWindow", u"nm", None))
        self.label_7.setText(QCoreApplication.translate("ConfigWindow", u"pm", None))
        self.ip_lineEdit.setText(QCoreApplication.translate("ConfigWindow", u"10.0.0.10", None))
        self.file_path_lbl.setText("")
        self.start_btn.setText(QCoreApplication.translate("ConfigWindow", u"Iniciar an\u00e1lise", None))
    # retranslateUi

