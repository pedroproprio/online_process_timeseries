# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'AnalysisWindow.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QDoubleSpinBox, QHBoxLayout,
    QLabel, QLayout, QMainWindow, QPushButton,
    QSizePolicy, QSpacerItem, QSpinBox, QStatusBar,
    QVBoxLayout, QWidget)

from pyqtgraph import (GraphicsLayoutWidget, PlotWidget)

class Ui_AnalysisWindow(object):
    def setupUi(self, AnalysisWindow):
        if not AnalysisWindow.objectName():
            AnalysisWindow.setObjectName(u"AnalysisWindow")
        AnalysisWindow.resize(1425, 941)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(AnalysisWindow.sizePolicy().hasHeightForWidth())
        AnalysisWindow.setSizePolicy(sizePolicy)
        icon = QIcon(QIcon.fromTheme(QIcon.ThemeIcon.EditFind))
        AnalysisWindow.setWindowIcon(icon)
        AnalysisWindow.setAutoFillBackground(True)
        self.centralwidget = QWidget(AnalysisWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.centralwidget.setAutoFillBackground(True)
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.spectraPlotWidget = PlotWidget(self.centralwidget)
        self.spectraPlotWidget.setObjectName(u"spectraPlotWidget")
        sizePolicy.setHeightForWidth(self.spectraPlotWidget.sizePolicy().hasHeightForWidth())
        self.spectraPlotWidget.setSizePolicy(sizePolicy)

        self.verticalLayout.addWidget(self.spectraPlotWidget)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.temporalPlotWidget = PlotWidget(self.centralwidget)
        self.temporalPlotWidget.setObjectName(u"temporalPlotWidget")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.temporalPlotWidget.sizePolicy().hasHeightForWidth())
        self.temporalPlotWidget.setSizePolicy(sizePolicy1)
        self.temporalPlotWidget.setAutoFillBackground(True)

        self.horizontalLayout.addWidget(self.temporalPlotWidget)

        self.boxPlotWidget = GraphicsLayoutWidget(self.centralwidget)
        self.boxPlotWidget.setObjectName(u"boxPlotWidget")
        sizePolicy1.setHeightForWidth(self.boxPlotWidget.sizePolicy().hasHeightForWidth())
        self.boxPlotWidget.setSizePolicy(sizePolicy1)
        self.boxPlotWidget.setAutoFillBackground(True)

        self.horizontalLayout.addWidget(self.boxPlotWidget)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.buttons_hlay = QHBoxLayout()
        self.buttons_hlay.setSpacing(5)
        self.buttons_hlay.setObjectName(u"buttons_hlay")
        self.buttons_hlay.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.buttons_hlay.setContentsMargins(10, 10, 10, -1)
        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.sr_lbl = QLabel(self.centralwidget)
        self.sr_lbl.setObjectName(u"sr_lbl")
        self.sr_lbl.setEnabled(False)

        self.verticalLayout_3.addWidget(self.sr_lbl)

        self.sr_spin = QSpinBox(self.centralwidget)
        self.sr_spin.setObjectName(u"sr_spin")
        self.sr_spin.setEnabled(False)
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.sr_spin.sizePolicy().hasHeightForWidth())
        self.sr_spin.setSizePolicy(sizePolicy2)
        self.sr_spin.setMinimum(100)
        self.sr_spin.setMaximum(5000)
        self.sr_spin.setValue(800)

        self.verticalLayout_3.addWidget(self.sr_spin)


        self.buttons_hlay.addLayout(self.verticalLayout_3)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)

        self.buttons_hlay.addItem(self.horizontalSpacer_2)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.cfg_lbl = QLabel(self.centralwidget)
        self.cfg_lbl.setObjectName(u"cfg_lbl")
        self.cfg_lbl.setEnabled(False)

        self.verticalLayout_2.addWidget(self.cfg_lbl)

        self.cfg_spin = QDoubleSpinBox(self.centralwidget)
        self.cfg_spin.setObjectName(u"cfg_spin")
        self.cfg_spin.setEnabled(False)
        sizePolicy2.setHeightForWidth(self.cfg_spin.sizePolicy().hasHeightForWidth())
        self.cfg_spin.setSizePolicy(sizePolicy2)
        self.cfg_spin.setDecimals(0)

        self.verticalLayout_2.addWidget(self.cfg_spin)


        self.buttons_hlay.addLayout(self.verticalLayout_2)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.buttons_hlay.addItem(self.horizontalSpacer_3)

        self.continuous_chk = QCheckBox(self.centralwidget)
        self.continuous_chk.setObjectName(u"continuous_chk")
        self.continuous_chk.setEnabled(False)

        self.buttons_hlay.addWidget(self.continuous_chk)

        self.save_btn = QPushButton(self.centralwidget)
        self.save_btn.setObjectName(u"save_btn")
        self.save_btn.setEnabled(False)
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.save_btn.sizePolicy().hasHeightForWidth())
        self.save_btn.setSizePolicy(sizePolicy3)

        self.buttons_hlay.addWidget(self.save_btn)

        self.clear_btn = QPushButton(self.centralwidget)
        self.clear_btn.setObjectName(u"clear_btn")

        self.buttons_hlay.addWidget(self.clear_btn)

        self.stop_btn = QPushButton(self.centralwidget)
        self.stop_btn.setObjectName(u"stop_btn")
        sizePolicy3.setHeightForWidth(self.stop_btn.sizePolicy().hasHeightForWidth())
        self.stop_btn.setSizePolicy(sizePolicy3)

        self.buttons_hlay.addWidget(self.stop_btn)


        self.verticalLayout.addLayout(self.buttons_hlay)

        AnalysisWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(AnalysisWindow)
        self.statusbar.setObjectName(u"statusbar")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.statusbar.sizePolicy().hasHeightForWidth())
        self.statusbar.setSizePolicy(sizePolicy4)
        AnalysisWindow.setStatusBar(self.statusbar)

        self.retranslateUi(AnalysisWindow)

        QMetaObject.connectSlotsByName(AnalysisWindow)
    # setupUi

    def retranslateUi(self, AnalysisWindow):
        AnalysisWindow.setWindowTitle(QCoreApplication.translate("AnalysisWindow", u"An\u00e1lise de dados", None))
        self.sr_lbl.setText(QCoreApplication.translate("AnalysisWindow", u"Intervalo entre amostras [ms]", None))
        self.cfg_lbl.setText(QCoreApplication.translate("AnalysisWindow", u"Tempo de exposi\u00e7\u00e3o [\u00b5s]", None))
        self.continuous_chk.setText(QCoreApplication.translate("AnalysisWindow", u" Modo cont\u00ednuo", None))
        self.save_btn.setText(QCoreApplication.translate("AnalysisWindow", u"Confirmar Regi\u00e3o e Salvar", None))
        self.clear_btn.setText(QCoreApplication.translate("AnalysisWindow", u"Limpar", None))
        self.stop_btn.setText(QCoreApplication.translate("AnalysisWindow", u"Parar", None))
    # retranslateUi

