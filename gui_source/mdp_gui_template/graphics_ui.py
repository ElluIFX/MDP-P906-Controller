# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'graphics.ui'
##
## Created by: Qt User Interface Compiler version 6.5.3
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSpinBox, QVBoxLayout,
    QWidget)

class Ui_DialogGraphics(object):
    def setupUi(self, DialogGraphics):
        if not DialogGraphics.objectName():
            DialogGraphics.setObjectName(u"DialogGraphics")
        DialogGraphics.setWindowModality(Qt.WindowModal)
        DialogGraphics.setEnabled(True)
        DialogGraphics.resize(217, 532)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(DialogGraphics.sizePolicy().hasHeightForWidth())
        DialogGraphics.setSizePolicy(sizePolicy)
        DialogGraphics.setMinimumSize(QSize(217, 532))
        DialogGraphics.setMaximumSize(QSize(217, 568))
        DialogGraphics.setSizeGripEnabled(False)
        DialogGraphics.setModal(True)
        self.verticalLayout = QVBoxLayout(DialogGraphics)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label_36 = QLabel(DialogGraphics)
        self.label_36.setObjectName(u"label_36")
        self.label_36.setMinimumSize(QSize(0, 0))
        self.label_36.setMaximumSize(QSize(999, 16777215))
        font = QFont()
        font.setFamilies([u"\u7b49\u8ddd\u66f4\u7eb1\u9ed1\u4f53 SC Semibold"])
        font.setBold(True)
        self.label_36.setFont(font)
        self.label_36.setAlignment(Qt.AlignCenter)
        self.label_36.setMargin(6)

        self.verticalLayout.addWidget(self.label_36)

        self.comboTheme = QComboBox(DialogGraphics)
        self.comboTheme.addItem("")
        self.comboTheme.addItem("")
        self.comboTheme.addItem("")
        self.comboTheme.setObjectName(u"comboTheme")
        self.comboTheme.setFont(font)
        self.comboTheme.setLayoutDirection(Qt.LeftToRight)
        self.comboTheme.setEditable(False)
        self.comboTheme.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        self.verticalLayout.addWidget(self.comboTheme)

        self.label_35 = QLabel(DialogGraphics)
        self.label_35.setObjectName(u"label_35")
        self.label_35.setMinimumSize(QSize(0, 28))
        self.label_35.setMaximumSize(QSize(999, 16777215))
        self.label_35.setFont(font)
        self.label_35.setAlignment(Qt.AlignCenter)
        self.label_35.setMargin(6)

        self.verticalLayout.addWidget(self.label_35)

        self.spinMaxFps = QDoubleSpinBox(DialogGraphics)
        self.spinMaxFps.setObjectName(u"spinMaxFps")
        self.spinMaxFps.setFont(font)
        self.spinMaxFps.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.spinMaxFps.setDecimals(1)
        self.spinMaxFps.setMinimum(1.000000000000000)
        self.spinMaxFps.setMaximum(120.000000000000000)
        self.spinMaxFps.setSingleStep(5.000000000000000)
        self.spinMaxFps.setValue(60.000000000000000)

        self.verticalLayout.addWidget(self.spinMaxFps)

        self.label_37 = QLabel(DialogGraphics)
        self.label_37.setObjectName(u"label_37")
        self.label_37.setMinimumSize(QSize(0, 28))
        self.label_37.setMaximumSize(QSize(999, 16777215))
        self.label_37.setFont(font)
        self.label_37.setAlignment(Qt.AlignCenter)
        self.label_37.setMargin(6)

        self.verticalLayout.addWidget(self.label_37)

        self.spinDataLength = QSpinBox(DialogGraphics)
        self.spinDataLength.setObjectName(u"spinDataLength")
        self.spinDataLength.setFont(font)
        self.spinDataLength.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.spinDataLength.setMinimum(100)
        self.spinDataLength.setMaximum(10000)
        self.spinDataLength.setSingleStep(100)
        self.spinDataLength.setValue(500)

        self.verticalLayout.addWidget(self.spinDataLength)

        self.label_40 = QLabel(DialogGraphics)
        self.label_40.setObjectName(u"label_40")
        self.label_40.setMinimumSize(QSize(0, 28))
        self.label_40.setMaximumSize(QSize(999, 16777215))
        self.label_40.setFont(font)
        self.label_40.setAlignment(Qt.AlignCenter)
        self.label_40.setMargin(6)

        self.verticalLayout.addWidget(self.label_40)

        self.comboAvgMode = QComboBox(DialogGraphics)
        self.comboAvgMode.addItem("")
        self.comboAvgMode.addItem("")
        self.comboAvgMode.addItem("")
        self.comboAvgMode.setObjectName(u"comboAvgMode")
        self.comboAvgMode.setFont(font)
        self.comboAvgMode.setLayoutDirection(Qt.LeftToRight)
        self.comboAvgMode.setEditable(False)
        self.comboAvgMode.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        self.verticalLayout.addWidget(self.comboAvgMode)

        self.label_38 = QLabel(DialogGraphics)
        self.label_38.setObjectName(u"label_38")
        self.label_38.setMinimumSize(QSize(0, 28))
        self.label_38.setMaximumSize(QSize(999, 16777215))
        self.label_38.setFont(font)
        self.label_38.setAlignment(Qt.AlignCenter)
        self.label_38.setMargin(6)

        self.verticalLayout.addWidget(self.label_38)

        self.spinStateFps = QDoubleSpinBox(DialogGraphics)
        self.spinStateFps.setObjectName(u"spinStateFps")
        self.spinStateFps.setFont(font)
        self.spinStateFps.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.spinStateFps.setDecimals(1)
        self.spinStateFps.setMinimum(1.000000000000000)
        self.spinStateFps.setMaximum(120.000000000000000)
        self.spinStateFps.setSingleStep(5.000000000000000)
        self.spinStateFps.setValue(60.000000000000000)

        self.verticalLayout.addWidget(self.spinStateFps)

        self.label_39 = QLabel(DialogGraphics)
        self.label_39.setObjectName(u"label_39")
        self.label_39.setMinimumSize(QSize(0, 28))
        self.label_39.setMaximumSize(QSize(999, 16777215))
        self.label_39.setFont(font)
        self.label_39.setAlignment(Qt.AlignCenter)
        self.label_39.setMargin(6)

        self.verticalLayout.addWidget(self.label_39)

        self.comboInterp = QComboBox(DialogGraphics)
        self.comboInterp.addItem("")
        self.comboInterp.addItem("")
        self.comboInterp.addItem("")
        self.comboInterp.addItem("")
        self.comboInterp.setObjectName(u"comboInterp")
        self.comboInterp.setFont(font)
        self.comboInterp.setLayoutDirection(Qt.LeftToRight)
        self.comboInterp.setEditable(False)
        self.comboInterp.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        self.verticalLayout.addWidget(self.comboInterp)

        self.checkBoxOpenGL = QCheckBox(DialogGraphics)
        self.checkBoxOpenGL.setObjectName(u"checkBoxOpenGL")
        self.checkBoxOpenGL.setFont(font)

        self.verticalLayout.addWidget(self.checkBoxOpenGL)

        self.line = QFrame(DialogGraphics)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.verticalLayout.addWidget(self.line)

        self.label_42 = QLabel(DialogGraphics)
        self.label_42.setObjectName(u"label_42")
        self.label_42.setMinimumSize(QSize(0, 28))
        self.label_42.setMaximumSize(QSize(999, 16777215))
        self.label_42.setFont(font)
        self.label_42.setAlignment(Qt.AlignCenter)
        self.label_42.setMargin(6)

        self.verticalLayout.addWidget(self.label_42)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setSpacing(6)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.spinStateVThres = QDoubleSpinBox(DialogGraphics)
        self.spinStateVThres.setObjectName(u"spinStateVThres")
        self.spinStateVThres.setFont(font)
        self.spinStateVThres.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.spinStateVThres.setDecimals(3)
        self.spinStateVThres.setMinimum(0.000000000000000)
        self.spinStateVThres.setMaximum(1.000000000000000)
        self.spinStateVThres.setSingleStep(5.000000000000000)
        self.spinStateVThres.setValue(0.001000000000000)

        self.horizontalLayout_2.addWidget(self.spinStateVThres)

        self.spinStateIThres = QDoubleSpinBox(DialogGraphics)
        self.spinStateIThres.setObjectName(u"spinStateIThres")
        self.spinStateIThres.setFont(font)
        self.spinStateIThres.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.spinStateIThres.setDecimals(3)
        self.spinStateIThres.setMinimum(0.000000000000000)
        self.spinStateIThres.setMaximum(1.000000000000000)
        self.spinStateIThres.setSingleStep(5.000000000000000)
        self.spinStateIThres.setValue(0.001000000000000)

        self.horizontalLayout_2.addWidget(self.spinStateIThres)


        self.verticalLayout.addLayout(self.horizontalLayout_2)

        self.labelCali = QLabel(DialogGraphics)
        self.labelCali.setObjectName(u"labelCali")
        self.labelCali.setMinimumSize(QSize(0, 28))
        self.labelCali.setMaximumSize(QSize(999, 16777215))
        self.labelCali.setFont(font)
        self.labelCali.setAlignment(Qt.AlignCenter)
        self.labelCali.setMargin(6)

        self.verticalLayout.addWidget(self.labelCali)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(6)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.btnTear = QPushButton(DialogGraphics)
        self.btnTear.setObjectName(u"btnTear")
        self.btnTear.setFont(font)

        self.horizontalLayout.addWidget(self.btnTear)

        self.btnResetTear = QPushButton(DialogGraphics)
        self.btnResetTear.setObjectName(u"btnResetTear")
        self.btnResetTear.setFont(font)

        self.horizontalLayout.addWidget(self.btnResetTear)


        self.verticalLayout.addLayout(self.horizontalLayout)

        self.btnClose = QPushButton(DialogGraphics)
        self.btnClose.setObjectName(u"btnClose")
        self.btnClose.setFont(font)

        self.verticalLayout.addWidget(self.btnClose)


        self.retranslateUi(DialogGraphics)

        self.comboAvgMode.setCurrentIndex(0)
        self.comboInterp.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(DialogGraphics)
    # setupUi

    def retranslateUi(self, DialogGraphics):
        DialogGraphics.setWindowTitle(QCoreApplication.translate("DialogGraphics", u"\u56fe\u5f62\u8bbe\u7f6e", None))
        self.label_36.setText(QCoreApplication.translate("DialogGraphics", u"\u663e\u793a\u4e3b\u9898", None))
        self.comboTheme.setItemText(0, QCoreApplication.translate("DialogGraphics", u"Dark", None))
        self.comboTheme.setItemText(1, QCoreApplication.translate("DialogGraphics", u"Light", None))
        self.comboTheme.setItemText(2, QCoreApplication.translate("DialogGraphics", u"Auto", None))

        self.label_35.setText(QCoreApplication.translate("DialogGraphics", u"\u56fe\u8868\u6700\u5927\u7ed8\u56fe\u5e27\u7387", None))
        self.spinMaxFps.setSuffix(QCoreApplication.translate("DialogGraphics", u"fps", None))
        self.label_37.setText(QCoreApplication.translate("DialogGraphics", u"\u56fe\u8868\u663e\u793a\u6570\u636e\u70b9\u6570", None))
        self.spinDataLength.setSuffix(QCoreApplication.translate("DialogGraphics", u"pts", None))
        self.spinDataLength.setPrefix("")
        self.label_40.setText(QCoreApplication.translate("DialogGraphics", u"\u56fe\u8868\u6570\u636e\u5e73\u6ed1\u5904\u7406", None))
        self.comboAvgMode.setItemText(0, QCoreApplication.translate("DialogGraphics", u"\u4e0d\u8fdb\u884c\u5e73\u6ed1", None))
        self.comboAvgMode.setItemText(1, QCoreApplication.translate("DialogGraphics", u"\u4e09\u503c\u5e73\u5747", None))
        self.comboAvgMode.setItemText(2, QCoreApplication.translate("DialogGraphics", u"\u4e5d\u503c\u5e73\u5747", None))

        self.label_38.setText(QCoreApplication.translate("DialogGraphics", u"\u72b6\u6001\u533a\u6700\u5927\u5237\u65b0\u7387", None))
        self.spinStateFps.setSuffix(QCoreApplication.translate("DialogGraphics", u"fps", None))
        self.label_39.setText(QCoreApplication.translate("DialogGraphics", u"\u72b6\u6001\u533a\u7535\u538b\u7535\u6d41\u63d2\u503c", None))
        self.comboInterp.setItemText(0, QCoreApplication.translate("DialogGraphics", u"\u4e0d\u8fdb\u884c\u63d2\u503c", None))
        self.comboInterp.setItemText(1, QCoreApplication.translate("DialogGraphics", u"\u4e00\u4f4d\u63d2\u503c", None))
        self.comboInterp.setItemText(2, QCoreApplication.translate("DialogGraphics", u"\u4e8c\u4f4d\u63d2\u503c", None))
        self.comboInterp.setItemText(3, QCoreApplication.translate("DialogGraphics", u"\u4e09\u4f4d\u63d2\u503c", None))

        self.checkBoxOpenGL.setText(QCoreApplication.translate("DialogGraphics", u"\u5f00\u542fOpenGL\u7ed8\u56fe", None))
        self.label_42.setText(QCoreApplication.translate("DialogGraphics", u"\u539f\u59cb\u6570\u636e\u9608\u503c", None))
        self.spinStateVThres.setSuffix(QCoreApplication.translate("DialogGraphics", u"V", None))
        self.spinStateIThres.setSuffix(QCoreApplication.translate("DialogGraphics", u"A", None))
        self.labelCali.setText(QCoreApplication.translate("DialogGraphics", u"\u6821\u51c6", None))
        self.btnTear.setText(QCoreApplication.translate("DialogGraphics", u"\u56de\u96f6", None))
        self.btnResetTear.setText(QCoreApplication.translate("DialogGraphics", u"\u91cd\u7f6e", None))
        self.btnClose.setText(QCoreApplication.translate("DialogGraphics", u"\u5b8c\u6210 / DONE", None))
    # retranslateUi

