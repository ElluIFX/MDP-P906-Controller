import datetime
import json
import math
import os
import random
import sys
import time
import warnings
from functools import partial
from threading import Lock
from typing import List, Optional, Tuple

os.environ["PYQTGRAPH_QT_LIB"] = "PyQt5"
warnings.filterwarnings("ignore", category=RuntimeWarning)

ARG_PATH = os.path.dirname(sys.argv[0])
ABS_PATH = os.path.dirname(__file__)
import richuru
from loguru import logger

if os.environ.get("MDP_ENABLE_LOG") is not None or "--debug" in sys.argv:
    richuru.install(level="DEBUG")
    logger.add(
        os.path.join(ARG_PATH, "mdp.log"), level="TRACE", backtrace=True, diagnose=True
    )
    DEBUG = True
else:
    richuru.install(level="INFO")
    DEBUG = False
logger.info("---- NEW SESSION ----")
logger.info(f"ARG_PATH: {ARG_PATH}")
logger.info(f"ABS_PATH: {ABS_PATH}")

try:
    from mdp_controller import MDP_P906
except ImportError:
    logger.info("Redirecting to repo mdp_controller")
    sys.path.append(os.path.dirname(ABS_PATH))
    sys.path.append(os.path.dirname(os.path.dirname(ABS_PATH)))
    from mdp_controller import MDP_P906

    logger.success("Found mdp_controller in repo")

import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets
from qframelesswindow import FramelessWindow

OPENGL_AVALIABLE = False
if sys.platform == "win32":  # OpenGL is not available on Linux
    try:
        import OpenGL  # noqa: F401

        OPENGL_AVALIABLE = True
        logger.success("OpenGL successfully enabled")
    except Exception as e:
        logger.warning(f"Enabling OpenGL failed with {e}.")
else:
    logger.info("OpenGL disabled on Linux")

NUMBA_ENABLED = False
try:
    import llvmlite  # noqa: F401
    import numba as nb  # noqa: F401

    pg.setConfigOption("useNumba", True)
    logger.success("Numba successfully enabled")
    NUMBA_ENABLED = True
except Exception as e:
    logger.warning(f"Enabling Numba failed with {e}.")


import numpy as np
import qdarktheme
from mdp_gui_template import Ui_DialogGraphics, Ui_DialogSettings, Ui_MainWindow
from serial.tools.list_ports import comports
from simple_pid import PID
from superqt.utils import signals_blocked

SETTING_FILE = os.path.join(ARG_PATH, "settings.json")
ICON_PATH = os.path.join(ABS_PATH, "icon.ico")
FONT_PATH = os.path.join(ABS_PATH, "SarasaFixedSC-SemiBold.ttf")
BAT_EXAMPLE_PATH = os.path.join(ABS_PATH, "Li-ion.csv")
VERSION = "Ver4.5"
qdarktheme.enable_hi_dpi()
app = QtWidgets.QApplication(sys.argv)

# get system language
system_lang = QtCore.QLocale.system().name()
logger.info(f"System language: {system_lang}")
ENGLISH = False
if (
    not system_lang.startswith("zh")
    or os.environ.get("MDP_FORCE_ENGLISH") == "1"
    or "--english" in sys.argv
):
    trans = QtCore.QTranslator()
    trans.load(os.path.join(ABS_PATH, "en_US.qm"))
    app.installTranslator(trans)
    ENGLISH = True

# load custom font
_ = QtGui.QFontDatabase.addApplicationFont(FONT_PATH)
fonts = QtGui.QFontDatabase.applicationFontFamilies(_)
logger.info(f"Loaded custom fonts: {fonts}")
global_font = QtGui.QFont()
global_font.setFamily(fonts[0])
app.setFont(global_font)

from mdp_custom import CustomInputDialog, CustomMessageBox, CustomTitleBar, FmtAxisItem


class RealtimeData:
    def __init__(self, data_length) -> None:
        self.start_time = time.perf_counter()
        self.eng_start_time = time.perf_counter()
        self.last_time = 0
        self.voltage_tmp = []
        self.current_tmp = []
        self.energy = 0
        self.sync_lock = Lock()
        self.voltages = np.zeros(data_length, np.float64)
        self.currents = np.zeros(data_length, np.float64)
        self.powers = np.zeros(data_length, np.float64)
        self.resistances = np.zeros(data_length, np.float64)
        self.times = np.zeros(data_length, np.float64)
        self.update_count = 0
        self.data_length = data_length


class RecordData:
    def __init__(self) -> None:
        self.voltages: List[float] = []
        self.currents: List[float] = []
        self.times: List[float] = []
        self.start_time = 0
        self.last_time = 0

    def add_values(self, voltage, current, time):
        self.voltages.append(voltage)
        self.currents.append(current)
        self.times.append(time)

    def to_csv(self, filename):
        data = np.array([self.times, self.voltages, self.currents]).T
        np.savetxt(
            filename,
            data,
            delimiter=",",
            fmt="%f",
            header="time/s,voltage/V,current/A",
            comments="",
        )


class FPSCounter(object):
    def __init__(self, max_sample=40) -> None:
        self.t = time.perf_counter()
        self.max_sample = max_sample
        self.t_list: List[float] = []
        self._fps = 0

    def clear(self) -> None:
        self.t = time.perf_counter()
        self.t_list = []
        self._fps = 0

    def tick(self) -> None:
        t = time.perf_counter()
        self.t_list.append(t - self.t)
        self.t = t
        if len(self.t_list) > self.max_sample:
            self.t_list.pop(0)

    @property
    def fps(self) -> float:
        length = len(self.t_list)
        sum_t = sum(self.t_list)
        if length == 0 or sum_t == 0:
            self._fps = 0
        else:
            fps = length / sum_t
            if abs(fps - self._fps) > 2 or self._fps == 0:
                self._fps = fps
            else:
                self._fps += (fps - self._fps) * 2 / self._fps
        return self._fps


def center_window(instance: QtWidgets.QWidget, width=None, height=None) -> None:
    if instance.isMaximized():  # restore window size
        instance.showNormal()
    if instance.isVisible():  # bring window to front
        instance.activateWindow()
    scr_geo = QtWidgets.QApplication.primaryScreen().geometry()
    logger.debug(f"Screen geometry: {scr_geo}")
    if not width or not height:  # center window
        geo = instance.geometry()
        center_x = (scr_geo.width() - geo.width()) // 2
        center_y = (scr_geo.height() - geo.height()) // 2
        instance.move(center_x, center_y)
    else:  # set window size and center window
        center_x = (scr_geo.width() - width) // 2
        center_y = (scr_geo.height() - height) // 2
        instance.setGeometry(center_x, center_y, width, height)


def float_str(value, limit=1e5):
    if value > limit:
        return f"{value:.1e}"
    else:
        return f"{value:.3f}"


def set_color(widget: QtWidgets.QWidget, rgb):
    if not rgb or rgb == "default":
        widget.setStyleSheet("")
        return
    color = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})" if isinstance(rgb, tuple) else rgb
    widget.setStyleSheet(f"color: {color}")


class Setting:
    def __init__(self) -> None:
        self.presets = {
            "1": (3.3, 2),
            "2": (3.3, 5),
            "3": (5, 2),
            "4": (5, 5),
            "5": (9, 5),
            "6": (12, 5),
            "7": (20, 5),
            "8": (24, 10),
            "9": (30, 10),
        }
        self.baudrate = 921600
        self.comport = ""
        self.address = "AA:BB:CC:DD:EE"
        self.freq = 2521
        self.txpower = "4dBm"
        self.idcode = ""
        self.color = "66CCFF"
        self.m01ch = "CH-0"
        self.blink = False

        self.data_pts = 100000
        self.display_pts = 600
        self.graph_max_fps = 50
        self.state_fps = 15
        self.interp = 1
        self.avgmode = 1
        self.opengl = False
        self.antialias = True
        self.bitadjust = True

        self.v_threshold = 0.002
        self.i_threshold = 0.002
        self.use_cali = False
        self.v_cali_k = 1.0
        self.v_cali_b = 0.0
        self.i_cali_k = 1.0
        self.i_cali_b = 0.0
        self.vset_cali_k = 1.0
        self.vset_cali_b = 0.0
        self.iset_cali_k = 1.0
        self.iset_cali_b = 0.0
        self.output_warning = False
        self.lock_when_output = False
        self.ignore_hw_lock = False
        self.theme = "dark"
        self.color_palette = {
            "dark": {
                "off": "khaki",
                "on": "lightgreen",
                "cv": "skyblue",
                "cc": "tomato",
                "lcd_voltage": "default",
                "lcd_current": "default",
                "lcd_power": "default",
                "lcd_energy": "default",
                "lcd_avg_power": "default",
                "lcd_resistance": "default",
                "general_green": "mediumaquamarine",
                "general_red": "orangered",
                "general_yellow": "yellow",
                "general_blue": "lightblue",
                "line1": "salmon",
                "line2": "turquoise",
            },
            "light": {
                "lcd_voltage": "default",
                "lcd_current": "default",
                "lcd_power": "default",
                "lcd_energy": "default",
                "lcd_avg_power": "default",
                "lcd_resistance": "default",
                "off": "darkgoldenrod",
                "on": "darkgreen",
                "cv": "darkblue",
                "cc": "darkred",
                "general_green": "forestgreen",
                "general_red": "firebrick",
                "general_yellow": "goldenrod",
                "general_blue": "darkblue",
                "line1": "orangered",
                "line2": "darkcyan",
            },
            "modify_this_to_add_your_custom_theme": {
                "based_on_dark_or_light": "dark",
                "any_other_item": "any_other_color",
            },
        }

    def save(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=4, ensure_ascii=False)

    def load(self, filename):
        if not os.path.exists(filename):
            self.save(filename)
            return
        def_colorplate = self.color_palette
        self.__dict__.update(json.load(open(filename, "r", encoding="utf-8")))
        for k, v in def_colorplate.items():
            if k not in self.color_palette:
                self.color_palette[k] = v
            elif len(self.color_palette[k]) < len(v):
                v.update(self.color_palette[k])
                self.color_palette[k] = v

    def get_color(self, key, override_theme=None):
        t = override_theme or self.theme
        if t in ("dark", "light"):
            return self.color_palette[t].get(key)
        else:
            if "based_on_dark_or_light" not in self.color_palette[t]:
                self.color_palette[t]["based_on_dark_or_light"] = "dark"
            return self.color_palette[t].get(
                key,
                self.color_palette[self.color_palette[t]["based_on_dark_or_light"]].get(
                    key
                ),
            )

    def __repr__(self) -> str:
        return f"Setting({self.__dict__})"


setting = Setting()
setting.load(SETTING_FILE)
setting.save(SETTING_FILE)


def update_pyqtgraph_setting():
    pg.setConfigOption("antialias", setting.antialias)
    if OPENGL_AVALIABLE:
        pg.setConfigOption("enableExperimental", setting.opengl)
        pg.setConfigOption("useOpenGL", setting.opengl)
    logger.debug(f"Antialias: {setting.antialias}, OpenGL: {setting.opengl}")


update_pyqtgraph_setting()


class MDPMainwindow(QtWidgets.QMainWindow, FramelessWindow):  # QtWidgets.QMainWindow
    uip_values_signal = QtCore.pyqtSignal(float, float, float)
    display_data_signal = QtCore.pyqtSignal(list, list, str, str, str, str, str, bool)
    highlight_point_signal = QtCore.pyqtSignal(float, float)
    close_signal = QtCore.pyqtSignal()
    data = RealtimeData(setting.data_pts)
    data_fps = 50
    graph_keep_flag = False
    graph_record_flag = False
    locked = False
    _v_set = 0.0
    _i_set = 0.0
    _output_state = False
    output_state_str = ""
    open_r = 1e7
    continuous_energy_counter = 0
    model = "Unknown"

    def __init__(self, parent=None):
        self.api: Optional[MDP_P906] = None

        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.initSignals()
        self.initGraph()
        self.initTimer()
        self.fps_counter = FPSCounter()
        self.CustomTitleBar = CustomTitleBar(
            self,
            self.tr("MDP-P906 数控电源上位机") + f" {VERSION}",
        )
        self.CustomTitleBar.set_theme("dark")
        self.ui.comboDataFps.setCurrentText(f"{self.data_fps}Hz")
        self.setTitleBar(self.CustomTitleBar)
        self.set_interp(setting.interp)
        self.refresh_preset()
        self.get_preset("1")
        self.close_state_ui()
        self.load_battery_model(BAT_EXAMPLE_PATH)
        center_window(self, 920, 800)
        self.ui.progressBarVoltage.setMaximum(1000)
        self.ui.progressBarCurrent.setMaximum(1000)
        self._last_state_change_t = time.perf_counter()
        self.titleBar.raise_()
        self.ui.btnSeqStop.hide()
        self.ui.listSeq.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui.spinBoxVoltage.setSingleStep(0.001)
        self.ui.spinBoxCurrent.setSingleStep(0.001)

        self.ui.tabWidget.tabBar().setVisible(False)
        self.ui.labelTab.setText(
            self.ui.tabWidget.tabText(self.ui.tabWidget.currentIndex())
        )

        if ENGLISH:
            c_font = QtGui.QFont()
            c_font.setFamily("Sarasa Fixed SC SemiBold")
            c_font.setPointSize(7)
            self.ui.btnSeqCurrent.setFont(c_font)
            self.ui.btnSeqCurrent.setText("I-SET")
            self.ui.btnSeqVoltage.setFont(c_font)
            self.ui.btnSeqVoltage.setText("V-SET")
            self.ui.btnSeqDelay.setFont(c_font)
            self.ui.btnSeqWaitTime.setFont(c_font)
            self.ui.btnSeqSingle.setFont(c_font)
            self.ui.btnSeqSingle.setText("Once")
            self.ui.btnSeqLoop.setFont(c_font)
            self.ui.btnSeqSave.setFont(c_font)
            self.ui.btnSeqLoad.setFont(c_font)

    @QtCore.pyqtSlot(int)
    def on_tabWidget_currentChanged(self, index):
        self.ui.labelTab.setText(self.ui.tabWidget.tabText(index))
        if index == 0:
            self.ui.pushButtonLastTab.setEnabled(False)
        elif index == self.ui.tabWidget.count() - 1:
            self.ui.pushButtonNextTab.setEnabled(False)
        else:
            self.ui.pushButtonLastTab.setEnabled(True)
            self.ui.pushButtonNextTab.setEnabled(True)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        pos = event.pos()
        label_geom = self.ui.labelTab.geometry()
        label_pos = self.ui.labelTab.mapTo(self, QtCore.QPoint(0, 0))
        label_rect = QtCore.QRect(label_pos, label_geom.size())
        if self.api is not None and label_rect.contains(pos):
            delta = event.angleDelta().y()
            current_idx = self.ui.tabWidget.currentIndex()
            if delta > 0:
                if current_idx > 0:
                    self.ui.tabWidget.setCurrentIndex(current_idx - 1)
            else:
                if current_idx < self.ui.tabWidget.count() - 1:
                    self.ui.tabWidget.setCurrentIndex(current_idx + 1)
            event.accept()
        else:
            event.ignore()

    @QtCore.pyqtSlot()
    def on_pushButtonLastTab_clicked(self):
        idx = self.ui.tabWidget.currentIndex()
        if idx > 0:
            self.ui.tabWidget.setCurrentIndex(idx - 1)

    @QtCore.pyqtSlot()
    def on_pushButtonNextTab_clicked(self):
        idx = self.ui.tabWidget.currentIndex()
        if idx < self.ui.tabWidget.count() - 1:
            self.ui.tabWidget.setCurrentIndex(idx + 1)

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.close_signal.emit()
        return super().closeEvent(a0)

    def initTimer(self):
        self.state_request_sender_timer = QtCore.QTimer(self)
        self.state_request_sender_timer.setTimerType(QtCore.Qt.PreciseTimer)
        self.state_request_sender_timer.timeout.connect(self.request_state)
        self.update_state_timer = QtCore.QTimer(self)
        self.update_state_timer.timeout.connect(self.update_state)
        self.draw_graph_timer = QtCore.QTimer(self)
        self.draw_graph_timer.timeout.connect(self.draw_graph)
        self.state_lcd_timer = QtCore.QTimer(self)
        self.state_lcd_timer.timeout.connect(self.update_state_lcd)
        self.func_sweep_timer = QtCore.QTimer(self)
        self.func_sweep_timer.timeout.connect(self.func_sweep)
        self.func_wave_gen_timer = QtCore.QTimer(self)
        self.func_wave_gen_timer.timeout.connect(self.func_wave_gen)
        self.func_keep_power_timer = QtCore.QTimer(self)
        self.func_keep_power_timer.timeout.connect(self.func_keep_power)
        self.func_seq_timer = QtCore.QTimer(self)
        self.func_seq_timer.timeout.connect(self.func_seq)
        self.func_bat_sim_timer = QtCore.QTimer(self)
        self.func_bat_sim_timer.timeout.connect(self.func_bat_sim)
        self.graph_record_save_timer = QtCore.QTimer(self)
        self.graph_record_save_timer.timeout.connect(self.graph_record_save)
        self.stable_checker_timer = QtCore.QTimer(self)
        self.stable_checker_timer.timeout.connect(self.stable_checker)

    def initSignals(self):
        self.ui.comboDataFps.currentTextChanged.connect(self.set_data_fps)
        self.ui.comboPreset.currentTextChanged.connect(self.set_preset)
        self.ui.comboPresetEdit.currentTextChanged.connect(self.get_preset)
        self.ui.comboGraph1Data.currentTextChanged.connect(self.set_graph1_data)
        self.ui.comboGraph2Data.currentTextChanged.connect(self.set_graph2_data)
        self.ui.spinBoxVoltage.valueChanged.connect(self.voltage_changed)
        self.ui.spinBoxCurrent.valueChanged.connect(self.current_changed)
        self.ui.comboWaveGenType.currentTextChanged.connect(self.set_wavegen_type)
        self.ui.spinBoxVoltage.lineEdit().cursorPositionChanged.connect(
            lambda *args: self.set_step(self.ui.spinBoxVoltage, *args)
        )
        self.ui.spinBoxCurrent.lineEdit().cursorPositionChanged.connect(
            lambda *args: self.set_step(self.ui.spinBoxCurrent, *args)
        )
        self.ui.horizontalSlider.sliderMoved.connect(
            self.on_horizontalSlider_sliderMoved
        )

    def startMyTimer(self):
        t = time.perf_counter()
        self.data.start_time = t
        self.data.eng_start_time = t
        self.data.last_time = t
        self.data.energy = 0
        self.update_state_timer.start(100)
        self.state_request_sender_timer.start(round(1000 / self.data_fps))
        self.draw_graph_timer.start(
            round(1000 / min(self.data_fps, setting.graph_max_fps))
        )
        self.state_lcd_timer.start(round(1000 / min(self.data_fps, setting.state_fps)))

    def stopMyTimer(self):
        self.state_request_sender_timer.stop()
        self.draw_graph_timer.stop()
        self.state_lcd_timer.stop()
        if self.func_sweep_timer.isActive():
            self.stop_func_sweep()
        if self.func_wave_gen_timer.isActive():
            self.stop_func_wave_gen()
        if self.func_keep_power_timer.isActive():
            self.stop_func_keep_power()
        if self.func_seq_timer.isActive():
            self.stop_func_seq()
        if self.func_bat_sim_timer.isActive():
            self.stop_func_bat_sim()
        if self.graph_record_save_timer.isActive():
            self.on_btnGraphRecord_clicked()
        if self.stable_checker_timer.isActive():
            self.stable_checker_timer.stop()

    def switch_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def set_step(self, spin: QtWidgets.QDoubleSpinBox, f, t):
        if not setting.bitadjust:
            # enable adaptive step size
            spin.setStepType(
                QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType
            )
            return
        spin.setStepType(QtWidgets.QAbstractSpinBox.StepType.DefaultStepType)
        STEPS = {
            0: 0.001,
            -1: 0.001,
            -2: 0.01,
            -3: 0.1,
        }
        if spin.lineEdit().hasSelectedText():
            return
        text = spin.lineEdit().text()
        tt = t - len(spin.lineEdit().text())
        t -= 1
        if tt == 0:
            t -= 1
        if text[t] == ".":
            if f < t:
                t += 1
            else:
                t -= 1
        if t <= 0:
            t = 0
        if spin.value() >= 10 and t == 0:
            t = 1
        spin.lineEdit().setSelection(t, 1)
        spin.setSingleStep(STEPS.get(tt, 1))

    ##########  基本功能  ##########

    @property
    def v_set(self):
        return self._v_set

    @v_set.setter
    def v_set(self, value):
        if self.api is None or self.locked:
            return
        value = max(0, min(value, 30))
        self._v_set = value
        self.ui.spinBoxVoltage.setValue(value)
        if setting.use_cali:
            value = value * setting.vset_cali_k + setting.vset_cali_b
        self.api.set_voltage(value)
        self._last_state_change_t = time.perf_counter()

    @property
    def i_set(self):
        return self._i_set

    @i_set.setter
    def i_set(self, value):
        if self.api is None or self.locked:
            return
        value = max(0, min(value, 10))
        self._i_set = value
        self.ui.spinBoxCurrent.setValue(value)
        if setting.use_cali:
            value = value * setting.iset_cali_k + setting.iset_cali_b
        self.api.set_current(value)
        self._last_state_change_t = time.perf_counter()

    @property
    def output_state(self):
        return self._output_state

    @output_state.setter
    def output_state(self, value):
        if self.api is None or value == self._output_state:
            return
        if setting.output_warning and not self._output_state:
            ok = CustomMessageBox.question(
                self,
                self.tr("警告"),
                self.tr("确定要打开输出?")
                + f"\n{self.tr('电压')}: {self.v_set:.3f}V"
                + f"\n{self.tr('电流')}: {self.i_set:.3f}A",
            )
            if not ok:
                return
        self._output_state = value
        self._last_state_change_t = time.perf_counter()
        self.api.set_output(self._output_state)
        self.update_state()

    def update_state(self):
        if self.api is None:
            return
        self.ui.labelComSpeed.setText(f"{self.api.speed_counter.KBps:.1f}kBps")
        errrate = self.api.speed_counter.error_rate * 100
        self.ui.labelErrRate.setText(f"CON-ERR {errrate:.0f}%")
        clr = (
            setting.get_color("general_red")
            if errrate > 50
            else (setting.get_color("general_yellow") if errrate > 10 else None)
        )
        set_color(self.ui.labelErrRate, clr)
        set_color(self.ui.labelComSpeed, clr)
        (
            State,
            Locked,
            SetVoltage,
            SetCurrent,
            InputVoltage,
            InputCurrent,
            Temperature,
            ErrFlag,
            _,
            Model,
        ) = self.api.get_status()
        if Model != self.model:
            self.model = Model
            if Model == "P905":
                self.ui.spinBoxCurrent.setRange(0, 5)
                self.CustomTitleBar.set_name(
                    self.tr("MDP-P906 数控电源上位机") + f" {VERSION} - P905 Mode"
                )
            elif Model == "P906":
                self.ui.spinBoxCurrent.setRange(0, 10)
                self.CustomTitleBar.set_name(
                    self.tr("MDP-P906 数控电源上位机") + f" {VERSION}"
                )
        self.ui.btnOutput.setText(f"-  {State.upper()}  -")
        set_color(
            self.ui.btnOutput,
            setting.get_color(State),
        )
        self._output_state = State != "off"
        self.output_state_str = State
        self.locked = False
        if not setting.ignore_hw_lock and Locked:
            self.locked = True
        self.ui.frameOutputSetting.setEnabled(not self.locked)
        if setting.lock_when_output and self._output_state:
            self.locked = True
        self.ui.spinBoxVoltage.setEnabled(not self.locked)
        self.ui.spinBoxCurrent.setEnabled(not self.locked)
        if SetVoltage >= 0:
            if setting.use_cali:
                SetVoltage = (SetVoltage - setting.vset_cali_b) / setting.vset_cali_k
            self._v_set = SetVoltage
            if not self.ui.spinBoxVoltage.hasFocus():
                self.ui.spinBoxVoltage.setValue(SetVoltage)
        if SetCurrent >= 0:
            if setting.use_cali:
                SetCurrent = (SetCurrent - setting.iset_cali_b) / setting.iset_cali_k
            self._i_set = SetCurrent
            if not self.ui.spinBoxCurrent.hasFocus():
                self.ui.spinBoxCurrent.setValue(SetCurrent)
        self.ui.labelLockState.setText("[LOCKED]" if Locked else "UNLOCKED")
        set_color(
            self.ui.labelLockState,
            setting.get_color("general_red") if Locked else None,
        )
        self.ui.labelInputVals.setText(f"{InputVoltage:.2f}V {InputCurrent:.2f}A")
        self.ui.labelTemperature.setText(f"TEMP {Temperature:.1f}℃")
        self.ui.labelError.setText(
            f"ERROR-{ErrFlag:02X}" if ErrFlag != 0 else "NO ERROR"
        )
        set_color(self.ui.labelError, "red" if ErrFlag != 0 else None)

    @QtCore.pyqtSlot()
    def on_btnOutput_clicked(self):
        self.output_state = not self.output_state

    _stable_callback = None
    _stable_start_t = 0

    def stable_checker(self):
        dt = time.perf_counter() - self._stable_start_t
        stable = (
            self.output_state_str == "cc"
            or abs(self.data.voltages[self.data.update_count - 1] - self.v_set) < 0.1
            or dt > 10
        )
        if stable:
            logger.info(f"Output is stable after {dt:.3f}s")
            if self._stable_callback is not None:
                self._stable_callback()
                self._stable_callback = None
            self.stable_checker_timer.stop()

    def wait_output_stable(self, func):
        self.output_state = True
        self._stable_callback = func
        self._stable_start_t = time.perf_counter()
        self.stable_checker_timer.start(50)

    def close_state_ui(self):
        self.ui.labelConnectState.setText(self.tr("未连接"))
        set_color(self.ui.labelConnectState, None)
        self.ui.frameOutputSetting.setEnabled(False)
        self.ui.frameSystemState.setEnabled(False)
        self.ui.frameGraph.setEnabled(False)
        self.ui.progressBarCurrent.setValue(0)
        self.ui.progressBarVoltage.setValue(0)
        self.state_callback([(0, 0)])
        self.ui.btnOutput.setText("[N/A]")
        set_color(self.ui.btnOutput, None)
        for widget in [
            self.ui.labelLockState,
            self.ui.labelInputVals,
            self.ui.labelTemperature,
            self.ui.labelError,
            self.ui.labelComSpeed,
            self.ui.labelErrRate,
        ]:
            set_color(widget, None)
            widget.setText("[N/A]")
        self.curve1.setData(x=[], y=[])
        self.curve2.setData(x=[], y=[])
        self.ui.labelGraphInfo.setText("No Info")
        for widget in [
            self.ui.lcdVoltage,
            self.ui.lcdCurrent,
            self.ui.lcdResistence,
            self.ui.lcdPower,
            self.ui.lcdAvgPower,
            self.ui.lcdEnerge,
        ]:
            widget.display("")
        self.ui.horizontalSlider.setRange(0, 10)
        self.ui.horizontalSlider.setValue((2, 8))
        self.ui.labelBufferSize.setText("N/A")
        self.ui.labelDisplayRange.setText("N/A")
        set_color(self.ui.labelBufferSize, None)
        self.ui.frameGraphControl.setEnabled(False)

    def open_state_ui(self):
        self.ui.labelConnectState.setText(self.tr("已连接"))
        set_color(
            self.ui.labelConnectState,
            setting.get_color("general_green"),
        )
        self.ui.frameOutputSetting.setEnabled(True)
        self.ui.frameGraph.setEnabled(True)
        self.ui.frameSystemState.setEnabled(True)
        self.ui.frameGraphControl.setEnabled(True)

    @QtCore.pyqtSlot()
    def on_btnConnect_clicked(self):
        try:
            if self.api is not None:
                self.stopMyTimer()
                self.close_state_ui()
                api = self.api
                self.api = None
                api.close()
                self.v_set = 0.0
                self.i_set = 0.0
                self.model = "Unknown"
                self.ui.spinBoxCurrent.setRange(0, 10)
                self.CustomTitleBar.set_name(
                    self.tr("MDP-P906 数控电源上位机") + f" {VERSION}"
                )
            else:
                if not setting.idcode:
                    CustomMessageBox(
                        self,
                        self.tr("错误"),
                        self.tr("IDCODE为空, 请先完成连接设置"),
                    )
                    return
                color_rgb = bytes.fromhex(setting.color.lstrip("#"))
                api = None
                try:
                    api = MDP_P906(
                        port=setting.comport,
                        baudrate=setting.baudrate,
                        address=setting.address,
                        freq=int(setting.freq),
                        blink=setting.blink,
                        idcode=setting.idcode,
                        led_color=(color_rgb[0], color_rgb[1], color_rgb[2]),
                        m01_channel=int(setting.m01ch[3]),
                        tx_output_power=setting.txpower,
                        debug=DEBUG,
                    )
                    api.connect(retry_times=2)
                except Exception as e:
                    if api is not None:
                        api.close()
                    logger.exception("Failed to connect")
                    raise e
                self.api = api
                self.api.register_realtime_value_callback(self.state_callback)
                self._last_state_change_t = time.perf_counter()
                self.startMyTimer()
                self.update_state()
                self.open_state_ui()
                self.on_btnGraphClear_clicked(skip_confirm=True)
        except Exception as e:
            CustomMessageBox(self, self.tr("连接失败"), str(e))
            return

    def request_state(self):
        if self.api is not None:
            self.api.request_realtime_value()

    def state_callback(self, rtvalues: List[Tuple[float, float]]):
        vt, it = setting.v_threshold, setting.i_threshold
        if setting.use_cali:
            rtvalues = [
                (
                    v * setting.v_cali_k + setting.v_cali_b,
                    i * setting.i_cali_k + setting.i_cali_b,
                )
                for v, i in rtvalues
            ]
        len_ = len(rtvalues)
        rtvalues = [(v if v > vt else 0.0, i if i > it else 0.0) for v, i in rtvalues]
        t1 = time.perf_counter()
        data = self.data
        if self.graph_record_flag:
            if self.graph_record_data.start_time == 0:
                self.graph_record_data.start_time = t1
                self.graph_record_data.last_time = t1
            else:
                t = t1 - self.graph_record_data.start_time
                dt = t1 - self.graph_record_data.last_time
                self.graph_record_data.last_time = t1
                for idx, (v, i) in enumerate(rtvalues):
                    self.graph_record_data.add_values(
                        v, i, t - dt + (dt / len_) * (idx + 1)
                    )
        eng = 0
        with data.sync_lock:
            for v, i in rtvalues:
                data.voltage_tmp.append(v)
                data.current_tmp.append(i)
            if len(rtvalues) == 9:
                if setting.avgmode == 1:
                    rtvalues = np.array(rtvalues)
                    rtvalues = np.reshape(rtvalues, [3, 3, 2])
                    rtvalues = np.mean(rtvalues, axis=(1))
                    len_ = 3
                elif setting.avgmode == 2:
                    rtvalues = np.array(rtvalues)
                    rtvalues = np.reshape(rtvalues, [1, 9, 2])
                    rtvalues = np.mean(rtvalues, axis=(1))
                    len_ = 1
            t = t1 - data.start_time
            dt = t1 - data.last_time
            data.last_time = t1
            for idx, (v, i) in enumerate(rtvalues):
                eng += v * i * (dt / len_)
            self.continuous_energy_counter += eng
            data.energy += eng
            if data.update_count + len_ > data.data_length:
                offset = data.update_count + len_ - data.data_length
                data.voltages = np.roll(data.voltages, -offset)
                data.currents = np.roll(data.currents, -offset)
                data.powers = np.roll(data.powers, -offset)
                data.resistances = np.roll(data.resistances, -offset)
                data.times = np.roll(data.times, -offset)
                data.update_count -= offset
            for idx, (v, i) in enumerate(rtvalues):
                data.voltages[data.update_count + idx] = v
                data.currents[data.update_count + idx] = i
                data.powers[data.update_count + idx] = v * i
                data.resistances[data.update_count + idx] = (
                    v / i if i != 0 else self.open_r
                )
                data.times[data.update_count + idx] = t - dt + (dt / len_) * (idx + 1)
            data.update_count += len_
        self.fps_counter.tick()

    def update_state_lcd(self):
        data = self.data
        if len(data.voltage_tmp) == 0 or len(data.current_tmp) == 0:
            return
        with data.sync_lock:
            vavg = sum(data.voltage_tmp) / len(data.voltage_tmp)
            iavg = sum(data.current_tmp) / len(data.current_tmp)
            data.voltage_tmp.clear()
            data.current_tmp.clear()
            self.ui.lcdAvgPower.display(
                f"{data.energy / (data.last_time - data.eng_start_time):.{3+setting.interp}f}"
            )
            self.ui.lcdEnerge.display(f"{data.energy:.{3+setting.interp}f}")
        power = vavg * iavg
        if iavg >= 0.002:  # 致敬P906的愚蠢adc
            resistance = vavg / iavg
        else:
            resistance = self.open_r
        r_text = (
            f"{resistance:.{3+setting.interp}f}"
            if resistance < self.open_r / 100
            else "--"
        )
        self.ui.lcdVoltage.display(f"{vavg:.{3+setting.interp}f}")
        self.ui.lcdCurrent.display(f"{iavg:.{3+setting.interp}f}")
        self.ui.lcdResistence.display(r_text)
        self.ui.lcdPower.display(f"{power:.{3+setting.interp}f}")
        self.uip_values_signal.emit(vavg, iavg, power)
        v_value = round(vavg / self.v_set * 1000) if self.v_set != 0 else 0
        i_value = round(iavg / self.i_set * 1000) if self.i_set != 0 else 0
        self.ui.progressBarVoltage.setValue(min(v_value, 1000))
        self.ui.progressBarCurrent.setValue(min(i_value, 1000))
        self.ui.progressBarVoltage.update()
        self.ui.progressBarCurrent.update()

    def set_interp(self, interp):
        self.ui.lcdVoltage.setDigitCount(6 + interp)
        self.ui.lcdCurrent.setDigitCount(6 + interp)
        self.ui.lcdResistence.setDigitCount(6 + interp)
        self.ui.lcdPower.setDigitCount(6 + interp)
        self.ui.lcdAvgPower.setDigitCount(6 + interp)
        self.ui.lcdEnerge.setDigitCount(6 + interp)

    def set_data_fps(self, text):
        if text != "":
            self.data_fps = int(text.replace("Hz", ""))
        if self.state_request_sender_timer.isActive():
            self.state_request_sender_timer.stop()
            self.state_request_sender_timer.start(round(1000 / self.data_fps))
        if self.draw_graph_timer.isActive():
            self.draw_graph_timer.stop()
            self.draw_graph_timer.start(
                round(1000 / min(self.data_fps, setting.graph_max_fps))
            )
        if self.state_lcd_timer.isActive():
            self.state_lcd_timer.stop()
            self.state_lcd_timer.start(
                round(1000 / min(self.data_fps, setting.state_fps))
            )
        self.fps_counter.clear()

    def set_graph_max_fps(self, _):
        self.set_data_fps(self.ui.comboDataFps.currentText())

    def set_state_fps(self, fps):
        self.set_data_fps(self.ui.comboDataFps.currentText())

    def set_data_length(self, length) -> None:
        self.data.data_length = length
        self.on_btnGraphClear_clicked(skip_confirm=True)

    @QtCore.pyqtSlot()
    def on_btnRecordClear_clicked(self):
        with self.data.sync_lock:
            self.data.energy = 0
            self.data.eng_start_time = time.perf_counter()

    @QtCore.pyqtSlot()
    def on_spinBoxVoltage_editingFinished(self):
        v_set = self.ui.spinBoxVoltage.value()
        self.ui.spinBoxVoltage.setSingleStep(0.001)
        self.v_set = v_set

    @QtCore.pyqtSlot()
    def on_spinBoxCurrent_editingFinished(self):
        i_set = self.ui.spinBoxCurrent.value()
        self.ui.spinBoxCurrent.setSingleStep(0.001)
        self.i_set = i_set

    def voltage_changed(self, value):
        if not self.ui.checkBoxQuickset.isChecked():
            return
        self.v_set = value

    def current_changed(self, value):
        if not self.ui.checkBoxQuickset.isChecked():
            return
        self.i_set = value

    ##########  图像绘制  ##########

    def initGraph(self):
        self.ui.widgetGraph1.setBackground(None)
        self.ui.widgetGraph2.setBackground(None)
        self.ui.widgetGraph1.setLabel("left", self.tr("电压"), units="V")
        self.ui.widgetGraph2.setLabel("left", self.tr("电流"), units="A")
        self._graph_units_dict = {
            self.tr("电压"): "V",
            self.tr("电流"): "A",
            self.tr("功率"): "W",
            self.tr("阻值"): "Ω",
        }
        self.ui.widgetGraph1.showGrid(x=True, y=True)
        self.ui.widgetGraph2.showGrid(x=True, y=True)
        self.ui.widgetGraph1.setMouseEnabled(x=False, y=False)
        self.ui.widgetGraph2.setMouseEnabled(x=False, y=False)
        self.pen1 = pg.mkPen(color=setting.get_color("line1"), width=1)
        self.pen2 = pg.mkPen(color=setting.get_color("line2"), width=1)
        self.curve1 = self.ui.widgetGraph1.plot(pen=self.pen1, clear=True)
        self.curve2 = self.ui.widgetGraph2.plot(pen=self.pen2, clear=True)
        self._graph_auto_scale_flag = True
        axis1 = FmtAxisItem(orientation="left")
        axis2 = FmtAxisItem(orientation="left")
        axis1.syncWith(axis2, left_spacing=True)
        axis2.syncWith(axis1, left_spacing=True)
        self.ui.widgetGraph1.setAxisItems(axisItems={"left": axis1})
        self.ui.widgetGraph2.setAxisItems(axisItems={"left": axis2})
        self.set_graph1_data(self.tr("电压"), skip_update=True)
        self.set_graph2_data(self.tr("电流"), skip_update=True)

    def update_pen(self):
        self.pen1.setColor(QtGui.QColor(setting.get_color("line1")))
        self.pen2.setColor(QtGui.QColor(setting.get_color("line2")))

    def get_data(self, text: str, display_pts: int, r_offset: int = 0):
        if text == self.tr("电压"):
            data = self.data.voltages[: self.data.update_count]
        elif text == self.tr("电流"):
            data = self.data.currents[: self.data.update_count]
        elif text == self.tr("功率"):
            data = self.data.powers[: self.data.update_count]
        elif text == self.tr("阻值"):
            data = self.data.resistances[: self.data.update_count]
            time = self.data.times[: self.data.update_count]
            # find indexs that != self.open_r
            indexs = np.where(data != self.open_r)[0]
            data = data[indexs]
            if data.size == 0:
                return None, None, None, None, None, None, None
            time = time[indexs]
            start_index = max(0, len(data) - display_pts - r_offset)
            to_index = len(data) - r_offset
            eval_data = data[start_index:to_index]
            return (
                data,
                time,
                start_index,
                to_index,
                np.max(eval_data),
                np.min(eval_data),
                np.mean(eval_data),
            )
        else:
            return None, None, None, None, None, None, None
        if data.size == 0:
            return None, None, None, None, None, None, None
        start_index = max(0, len(data) - display_pts - r_offset)
        to_index = len(data) - r_offset
        eval_data = data[start_index:to_index]
        return (
            data,
            self.data.times[: self.data.update_count],
            start_index,
            to_index,
            np.max(eval_data),
            np.min(eval_data),
            np.mean(eval_data),
        )

    _typename_dict = None

    _left_last = -1

    def on_horizontalSlider_sliderMoved(self, values):
        left = int(values[0])
        right = int(values[1])
        left_moved = left != self._left_last
        if right - left < setting.display_pts:
            if left_moved:
                right = min(
                    left + setting.display_pts, self.ui.horizontalSlider._maximum
                )
                if right - left < setting.display_pts:
                    left = max(right - setting.display_pts, 0)
            else:
                left = max(right - setting.display_pts, 0)
                if right - left < setting.display_pts:
                    right = min(
                        left + setting.display_pts, self.ui.horizontalSlider._maximum
                    )
            with signals_blocked(self.ui.horizontalSlider):
                self.ui.horizontalSlider.setValue((left, right))
        self._left_last = left

    def draw_graph(self):
        if self._typename_dict is None:
            self._typename_dict = {
                self.tr("电压"): "V",
                self.tr("电流"): "I",
                self.tr("功率"): "P",
                self.tr("阻值"): "R",
            }
        self.ui.labelFps.setText(f"{self.fps_counter.fps:.1f}Hz")
        if self.graph_keep_flag:
            return
        type1 = self.ui.comboGraph1Data.currentText()
        type2 = self.ui.comboGraph2Data.currentText()
        with self.data.sync_lock:
            update_count = self.data.update_count
            if update_count > setting.display_pts + 5:
                left, right = self.ui.horizontalSlider.sliderPosition()
                max_ = self.ui.horizontalSlider._maximum
                syncing = right == max_
                allfit = syncing and (left == 0)
                if not self.ui.horizontalSlider.isEnabled():
                    self.ui.horizontalSlider.setEnabled(True)
                    allfit = False
                    left = max(1, right - setting.display_pts)
                if allfit:
                    display_pts = update_count
                else:
                    display_pts = max(int(right) - int(left), setting.display_pts)
                if not syncing:
                    r_offset = update_count - int(right)
                else:
                    r_offset = 0
                right = update_count - r_offset
                if not allfit:
                    left = max(0, right - display_pts)
                else:
                    left = 0
                self.ui.horizontalSlider.setRange(0, update_count)
            else:
                display_pts = update_count
                r_offset = 0
                syncing = True
                allfit = False
                left = 0
                right = update_count
                self.ui.horizontalSlider.setEnabled(False)
                self.ui.horizontalSlider.setRange(0, 10)
            if syncing:
                self.ui.horizontalSlider.setValue((left, update_count))
            data1, time1, start_index1, to_index1, max1, min1, avg1 = self.get_data(
                type1, display_pts, r_offset
            )
            data2, time2, start_index2, to_index2, max2, min2, avg2 = self.get_data(
                type2, display_pts, r_offset
            )
        self.ui.labelBufferSize.setText(
            f"{update_count/self.data.data_length*100:.1f}%"
        )
        self.ui.labelBufferSize.setToolTip(
            self.tr("数据缓冲区占用率") + f"\n{update_count} / {self.data.data_length}"
        )
        self.ui.labelDisplayRange.setText(str(display_pts))
        if update_count > self.data.data_length * 0.95:
            set_color(
                self.ui.labelBufferSize,
                setting.get_color("general_yellow"),
            )

        _ = self._typename_dict.get(type1)
        if data1 is not None and data1.size > 0:
            self.curve1.setData(x=time1, y=data1)
            text1 = f"{_}avg: {float_str(avg1)}  {_}max: {float_str(max1)}  {_}min: {float_str(min1)}  {_}pp: {float_str(max1 - min1)}"
        else:
            self.curve1.setData(x=[], y=[])
            text1 = f"{_}avg: N/A  {_}max: N/A  {_}min: N/A  {_}pp: N/A"
        _ = self._typename_dict.get(type2)
        if data2 is not None and data2.size > 0:
            self.curve2.setData(x=time2, y=data2)
            text2 = f"{_}avg: {float_str(avg2)}  {_}max: {float_str(max2)}  {_}min: {float_str(min2)}  {_}pp: {float_str(max2 - min2)}"
        else:
            self.curve2.setData(x=[], y=[])
            text2 = f"{_}avg: N/A  {_}max: N/A  {_}min: N/A  {_}pp: N/A"
        if data1 is not None and data2 is not None:
            text = text1 + "  |  " + text2
        elif data1 is not None:
            text = text1
        elif data2 is not None:
            text = text2
        else:
            text = "No Info"
        self.ui.labelGraphInfo.setText(text)
        if self._graph_auto_scale_flag:
            if data1 is not None and time1.size != 0:
                if max1 != np.inf and min1 != -np.inf:
                    add1 = max(0.01, (max1 - min1) * 0.05)
                    self.ui.widgetGraph1.setYRange(min1 - add1, max1 + add1)
                    self.ui.widgetGraph1.setXRange(
                        time1[start_index1], time1[to_index1 - 1]
                    )
            if data2 is not None and time2.size != 0:
                if max2 != np.inf and min2 != -np.inf:
                    add2 = max(0.01, (max2 - min2) * 0.05)
                    self.ui.widgetGraph2.setYRange(min2 - add2, max2 + add2)
                    self.ui.widgetGraph2.setXRange(
                        time2[start_index2], time2[to_index2 - 1]
                    )

    def set_graph1_data(self, text, skip_update=False):
        if text == self.tr("无"):
            self.ui.widgetGraph1.hide()
            return
        self.ui.widgetGraph1.show()
        self.ui.widgetGraph1.setLabel("left", text, units=self._graph_units_dict[text])
        if not skip_update and self.draw_graph_timer.isActive():  # force update axis
            self.ui.widgetGraph1.setYRange(0, 0)
            self.ui.widgetGraph2.setYRange(0, 0)
            self.draw_graph()

    def set_graph2_data(self, text, skip_update=False):
        if text == self.tr("无"):
            self.ui.widgetGraph2.hide()
            return
        self.ui.widgetGraph2.show()
        self.ui.widgetGraph2.setLabel("left", text, units=self._graph_units_dict[text])
        if not skip_update and self.draw_graph_timer.isActive():
            self.ui.widgetGraph1.setYRange(0, 0)
            self.ui.widgetGraph2.setYRange(0, 0)
            self.draw_graph()

    @QtCore.pyqtSlot()
    def on_btnGraphClear_clicked(self, _=None, skip_confirm=False):
        if not skip_confirm and not CustomMessageBox.question(
            self,
            self.tr("警告"),
            self.tr("确定要清空数据缓冲区吗？"),
        ):
            return
        with self.data.sync_lock:
            self.data.voltages = np.zeros(self.data.data_length, np.float64)
            self.data.currents = np.zeros(self.data.data_length, np.float64)
            self.data.powers = np.zeros(self.data.data_length, np.float64)
            self.data.resistances = np.zeros(self.data.data_length, np.float64)
            self.data.times = np.zeros(self.data.data_length, np.float64)
            self.data.update_count = 0
            t = time.perf_counter()
            self.data.start_time = t
            self.data.last_time = t

        self.curve1.setData(x=[], y=[])
        self.curve2.setData(x=[], y=[])
        set_color(self.ui.labelBufferSize, None)

    @QtCore.pyqtSlot()
    def on_btnGraphKeep_clicked(self):
        self.graph_keep_flag = not self.graph_keep_flag
        if self.graph_keep_flag:
            self.ui.btnGraphKeep.setText(self.tr("解除"))
            self.ui.comboGraph1Data.setEnabled(False)
            self.ui.comboGraph2Data.setEnabled(False)
        else:
            self.ui.btnGraphKeep.setText(self.tr("保持"))
            self.ui.comboGraph1Data.setEnabled(True)
            self.ui.comboGraph2Data.setEnabled(True)
        mouse_enabled = self.graph_keep_flag or (not self._graph_auto_scale_flag)
        self.ui.frameGraphControl.setEnabled(not mouse_enabled)
        self.ui.widgetGraph1.setMouseEnabled(x=mouse_enabled, y=mouse_enabled)
        self.ui.widgetGraph2.setMouseEnabled(x=mouse_enabled, y=mouse_enabled)

    @QtCore.pyqtSlot()
    def on_btnGraphAutoScale_clicked(self):
        self._graph_auto_scale_flag = not self._graph_auto_scale_flag
        if self._graph_auto_scale_flag:
            self.ui.btnGraphAutoScale.setText(self.tr("适应"))
        else:
            self.ui.btnGraphAutoScale.setText(self.tr("手动"))
        mouse_enabled = self.graph_keep_flag or (not self._graph_auto_scale_flag)
        self.ui.frameGraphControl.setEnabled(not mouse_enabled)
        self.ui.widgetGraph1.setMouseEnabled(x=mouse_enabled, y=mouse_enabled)
        self.ui.widgetGraph2.setMouseEnabled(x=mouse_enabled, y=mouse_enabled)

    @QtCore.pyqtSlot()
    def on_btnGraphRecord_clicked(self):
        self.graph_record_flag = not self.graph_record_flag
        if self.graph_record_flag:
            self.graph_record_data = RecordData()
            time_str = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            self.graph_record_filename = os.path.join(
                ARG_PATH, f"record_{time_str}.csv"
            )
            self.ui.btnGraphRecord.setText(self.tr("停止"))
            self.graph_record_save_timer.start(30000)
        else:
            self.graph_record_save_timer.stop()
            self.graph_record_data.to_csv(self.graph_record_filename)
            self.graph_record_data = RecordData()

            CustomMessageBox(
                self,
                self.tr("录制完成"),
                self.tr("数据已保存至：")
                + f"\n{os.path.basename(self.graph_record_filename)}",
                additional_actions=[
                    (
                        self.tr("打开文件路径"),
                        partial(self._handle_open_filebase, self.graph_record_filename),
                    ),
                ],
            )
            self.ui.btnGraphRecord.setText(self.tr("录制"))

    @QtCore.pyqtSlot()
    def on_btnGraphDump_clicked(self):
        path, ok = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.tr("保存数据"),
            os.path.join(ARG_PATH, "mdp_buffer_dump.csv"),
            "CSV Files (*.csv)",
        )
        if not ok:
            return
        with self.data.sync_lock:
            voltages = self.data.voltages[: self.data.update_count]
            currents = self.data.currents[: self.data.update_count]
            powers = self.data.powers[: self.data.update_count]
            resistances = self.data.resistances[: self.data.update_count]
            times = self.data.times[: self.data.update_count]
            np.savetxt(
                path,
                np.c_[times, voltages, currents, powers, resistances],
                delimiter=",",
                header="time/s,voltage/V,current/A,power/W,resistance/ohm",
                comments="",
                fmt="%f",
            )
        CustomMessageBox(
            self,
            self.tr("保存完成"),
            self.tr("数据已保存至：") + f"\n{os.path.basename(path)}",
            additional_actions=[
                (
                    self.tr("打开文件路径"),
                    partial(self._handle_open_filebase, path),
                ),
            ],
        )

    def _handle_open_filebase(self, file):
        folder = os.path.dirname(file)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
        return True

    def graph_record_save(self):
        if self.graph_record_flag:
            self.graph_record_data.to_csv(self.graph_record_filename)
        else:
            self.graph_record_save_timer.stop()

    ######### 辅助功能-预设组 #########

    def set_preset(self, _):
        text = self.ui.comboPreset.currentText()
        if not text or not text[1].isdigit():
            return
        voltage, current = setting.presets[text[1]]
        self.v_set = voltage
        self.i_set = current
        self.ui.comboPreset.setCurrentIndex(0)

    def refresh_preset(self):
        idx = self.ui.comboPreset.currentIndex()
        self.ui.comboPreset.clear()
        self.ui.comboPreset.addItem("[>] " + self.tr("选择预设"))
        self.ui.comboPreset.addItems(
            [f"[{k}] {v[0]:06.3f}V {v[1]:06.3f}A" for k, v in setting.presets.items()]
        )
        self.ui.comboPreset.setCurrentIndex(idx)
        self.ui.comboPreset.setItemData(0, 0, QtCore.Qt.UserRole - 1)
        idx = self.ui.comboPresetEdit.currentIndex()
        self.ui.comboPresetEdit.clear()
        self.ui.comboPresetEdit.addItems(
            [f"Preset-{k}" for k, v in setting.presets.items()]
        )
        self.ui.comboPresetEdit.setCurrentIndex(idx)

    @QtCore.pyqtSlot()
    def on_btnPresetSave_clicked(self):
        preset = self.ui.comboPresetEdit.currentText()
        if not preset:
            return
        preset = preset.split("-")[1]
        v_set = self.ui.spinBoxPresetVoltage.value()
        i_set = self.ui.spinBoxPresetCurrent.value()
        try:
            setting.presets[preset] = [v_set, i_set]
            setting.save(SETTING_FILE)
            self.ui.btnPresetSave.setText(self.tr("保存成功"))
            self.refresh_preset()
        except Exception:
            logger.exception(self.tr("保存预设失败"))
            self.ui.btnPresetSave.setText(self.tr("保存失败"))
        QtCore.QTimer.singleShot(
            1000, lambda: self.ui.btnPresetSave.setText(self.tr("保存"))
        )

    def get_preset(self, text):
        if "-" not in text:
            return
        voltage, current = setting.presets[text.split("-")[1]]
        self.ui.spinBoxPresetVoltage.setValue(voltage)
        self.ui.spinBoxPresetCurrent.setValue(current)

    ######### 辅助功能-参数扫描 #########

    _sweep_response_type = ""
    _sweep_response_data_y = []
    _sweep_response_data_x = []
    _sweep_response_x_label = ""
    _sweep_response_y_label = ""
    _sweep_response_x_unit = ""
    _sweep_response_y_unit = ""
    _sweep_flag = False

    @QtCore.pyqtSlot()
    def on_btnSweep_clicked(self):
        if self.func_sweep_timer.isActive():
            self.stop_func_sweep()
        else:
            self._sweep_target = self.ui.comboSweepTarget.currentText()
            self._sweep_start = self.ui.spinBoxSweepStart.value()
            self._sweep_stop = self.ui.spinBoxSweepStop.value()
            self._sweep_step = self.ui.spinBoxSweepStep.value()
            self._sweep_delay = self.ui.spinBoxSweepDelay.value()
            try:
                assert self._sweep_step > 0
                assert self._sweep_start != self._sweep_stop
                assert self._sweep_delay > 0
            except Exception:
                self.ui.btnSweep.setText(self.tr("非法参数"))
                QtCore.QTimer.singleShot(
                    1000, lambda: self.ui.btnSweep.setText(self.tr("功能已关闭"))
                )
                return

            self._sweep_temp = None
            if self.ui.comboSweepRecord.currentIndex() == 0:
                self._sweep_response_type = ""
            else:
                self._sweep_response_type = self.ui.comboSweepRecord.currentText()
                units_dict = {
                    self.tr("电压"): "V",
                    self.tr("电流"): "A",
                    self.tr("功率"): "W",
                    self.tr("阻值"): "Ω",
                }
                self._sweep_response_x_label = self._sweep_target
                self._sweep_response_y_label = self._sweep_response_type
                self._sweep_response_x_unit = units_dict[self._sweep_target]
                self._sweep_response_y_unit = units_dict[self._sweep_response_type]
                self._sweep_response_data_x = []
                self._sweep_response_data_y = []

            self._sweep_flag = True
            self.ui.btnSweep.setText(self.tr("功能已开启"))
            if self._sweep_target == self.tr("电压"):
                self.ui.spinBoxVoltage.setEnabled(False)
            elif self._sweep_target == self.tr("电流"):
                self.ui.spinBoxCurrent.setEnabled(False)
            self.ui.scrollAreaSweep.setEnabled(False)

            def start_sweep():
                self.func_sweep_timer.start(round(self._sweep_delay * 1000))

            self.v_set = self._sweep_start
            self.wait_output_stable(start_sweep)

    @QtCore.pyqtSlot()
    def on_btnSweepShowRecord_clicked(self):
        if not self._sweep_response_type:
            CustomMessageBox(self, self.tr("错误"), self.tr("扫描响应记录为空"))
            return
        len_y = len(self._sweep_response_data_y)
        len_x = len(self._sweep_response_data_x)
        min_len = min(len_x, len_y)
        MainWindow.display_data_signal.emit(
            self._sweep_response_data_x[:min_len],
            self._sweep_response_data_y[:min_len],
            self._sweep_response_x_label,
            self._sweep_response_y_label,
            self._sweep_response_x_unit,
            self._sweep_response_y_unit,
            self.tr("扫描响应结果曲线"),
            False,
        )

    @QtCore.pyqtSlot(str)
    def on_comboSweepTarget_currentTextChanged(self, text):
        if text == self.tr("电压"):
            self.ui.spinBoxSweepStart.setSuffix("V")
            self.ui.spinBoxSweepStop.setSuffix("V")
            self.ui.spinBoxSweepStep.setSuffix("V")
            self.ui.spinBoxSweepStart.setRange(0, 30)
            self.ui.spinBoxSweepStop.setRange(0, 30)
            self.ui.spinBoxSweepStep.setRange(0.001, 30)
        elif text == self.tr("电流"):
            self.ui.spinBoxSweepStart.setSuffix("A")
            self.ui.spinBoxSweepStop.setSuffix("A")
            self.ui.spinBoxSweepStep.setSuffix("A")
            self.ui.spinBoxSweepStart.setRange(0, 10)
            self.ui.spinBoxSweepStop.setRange(0, 10)
            self.ui.spinBoxSweepStep.setRange(0.001, 10)

    def stop_func_sweep(self):
        self.func_sweep_timer.stop()
        self.ui.btnSweep.setText(self.tr("功能已关闭"))
        if self._sweep_target == self.tr("电压"):
            self.ui.spinBoxVoltage.setEnabled(True)
        elif self._sweep_target == self.tr("电流"):
            self.ui.spinBoxCurrent.setEnabled(True)
        self.ui.scrollAreaSweep.setEnabled(True)

    def func_sweep(self):
        if self._sweep_response_type:
            _data_sources = {
                self.tr("电压"): self.data.voltages,
                self.tr("电流"): self.data.currents,
                self.tr("功率"): self.data.powers,
                self.tr("阻值"): self.data.resistances,
            }
            self._sweep_response_data_x.append(
                _data_sources[self._sweep_response_x_label][self.data.update_count - 1]
            )
            self._sweep_response_data_y.append(
                _data_sources[self._sweep_response_y_label][self.data.update_count - 1]
            )

        if not self._sweep_flag:
            self.stop_func_sweep()
            return

        if self._sweep_temp is None:
            self._sweep_temp = self._sweep_start
        else:
            if self._sweep_start <= self._sweep_stop:
                self._sweep_temp += self._sweep_step
            else:
                self._sweep_temp -= self._sweep_step

        if (
            self._sweep_start > self._sweep_stop
            and self._sweep_temp <= self._sweep_stop
        ) or (
            self._sweep_start <= self._sweep_stop
            and self._sweep_temp >= self._sweep_stop
        ):
            self._sweep_temp = self._sweep_stop
            self._sweep_flag = False
            self.stop_func_sweep()

        if self._sweep_target == self.tr("电压"):
            self.v_set = self._sweep_temp
        elif self._sweep_target == self.tr("电流"):
            self.i_set = self._sweep_temp

    ######### 辅助功能-发生器 #########

    @QtCore.pyqtSlot()
    def on_btnWaveGen_clicked(self):
        if self.func_wave_gen_timer.isActive():
            self.stop_func_wave_gen()
        else:
            self._wavegen_type = self.ui.comboWaveGenType.currentText()
            self._wavegen_period = self.ui.spinBoxWaveGenPeriod.value()
            self._wavegen_highlevel = self.ui.spinBoxWaveGenHigh.value()
            self._wavegen_lowlevel = self.ui.spinBoxWaveGenLow.value()
            self._wavegen_loopfreq = self.ui.spinBoxWaveGenLoopFreq.value()
            try:
                assert self._wavegen_highlevel > self._wavegen_lowlevel
                assert self._wavegen_period > 0
                assert self._wavegen_loopfreq > 0
            except Exception:
                self.ui.btnWaveGen.setText(self.tr("非法参数"))
                QtCore.QTimer.singleShot(
                    1000, lambda: self.ui.btnWaveGen.setText(self.tr("功能已关闭"))
                )
                return
            self.ui.btnWaveGen.setText(self.tr("功能已开启"))
            self.ui.spinBoxWaveGenLoopFreq.setEnabled(False)
            self.ui.spinBoxVoltage.setEnabled(False)
            self._wavegen_start_time = 0

            def start_wave_gen():
                self._wavegen_start_time = time.perf_counter()
                self.func_wave_gen_timer.start(round(1000 / self._wavegen_loopfreq))
                self.v_set = self._wavegen_lowlevel

            self.v_set = self._wavegen_lowlevel
            self.wait_output_stable(start_wave_gen)

    def stop_func_wave_gen(self):
        self.func_wave_gen_timer.stop()
        self.ui.btnWaveGen.setText(self.tr("功能已关闭"))
        self.ui.spinBoxWaveGenLoopFreq.setEnabled(True)
        self.ui.spinBoxVoltage.setEnabled(True)

    def set_wavegen_type(self, _):
        self._wavegen_type = self.ui.comboWaveGenType.currentText()

    @QtCore.pyqtSlot()
    def on_spinBoxWaveGenPeriod_editingFinished(self):
        self._wavegen_period = self.ui.spinBoxWaveGenPeriod.value()

    @QtCore.pyqtSlot()
    def on_spinBoxWaveGenHigh_editingFinished(self):
        self._wavegen_highlevel = self.ui.spinBoxWaveGenHigh.value()

    @QtCore.pyqtSlot()
    def on_spinBoxWaveGenLow_editingFinished(self):
        self._wavegen_lowlevel = self.ui.spinBoxWaveGenLow.value()

    def func_wave_gen(self):
        t = time.perf_counter() - self._wavegen_start_time
        if self._wavegen_type == self.tr("正弦波"):
            voltage = (
                self._wavegen_lowlevel
                + (self._wavegen_highlevel - self._wavegen_lowlevel)
                * (math.sin(2 * math.pi / self._wavegen_period * t) + 1.0)
                / 2
            )
        elif self._wavegen_type == self.tr("方波"):
            voltage = (
                self._wavegen_highlevel
                if math.sin(2 * math.pi / self._wavegen_period * t) > 0
                else self._wavegen_lowlevel
            )
        elif self._wavegen_type == self.tr("三角波"):
            mul = (t / self._wavegen_period) % 2
            mul = mul if mul < 1 else 2 - mul
            voltage = (
                self._wavegen_lowlevel
                + (self._wavegen_highlevel - self._wavegen_lowlevel) * mul
            )
        elif self._wavegen_type == self.tr("锯齿波"):
            voltage = (self._wavegen_highlevel - self._wavegen_lowlevel) * (
                (t / self._wavegen_period) % 1
            ) + self._wavegen_lowlevel
        elif self._wavegen_type == self.tr("噪音"):
            voltage = random.uniform(self._wavegen_lowlevel, self._wavegen_highlevel)
        else:
            voltage = 0
        voltage = max(
            min(voltage, self._wavegen_highlevel), self._wavegen_lowlevel
        )  # 限幅
        self.v_set = voltage

    ######### 辅助功能-功率保持 #########

    @QtCore.pyqtSlot()
    def on_btnKeepPower_clicked(self):
        if self.func_keep_power_timer.isActive():
            self.stop_func_keep_power()
        else:
            self._keep_power_target = self.ui.spinBoxKeepPowerSet.value()
            self._keep_power_loopfreq = self.ui.spinBoxKeepPowerLoopFreq.value()
            self._keep_power_pid_i = self.ui.spinBoxKeepPowerPi.value()
            self._keep_power_pid_max_v = self.ui.spinBoxKeepPowerMaxV.value()
            try:
                assert self._keep_power_loopfreq > 0
                assert self._keep_power_pid_i > 0
            except Exception:
                self.ui.btnKeepPower.setText(self.tr("非法参数"))
                QtCore.QTimer.singleShot(
                    1000, lambda: self.ui.btnKeepPower.setText(self.tr("功能已关闭"))
                )
                return
            self._keep_power_pid = PID(
                0,
                self._keep_power_pid_i,
                0,
                setpoint=self._keep_power_target,
                auto_mode=False,
            )
            self._keep_power_pid.output_limits = (0, self._keep_power_pid_max_v)
            self._keep_power_pid.set_auto_mode(True, last_output=self.v_set)
            self.func_keep_power_timer.start(round(1000 / self._keep_power_loopfreq))
            self.ui.btnKeepPower.setText(self.tr("功能已开启"))
            self.ui.spinBoxVoltage.setEnabled(False)
            self.ui.spinBoxKeepPowerLoopFreq.setEnabled(False)

    def stop_func_keep_power(self):
        self.func_keep_power_timer.stop()
        self.ui.btnKeepPower.setText(self.tr("功能已关闭"))
        self.ui.spinBoxVoltage.setEnabled(True)
        self.ui.spinBoxKeepPowerLoopFreq.setEnabled(True)

    def func_keep_power(self):
        if not self.output_state:
            if self._keep_power_pid.auto_mode:
                self._keep_power_pid.set_auto_mode(False)
            voltage = 0
        else:
            if not self._keep_power_pid.auto_mode:
                self._keep_power_pid.set_auto_mode(True, last_output=self.v_set)
            voltage = self._keep_power_pid(self.data.powers[self.data.update_count - 1])
        self.v_set = voltage

    @QtCore.pyqtSlot()
    def on_spinBoxKeepPowerSet_editingFinished(self):
        self._keep_power_target = self.ui.spinBoxKeepPowerSet.value()
        if self.func_keep_power_timer.isActive():
            self._keep_power_pid.setpoint = self._keep_power_target

    @QtCore.pyqtSlot()
    def on_spinBoxKeepPowerPi_editingFinished(self):
        self._keep_power_pid_i = self.ui.spinBoxKeepPowerPi.value()
        if self.func_keep_power_timer.isActive():
            self._keep_power_pid.tunings = (0, self._keep_power_pid_i, 0)

    @QtCore.pyqtSlot()
    def on_spinBoxKeepPowerMaxV_editingFinished(self):
        self._keep_power_pid_max_v = self.ui.spinBoxKeepPowerMaxV.value()
        if self.func_keep_power_timer.isActive():
            self._keep_power_pid.output_limits = (0, self._keep_power_pid_max_v)

    ######### 辅助功能-电池模拟 #########

    _battery_models = {}
    _bat_sim_soc = []
    _bat_sim_voltage = []
    _bat_sim_total_energy = 0
    _bat_sim_used_energy = 0
    _bat_sim_stop_energy = 0
    _bat_sim_cells = 1
    _bat_sim_internal_r = 0.0
    _bat_sim_last_e_temp = 0
    _bat_sim_start_time = 0

    def load_battery_model(self, path):
        csv = np.loadtxt(path, delimiter=",", skiprows=1)
        csv_name = os.path.basename(os.path.splitext(path)[0])
        soc = csv[:, 0]
        voltage = csv[:, 1]
        self._battery_models[csv_name] = (soc, voltage)
        if csv_name not in [
            self.ui.comboBatSimCurve.itemText(i)
            for i in range(self.ui.comboBatSimCurve.count())
        ]:
            self.ui.comboBatSimCurve.addItem(csv_name)
        self.ui.comboBatSimCurve.setCurrentText(csv_name)

    @QtCore.pyqtSlot()
    def on_btnBatSimLoad_clicked(self):
        path, ok = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("打开"), "", self.tr("CSV文件 (*.csv)")
        )
        if path == "" or not ok:
            return
        self.load_battery_model(path)

    @QtCore.pyqtSlot()
    def on_btnBatSimPreview_clicked(self):
        curve_name = self.ui.comboBatSimCurve.currentText()
        if curve_name not in self._battery_models:
            return
        soc, voltage = self._battery_models[curve_name]
        new_soc = np.arange(0, 100 + 1e-9, 0.1)
        new_voltage = np.interp(new_soc, soc, voltage)
        self.display_data_signal.emit(
            new_soc.tolist(),
            new_voltage.tolist(),
            self.tr("SOC"),
            self.tr("电压"),
            "%",
            "V",
            f"{curve_name} Voltage-SOC (State of Charge) Curve",
            True,
        )

    def set_batsim_widget_enabled(self, enabled):
        for item in self.ui.scrollAreaBatSim.findChildren(QtWidgets.QPushButton):
            if item is not self.ui.btnBatSimPreview:
                item.setEnabled(enabled)
        for item in self.ui.scrollAreaBatSim.findChildren(QtWidgets.QDoubleSpinBox):
            item.setEnabled(enabled)
        for item in self.ui.scrollAreaBatSim.findChildren(QtWidgets.QComboBox):
            item.setEnabled(enabled)

    def stop_func_bat_sim(self):
        self.func_bat_sim_timer.stop()
        self.set_batsim_widget_enabled(True)
        self.ui.btnBatSim.setText(self.tr("功能已关闭"))

    @QtCore.pyqtSlot()
    def on_btnBatSim_clicked(self):
        if self.func_bat_sim_timer.isActive():
            self.stop_func_bat_sim()
        else:
            curve_name = self.ui.comboBatSimCurve.currentText()
            if curve_name not in self._battery_models:
                return
            self._bat_sim_soc = self._battery_models[curve_name][0]
            self._bat_sim_voltage = self._battery_models[curve_name][1]
            self._bat_sim_cells = self.ui.spinBoxBatSimCells.value()
            self._bat_sim_total_energy = (
                self.ui.spinBoxBatSimCap.value() * 3600 * self._bat_sim_cells
            )  # Wh->J
            self._bat_sim_used_energy = (
                1 - self.ui.spinBoxBatSimCurrent.value() / 100
            ) * self._bat_sim_total_energy
            self._bat_sim_stop_energy = self._bat_sim_total_energy - (
                self.ui.spinBoxBatSimStop.value() / 100 * self._bat_sim_total_energy
            )
            self._bat_sim_internal_r = (
                self.ui.spinBoxBatSimRes.value() / 1000
            )  # mOhm->Ohm
            self._bat_sim_last_e_temp = self.continuous_energy_counter
            self.ui.labelBatSimTime.setText("Discharge Time: 00:00:00")
            self.ui.btnBatSim.setText(self.tr("功能已开启"))
            self.set_batsim_widget_enabled(False)
            self.display_data_signal.emit(
                self._bat_sim_soc.tolist(),
                self._bat_sim_voltage.tolist(),
                self.tr("SOC"),
                self.tr("电压"),
                "%",
                "V",
                f"{curve_name} Battery Simulation Real-Time Curve",
                True,
            )

            def start_bat_sim():
                self.func_bat_sim_timer.start(
                    round(1000 / self.ui.spinBoxBatSimLoopFreq.value())
                )
                self._bat_sim_start_time = time.perf_counter()

            self.v_set = 0
            self.wait_output_stable(start_bat_sim)

    def func_bat_sim(self):
        add_e = self.continuous_energy_counter - self._bat_sim_last_e_temp
        self._bat_sim_last_e_temp += add_e
        self._bat_sim_used_energy += add_e
        if self._bat_sim_used_energy >= self._bat_sim_stop_energy:
            self.output_state = False
            self.on_btnBatSim_clicked()
        new_percent = (
            (self._bat_sim_total_energy - self._bat_sim_used_energy)
            / self._bat_sim_total_energy
            * 100
        )
        self.ui.spinBoxBatSimCurrent.setValue(new_percent)
        new_volt = np.interp(new_percent, self._bat_sim_soc, self._bat_sim_voltage)
        self.v_set = (
            new_volt
            - self._bat_sim_internal_r * self.data.currents[self.data.update_count - 1]
        ) * self._bat_sim_cells
        self.highlight_point_signal.emit(new_percent, new_volt)
        self.ui.labelBatSimTime.setText(
            "Discharge Time: "
            + time.strftime(
                "%H:%M:%S", time.gmtime(time.perf_counter() - self._bat_sim_start_time)
            )
        )

    ######### 辅助功能-序列 #########

    def seq_btn_disable(self):
        self.ui.btnSeqSave.hide()
        self.ui.btnSeqLoad.hide()
        self.ui.btnSeqSingle.hide()
        self.ui.btnSeqLoop.hide()
        self.ui.btnSeqDelay.hide()
        self.ui.btnSeqWaitTime.hide()
        self.ui.btnSeqVoltage.hide()
        self.ui.btnSeqCurrent.hide()
        self.ui.listSeq.setEnabled(False)
        self.ui.btnSeqStop.show()

    def seq_btn_enable(self):
        self.ui.btnSeqSave.show()
        self.ui.btnSeqLoad.show()
        self.ui.btnSeqSingle.show()
        self.ui.btnSeqLoop.show()
        self.ui.btnSeqDelay.show()
        self.ui.btnSeqWaitTime.show()
        self.ui.btnSeqVoltage.show()
        self.ui.btnSeqCurrent.show()
        self.ui.listSeq.setEnabled(True)
        self.ui.btnSeqStop.hide()

    @QtCore.pyqtSlot()
    def on_btnSeqSingle_clicked(self):
        cnt = self.ui.listSeq.count()
        if cnt == 0:
            return
        self.seq_btn_disable()
        self.start_seq(loop=False)
        if not self.output_state:
            self.ui.btnOutput.click()

    @QtCore.pyqtSlot()
    def on_btnSeqLoop_clicked(self):
        cnt = self.ui.listSeq.count()
        if cnt == 0:
            return
        self.seq_btn_disable()
        self.start_seq(loop=True)
        if not self.output_state:
            self.ui.btnOutput.click()

    @QtCore.pyqtSlot()
    def on_btnSeqStop_clicked(self):
        self.func_seq_timer.stop()
        self.seq_btn_enable()

    # listSeq 删除
    def seq_del_item(self):
        row = self.ui.listSeq.currentRow()
        cnt = self.ui.listSeq.count()
        if cnt == 0:
            return
        if row == -1:
            row = cnt - 1
        self.ui.listSeq.takeItem(row)
        self.ui.listSeq.setCurrentRow(max(row - 1, 0))

    def seq_edit_item(self):
        row = self.ui.listSeq.currentRow()
        cnt = self.ui.listSeq.count()
        if cnt == 0:
            return
        if row == -1:
            return
        item = self.ui.listSeq.item(row)
        text = item.text()
        if text.split()[0] == "DELAY":
            delay, ok = CustomInputDialog.getInt(
                self,
                self.tr("编辑动作"),
                self.tr("请输入延时时间:"),
                default_value=int(text.split()[1]),
                min_value=0,
                max_value=100000,
                step=1,
                suffix="ms",
            )
            if not ok:
                return
            item.setText(f"DELAY {delay} ms")
        elif text.split()[0] == "WAIT":
            default_value = QtCore.QDateTime.fromString(
                " ".join(text.split()[1:]), "%Y-%m-%d %H:%M:%S"
            )
            wait_time, ok = CustomInputDialog.getDateTime(
                self,
                self.tr("编辑动作"),
                self.tr("请输入等待时间:"),
                default_value=default_value,
            )
            if not ok:
                return
            item.setText(f"WAIT  {wait_time.toString('yyyy-MM-dd HH:mm:ss')}")
        elif text.split()[0] == "SET-V":
            voltage, ok = CustomInputDialog.getDouble(
                self,
                self.tr("编辑动作"),
                self.tr("请输入电压值:"),
                default_value=float(text.split()[1]),
                min_value=0,
                max_value=30,
                step=0.001,
                decimals=3,
                suffix="V",
            )
            if not ok:
                return
            item.setText(f"SET-V {voltage:.3f} V")
        elif text.split()[0] == "SET-I":
            current, ok = CustomInputDialog.getDouble(
                self,
                self.tr("编辑动作"),
                self.tr("请输入电流值:"),
                default_value=float(text.split()[1]),
                min_value=0,
                max_value=10,
                step=0.001,
                decimals=3,
                suffix="A",
            )
            if not ok:
                return
            item.setText(f"SET-I {current:.3f} A")
        else:
            CustomMessageBox(
                self,
                self.tr("错误"),
                self.tr("无法识别动作"),
            )

    def seq_clear_all(self):
        if CustomMessageBox.question(
            self,
            self.tr("警告"),
            self.tr("确定要清空序列吗？"),
        ):
            self.ui.listSeq.clear()

    # listSeq 右键菜单 (listSeq)
    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_listSeq_customContextMenuRequested(self, pos):
        row = self.ui.listSeq.currentRow()
        cnt = self.ui.listSeq.count()
        if cnt == 0:
            return
        if row == -1:
            return
        menu = QtWidgets.QMenu()
        menu.addAction(self.tr("编辑"), lambda: self.seq_edit_item())
        menu.addAction(self.tr("删除"), lambda: self.seq_del_item())
        menu.addAction(self.tr("清空"), lambda: self.seq_clear_all())
        menu.exec_(QtGui.QCursor.pos())

    # 双击修改
    @QtCore.pyqtSlot(QtWidgets.QListWidgetItem)
    def on_listSeq_itemDoubleClicked(self, item):
        self.seq_edit_item()

    def seq_set_item_font(self, index):
        item = self.ui.listSeq.item(index)
        sfont = QtGui.QFont()
        sfont.setFamily("Sarasa Fixed SC SemiBold")
        sfont.setPointSize(10)
        item.setFont(sfont)

    @QtCore.pyqtSlot()
    def on_btnSeqDelay_clicked(self):
        row = self.ui.listSeq.currentRow()
        delay, ok = CustomInputDialog.getInt(
            self,
            self.tr("添加动作"),
            self.tr("请输入延时时间:"),
            default_value=1000,
            min_value=0,
            max_value=100000,
            step=1,
            suffix="ms",
        )
        if not ok:
            return
        self.ui.listSeq.insertItem(row + 1, f"DELAY {delay} ms")
        self.ui.listSeq.setCurrentRow(row + 1)
        self.seq_set_item_font(row + 1)

    @QtCore.pyqtSlot()
    def on_btnSeqWaitTime_clicked(self):
        row = self.ui.listSeq.currentRow()
        wait_time, ok = CustomInputDialog.getDateTime(
            self,
            self.tr("添加动作"),
            self.tr("请输入等待时间:") + "\n" + self.tr("格式: 年-月-日 时:分:秒"),
        )
        if not ok:
            return
        wait_time_str = wait_time.toString("yyyy-MM-dd HH:mm:ss")
        self.ui.listSeq.insertItem(row + 1, f"WAIT  {wait_time_str}")
        self.ui.listSeq.setCurrentRow(row + 1)
        self.seq_set_item_font(row + 1)

    @QtCore.pyqtSlot()
    def on_btnSeqVoltage_clicked(self):
        row = self.ui.listSeq.currentRow()
        voltage, ok = CustomInputDialog.getDouble(
            self,
            self.tr("添加动作"),
            self.tr("请输入电压值:"),
            default_value=5,
            min_value=0,
            max_value=30,
            step=0.001,
            decimals=3,
            suffix="V",
        )
        if not ok:
            return
        self.ui.listSeq.insertItem(row + 1, f"SET-V {voltage:.3f} V")
        self.ui.listSeq.setCurrentRow(row + 1)
        self.seq_set_item_font(row + 1)

    @QtCore.pyqtSlot()
    def on_btnSeqCurrent_clicked(self):
        row = self.ui.listSeq.currentRow()
        current, ok = CustomInputDialog.getDouble(
            self,
            self.tr("添加动作"),
            self.tr("请输入电流值:"),
            default_value=1,
            min_value=0,
            max_value=10,
            step=0.001,
            decimals=3,
            suffix="A",
        )
        if not ok:
            return
        self.ui.listSeq.insertItem(row + 1, f"SET-I {current:.3f} A")
        self.ui.listSeq.setCurrentRow(row + 1)
        self.seq_set_item_font(row + 1)

    def switch_to_seq(self, index) -> bool:
        if index > self._seq_cnt:
            return False
        item = self.ui.listSeq.item(index)
        if item is None:
            return False
        self._seq_index = index
        self.ui.listSeq.setCurrentRow(index)
        text = item.text()
        self._seq_type = text.split()[0]
        if self._seq_type == "WAIT":
            self._seq_value = datetime.datetime.strptime(
                " ".join(text.split()[1:]), "%Y-%m-%d %H:%M:%S"
            )
        else:
            self._seq_value = float(text.split()[1])
        if self._seq_type in ("DELAY", "WAIT") or self._seq_index == 0:
            self._seq_time = time.perf_counter()
        return True

    def stop_func_seq(self):
        self.func_seq_timer.stop()
        self.seq_btn_enable()

    def start_seq(self, loop=False):
        self._seq_loop = loop
        self._seq_index = 0
        self._seq_cnt = self.ui.listSeq.count()
        self.switch_to_seq(0)
        self.func_seq_timer.start(1)

    def func_seq(self):
        now = time.perf_counter()
        if self._seq_type == "DELAY":
            if now - self._seq_time < self._seq_value / 1000:
                return
        elif self._seq_type == "WAIT":
            now = datetime.datetime.now()
            if now < self._seq_value:
                return
        elif self._seq_type == "SET-V":
            self.v_set = self._seq_value
        elif self._seq_type == "SET-I":
            self.i_set = self._seq_value
        else:
            raise ValueError("Unknown seq type")
        if not self.switch_to_seq(self._seq_index + 1):
            if self._seq_loop:
                self.switch_to_seq(0)
            else:
                self.func_seq_timer.stop()
                self.seq_btn_enable()

    @QtCore.pyqtSlot()
    def on_btnSeqSave_clicked(self):
        if self.ui.listSeq.count() == 0:
            return
        # 保存到文件
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, self.tr("保存"), "", self.tr("文本文件 (*.txt)")
        )
        if filename == "" or filename is None:
            return
        lines = []
        for i in range(self.ui.listSeq.count()):
            lines.append(self.ui.listSeq.item(i).text())
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    @QtCore.pyqtSlot()
    def on_btnSeqLoad_clicked(self):
        # 从文件加载

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("打开"), "", self.tr("文本文件 (*.txt)")
        )

        if filename == "" or filename is None:
            return
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
        self.ui.listSeq.clear()
        for line in lines:
            try:
                _ = line.split(" ")
                assert len(_) == 3
                assert _[0] in ["WAIT", "DELAY", "SET-V", "SET-I"]
                if _[0] != "WAIT":
                    assert _[2] in ["ms", "V", "A"]
                    float(_[1])
                self.ui.listSeq.addItem(line)
                self.seq_set_item_font(self.ui.listSeq.count() - 1)
            except Exception:
                CustomMessageBox(
                    self, self.tr("错误"), self.tr("数据验证错误: ") + f"{line}"
                )
                return


MainWindow = MDPMainwindow()


class MDPSettings(QtWidgets.QDialog, FramelessWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.ui = Ui_DialogSettings()
        self.ui.setupUi(self)
        self.CustomTitleBar = CustomTitleBar(self, self.tr("连接设置"))
        self.CustomTitleBar.set_theme("dark")
        self.CustomTitleBar.set_allow_double_toggle_max(False)
        self.CustomTitleBar.set_min_btn_enabled(False)
        self.CustomTitleBar.set_max_btn_enabled(False)
        self.CustomTitleBar.set_full_btn_enabled(False)
        self.CustomTitleBar.set_close_btn_enabled(False)
        self.setTitleBar(self.CustomTitleBar)
        # self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        for lineedit in [
            self.ui.lineEditAddr1,
            self.ui.lineEditAddr2,
            self.ui.lineEditAddr3,
            self.ui.lineEditAddr4,
            self.ui.lineEditAddr5,
            self.ui.lineEditColor,
            self.ui.lineEditIdcode,
        ]:
            lineedit.textChanged.connect(
                lambda t=None, le=lineedit: self.check_hex_input(le)
            )

    def check_hex_input(self, lineedit: QtWidgets.QLineEdit):
        text = lineedit.text()
        new_text = ""
        for char in text:
            if char in "0123456789ABCDEFabcdef":
                new_text += char.upper()
            else:
                new_text += ""
        lineedit.setText(new_text)

    def initValues(self):
        self.ui.spinBoxBaud.setValue(setting.baudrate)
        self.ui.lineEditAddr1.setText(setting.address.split(":")[0])
        self.ui.lineEditAddr2.setText(setting.address.split(":")[1])
        self.ui.lineEditAddr3.setText(setting.address.split(":")[2])
        self.ui.lineEditAddr4.setText(setting.address.split(":")[3])
        self.ui.lineEditAddr5.setText(setting.address.split(":")[4])
        self.ui.spinBoxFreq.setValue(setting.freq)
        self.ui.comboBoxPower.setCurrentText(setting.txpower)
        self.ui.lineEditIdcode.setText(setting.idcode)
        self.ui.lineEditColor.setText(setting.color)
        self.ui.spinBoxM01.setValue(int(setting.m01ch[3]))
        self.ui.comboBoxPort.setCurrentText(
            setting.comport if setting.comport else self.tr("自动")
        )
        self.ui.comboBoxBlink.setCurrentText(
            self.tr("闪烁") if setting.blink else self.tr("常亮")
        )
        self.ui.checkBoxOutputWarn.setChecked(setting.output_warning)
        self.ui.checkBoxSetLock.setChecked(setting.lock_when_output)
        self.ui.checkBoxIgnoreHWLock.setChecked(setting.ignore_hw_lock)

    def refreshPorts(self):
        self.ui.comboBoxPort.clear()
        self.ui.comboBoxPort.addItem(self.tr("自动"))
        ports = []
        for port in comports():
            self.ui.comboBoxPort.addItem(port.name)
            ports.append(port.name)
        if setting.comport not in ports:
            self.ui.comboBoxPort.setCurrentText(self.tr("自动"))
        else:
            self.ui.comboBoxPort.setCurrentText(setting.comport)

    @QtCore.pyqtSlot()
    def on_btnMatch_clicked(self):
        if MainWindow.api is not None:
            CustomMessageBox(self, self.tr("错误"), self.tr("请先断开连接"))
            return
        self.save_settings()
        try:
            color_rgb = bytes.fromhex(setting.color.lstrip("#"))
            api = MDP_P906(
                port=setting.comport,
                baudrate=setting.baudrate,
                address=setting.address,
                freq=int(setting.freq),
                blink=setting.blink,
                idcode=setting.idcode,
                led_color=(color_rgb[0], color_rgb[1], color_rgb[2]),
                m01_channel=int(setting.m01ch[3]),
                tx_output_power=setting.txpower,
                debug=DEBUG,
            )
            idcode = api.auto_match()
        except Exception as e:
            logger.exception(self.tr("自动配对失败"))
            CustomMessageBox(self, self.tr("自动配对失败"), str(e))
            try:
                api.close()
            except Exception:
                pass
            return
        api.close()
        CustomMessageBox(self, self.tr("自动配对成功"), f"IDCODE: {idcode}")
        self.ui.lineEditIdcode.setText(idcode)
        self.save_settings()

    def show(self) -> None:
        self.initValues()
        self.refreshPorts()
        self.ui.lineEditColorIndicator.setStyleSheet(
            f"background-color: #{setting.color.lstrip('#')}"
        )
        center_window(self)
        super().show()

    @QtCore.pyqtSlot()
    def on_lineEditColor_editingFinished(self):
        color = self.ui.lineEditColor.text().lstrip("#")
        try:
            _ = bytes.fromhex(color)
            self.ui.lineEditColorIndicator.setStyleSheet(f"background-color: #{color}")
        except Exception:
            CustomMessageBox(
                self,
                self.tr("颜色格式错误"),
                self.tr("请输入16进制RGB颜色代码(例如: 66CCFF)"),
            )
            self.ui.lineEditColor.setText(setting.color)

    def save_settings(self):
        setting.baudrate = int(self.ui.spinBoxBaud.value())
        setting.address = ":".join(
            [
                self.ui.lineEditAddr1.text(),
                self.ui.lineEditAddr2.text(),
                self.ui.lineEditAddr3.text(),
                self.ui.lineEditAddr4.text(),
                self.ui.lineEditAddr5.text(),
            ]
        )
        setting.freq = int(self.ui.spinBoxFreq.value())
        setting.txpower = self.ui.comboBoxPower.currentText()
        setting.idcode = self.ui.lineEditIdcode.text()
        setting.color = self.ui.lineEditColor.text()
        setting.m01ch = f"CH-{int(self.ui.spinBoxM01.value())}"
        setting.comport = (
            self.ui.comboBoxPort.currentText()
            if self.ui.comboBoxPort.currentText() != self.tr("自动")
            else ""
        )
        setting.blink = self.ui.comboBoxBlink.currentText() == self.tr("闪烁")
        setting.output_warning = self.ui.checkBoxOutputWarn.isChecked()
        setting.lock_when_output = self.ui.checkBoxSetLock.isChecked()
        setting.ignore_hw_lock = self.ui.checkBoxIgnoreHWLock.isChecked()
        setting.save(SETTING_FILE)

    @QtCore.pyqtSlot()
    def on_btnSave_clicked(self):
        self.save_settings()
        self.ui.btnSave.setText(self.tr("重新连接生效"))
        QtCore.QTimer.singleShot(1000, self._reset_btn_text)

    def _reset_btn_text(self):
        self.ui.btnSave.setText(self.tr("应用 / Apply"))

    @QtCore.pyqtSlot()
    def on_btnOk_clicked(self):
        self.save_settings()
        self.close()

    @QtCore.pyqtSlot(int)
    def on_checkBoxIgnoreHWLock_stateChanged(self, state: int):
        setting.ignore_hw_lock = state == QtCore.Qt.CheckState.Checked

    @QtCore.pyqtSlot(int)
    def on_checkBoxSetLock_stateChanged(self, state: int):
        setting.lock_when_output = state == QtCore.Qt.CheckState.Checked

    @QtCore.pyqtSlot(int)
    def on_checkBoxOutputWarn_stateChanged(self, state: int):
        setting.output_warning = state == QtCore.Qt.CheckState.Checked


class MDPGraphics(QtWidgets.QDialog, FramelessWindow):
    set_max_fps_sig = QtCore.pyqtSignal(float)
    state_fps_sig = QtCore.pyqtSignal(float)
    set_data_len_sig = QtCore.pyqtSignal(int)
    set_interp_sig = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_DialogGraphics()
        self.ui.setupUi(self)
        self.CustomTitleBar = CustomTitleBar(self, self.tr("图形设置"))
        self.CustomTitleBar.set_theme("dark")
        self.CustomTitleBar.set_allow_double_toggle_max(False)
        self.CustomTitleBar.set_min_btn_enabled(False)
        self.CustomTitleBar.set_max_btn_enabled(False)
        self.CustomTitleBar.set_full_btn_enabled(False)
        self.CustomTitleBar.set_close_btn_enabled(False)
        self.setTitleBar(self.CustomTitleBar)
        # self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        if NUMBA_ENABLED:
            self.ui.labelNumba.setVisible(True)
        else:
            self.ui.labelNumba.setVisible(False)

        if not OPENGL_AVALIABLE:
            self.ui.checkBoxOpenGL.setEnabled(False)
            self.ui.checkBoxOpenGL.setChecked(False)

        for k in setting.color_palette:
            if k not in ("dark", "light", "modify_this_to_add_your_custom_theme"):
                self.ui.comboTheme.addItem(k)

    def initValues(self):
        self.ui.spinMaxFps.setValue(setting.graph_max_fps)
        self.ui.spinStateFps.setValue(setting.state_fps)
        self.ui.spinDataLength.setValue(setting.data_pts)
        self.ui.spinDisplayLength.setMaximum(setting.data_pts)
        self.ui.spinDisplayLength.setValue(setting.display_pts)
        self.ui.comboInterp.setCurrentIndex(setting.interp)
        self.ui.comboAvgMode.setCurrentIndex(setting.avgmode)
        self.ui.spinStateVThres.setValue(setting.v_threshold)
        self.ui.spinStateIThres.setValue(setting.i_threshold)
        self.ui.checkBoxUseCali.setChecked(setting.use_cali)
        self.ui.spinCaliVk.setValue(setting.v_cali_k)
        self.ui.spinCaliVb.setValue(setting.v_cali_b)
        self.ui.spinCaliIk.setValue(setting.i_cali_k)
        self.ui.spinCaliIb.setValue(setting.i_cali_b)
        self.ui.spinCaliVk_2.setValue(setting.vset_cali_k)
        self.ui.spinCaliVb_2.setValue(setting.vset_cali_b)
        self.ui.spinCaliIk_2.setValue(setting.iset_cali_k)
        self.ui.spinCaliIb_2.setValue(setting.iset_cali_b)
        self.ui.checkBoxAntialias.setChecked(setting.antialias)
        self.ui.checkBoxOpenGL.setChecked(setting.opengl)
        self.ui.comboTheme.setCurrentIndex(
            {"light": 1, "dark": 0}.get(setting.theme, setting.theme)
        )
        self.ui.comboInput.setCurrentIndex(int(not setting.bitadjust))

    def show(self) -> None:
        self.initValues()
        center_window(self)
        super().show()

    @QtCore.pyqtSlot(int)
    def on_comboInput_currentIndexChanged(self, index):
        setting.bitadjust = index == 0

    @QtCore.pyqtSlot(int)
    def on_comboTheme_currentIndexChanged(self, index):
        set_theme({0: "dark", 1: "light"}.get(index, self.ui.comboTheme.currentText()))

    @QtCore.pyqtSlot(int)
    def on_checkBoxAntialias_stateChanged(self, state: int):
        setting.antialias = state == QtCore.Qt.CheckState.Checked
        update_pyqtgraph_setting()

    @QtCore.pyqtSlot(int)
    def on_checkBoxOpenGL_stateChanged(self, state: int):
        setting.opengl = state == QtCore.Qt.CheckState.Checked
        update_pyqtgraph_setting()

    @QtCore.pyqtSlot(float)
    def on_spinMaxFps_valueChanged(self, _=None):
        setting.graph_max_fps = self.ui.spinMaxFps.value()
        self.set_max_fps_sig.emit(self.ui.spinMaxFps.value())

    @QtCore.pyqtSlot(float)
    def on_spinStateFps_valueChanged(self, _=None):
        setting.state_fps = self.ui.spinStateFps.value()
        self.state_fps_sig.emit(self.ui.spinStateFps.value())

    @QtCore.pyqtSlot()
    def on_spinDataLength_editingFinished(self):
        value = self.ui.spinDataLength.value()
        if value == setting.data_pts:
            return
        setting.data_pts = value
        self.set_data_len_sig.emit(value)
        self.ui.spinDisplayLength.setMaximum(value)

    @QtCore.pyqtSlot()
    def on_spinDisplayLength_editingFinished(self):
        setting.display_pts = self.ui.spinDisplayLength.value()

    @QtCore.pyqtSlot(int)
    def on_comboInterp_currentIndexChanged(self, index):
        setting.interp = self.ui.comboInterp.currentIndex()
        self.set_interp_sig.emit(index)

    @QtCore.pyqtSlot(int)
    def on_comboAvgMode_currentIndexChanged(self, index):
        setting.avgmode = self.ui.comboAvgMode.currentIndex()

    @QtCore.pyqtSlot(float)
    def on_spinStateVThres_valueChanged(self, _=None):
        setting.v_threshold = self.ui.spinStateVThres.value()

    @QtCore.pyqtSlot(float)
    def on_spinStateIThres_valueChanged(self, _=None):
        setting.i_threshold = self.ui.spinStateIThres.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliVk_valueChanged(self, _=None):
        setting.v_cali_k = self.ui.spinCaliVk.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliVb_valueChanged(self, _=None):
        setting.v_cali_b = self.ui.spinCaliVb.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliIk_valueChanged(self, _=None):
        setting.i_cali_k = self.ui.spinCaliIk.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliIb_valueChanged(self, _=None):
        setting.i_cali_b = self.ui.spinCaliIb.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliVk_2_valueChanged(self, _=None):
        setting.vset_cali_k = self.ui.spinCaliVk_2.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliVb_2_valueChanged(self, _=None):
        setting.vset_cali_b = self.ui.spinCaliVb_2.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliIk_2_valueChanged(self, _=None):
        setting.iset_cali_k = self.ui.spinCaliIk_2.value()

    @QtCore.pyqtSlot(float)
    def on_spinCaliIb_2_valueChanged(self, _=None):
        setting.iset_cali_b = self.ui.spinCaliIb_2.value()

    @QtCore.pyqtSlot(int)
    def on_checkBoxUseCali_stateChanged(self, state: int):
        setting.use_cali = state == QtCore.Qt.CheckState.Checked

    @QtCore.pyqtSlot()
    def on_btnClose_clicked(self):
        try:
            setting.graph_max_fps = self.ui.spinMaxFps.value()
            setting.state_fps = self.ui.spinStateFps.value()
            setting.data_pts = self.ui.spinDataLength.value()
            setting.display_pts = self.ui.spinDisplayLength.value()
            setting.interp = self.ui.comboInterp.currentIndex()
            setting.avgmode = self.ui.comboAvgMode.currentIndex()
            setting.v_threshold = self.ui.spinStateVThres.value()
            setting.i_threshold = self.ui.spinStateIThres.value()
            setting.use_cali = self.ui.checkBoxUseCali.isChecked()
            setting.v_cali_k = self.ui.spinCaliVk.value()
            setting.v_cali_b = self.ui.spinCaliVb.value()
            setting.i_cali_k = self.ui.spinCaliIk.value()
            setting.i_cali_b = self.ui.spinCaliIb.value()
            setting.vset_cali_k = self.ui.spinCaliVk_2.value()
            setting.vset_cali_b = self.ui.spinCaliVb_2.value()
            setting.iset_cali_k = self.ui.spinCaliIk_2.value()
            setting.iset_cali_b = self.ui.spinCaliIb_2.value()
            setting.antialias = self.ui.checkBoxAntialias.isChecked()
            setting.opengl = self.ui.checkBoxOpenGL.isChecked()
            setting.bitadjust = self.ui.comboInput.currentIndex() == 0
            setting.save(SETTING_FILE)
        except Exception as e:
            logger.error(e)
        self.close()


class TransparentFloatingWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # 设置窗口为无边框和置顶
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setWindowTitle("MDP-P906 Floating Monitor")

        # 设置窗口大小和透明度
        self.setFixedSize(75, 140)
        self.setWindowOpacity(0.95)

        font_title = QtGui.QFont()
        font_title.setFamily("Sarasa Fixed SC SemiBold")
        font_title.setPointSize(10)

        font_value = QtGui.QFont()
        font_value.setFamily("Sarasa Fixed SC SemiBold")
        font_value.setPointSize(12)

        # 创建主窗口布局
        window_layout = QtWidgets.QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)

        # 创建Frame
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("QFrame { background-color: rgba(17, 17, 21, 100); }")
        window_layout.addWidget(frame)

        # 创建Frame内部布局
        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QtWidgets.QLabel(" MDP-P906 ", self)
        self.title_label.setFont(font_title)
        set_color(self.title_label, "rgb(200, 200, 200)")
        layout.addWidget(self.title_label, alignment=QtCore.Qt.AlignCenter)

        self.label_visable = True

        self.v_label = QtWidgets.QLabel(self.tr("电压 U"), self)
        self.v_label.setFont(font_title)
        set_color(self.v_label, setting.get_color("general_red", "dark"))
        layout.addWidget(self.v_label)
        self.voltage_label = QtWidgets.QLabel("", self)
        self.voltage_label.setFont(font_value)
        set_color(self.voltage_label, setting.get_color("general_red", "dark"))
        layout.addWidget(self.voltage_label)

        self.i_label = QtWidgets.QLabel(self.tr("电流 I"), self)
        self.i_label.setFont(font_title)
        set_color(self.i_label, setting.get_color("general_green", "dark"))
        layout.addWidget(self.i_label)
        self.current_label = QtWidgets.QLabel("", self)
        self.current_label.setFont(font_value)
        set_color(self.current_label, setting.get_color("general_green", "dark"))
        layout.addWidget(self.current_label)

        self.p_label = QtWidgets.QLabel(self.tr("功率 P"), self)
        self.p_label.setFont(font_title)
        set_color(self.p_label, setting.get_color("general_blue", "dark"))
        layout.addWidget(self.p_label)
        self.power_label = QtWidgets.QLabel("", self)
        self.power_label.setFont(font_value)
        set_color(self.power_label, setting.get_color("general_blue", "dark"))
        layout.addWidget(self.power_label)

        self.setLayout(window_layout)

        self.dragging = False
        self.offset = None

        self.update_values(0, 0, 0)

    def center_window(self):
        self.screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = self.screen.width() - self.width() - 10
        y = self.screen.height() // 2 - self.height() // 2
        self.move(x, y)
        self.setWindowOpacity(0.95)

    def update_values(self, u, i, p):
        self.voltage_label.setText(f"{u:06.3f} V")
        self.current_label.setText(f"{i:06.3f} A")
        if p < 100:
            self.power_label.setText(f"{p:06.3f} W")
        else:
            self.power_label.setText(f"{p:06.2f} W")

    def switch_visibility(self):
        if self.isVisible():
            self.close()
        else:
            self.center_window()
            self.show()

    def wheelEvent(self, event):
        current_opacity = self.windowOpacity()
        if event.angleDelta().y() > 0:
            new_opacity = min(1.0, current_opacity + 0.1)
        else:
            new_opacity = max(0.1, current_opacity - 0.1)
        self.setWindowOpacity(new_opacity)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.dragging:
            move = event.globalPos() - self.offset
            x = max(0, min(move.x(), self.screen.width() - self.width()))
            y = max(0, min(move.y(), self.screen.height() - self.height()))
            self.move(x, y)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False

    def mouseDoubleClickEvent(self, event):
        self.switch_label_visibility()

    def switch_label_visibility(self):
        self.label_visable = not self.label_visable
        if self.label_visable:
            self.v_label.setVisible(True)
            self.i_label.setVisible(True)
            self.p_label.setVisible(True)
            self.setFixedHeight(140)
        else:
            self.v_label.setVisible(False)
            self.i_label.setVisible(False)
            self.p_label.setVisible(False)
            self.setFixedHeight(80)

    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)

        toggle_action = menu.addAction(
            self.tr("折叠") if self.label_visable else self.tr("展开")
        )
        close_action = menu.addAction(self.tr("关闭"))

        action = menu.exec_(event.globalPos())

        if action == toggle_action:
            self.switch_label_visibility()
        elif action == close_action:
            self.close()


class ResultGraphWindow(QtWidgets.QDialog, FramelessWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 创建主布局
        self.main_layout = QtWidgets.QVBoxLayout()

        # padding
        label = QtWidgets.QLabel("")
        label.setFixedHeight(25)
        self.main_layout.addWidget(label)
        self.setLayout(self.main_layout)

        # 设置自定义标题栏
        self.setWindowTitle("MDP-P906 Result Graph Window")
        self.CustomTitleBar = CustomTitleBar(self, "MDP-P906 Result Graph Window")
        self.CustomTitleBar.set_theme("dark")
        self.CustomTitleBar.set_allow_double_toggle_max(False)
        self.CustomTitleBar.set_full_btn_enabled(False)
        self.setTitleBar(self.CustomTitleBar)

        # 创建图表组件
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(None)
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel("left", "Y-Axis")
        self.plot_widget.setLabel("bottom", "X-Axis")

        # 创建曲线
        self.pen = pg.mkPen(color=setting.get_color("line1"), width=2)
        self.fit_pen = pg.mkPen(color=setting.get_color("line2"), width=2)
        self.curve = self.plot_widget.plot(pen=self.pen)
        self.curve.setData([], [])
        self.curve_fit = self.plot_widget.plot(pen=self.fit_pen)
        self.curve_fit.setData([], [])
        self.plot_widget.autoRange()
        self.main_layout.addWidget(self.plot_widget)

        self.hlayout = QtWidgets.QHBoxLayout()

        self.btnXYSwap = QtWidgets.QPushButton("X/Y")
        self.hlayout.addWidget(self.btnXYSwap)
        self.btnXYSwap.clicked.connect(self.swapXY)

        label = QtWidgets.QLabel(self.tr("多项式拟合次数:"))
        label.setFont(global_font)
        self.hlayout.addWidget(label)

        self.spinBoxFit = QtWidgets.QSpinBox()
        self.spinBoxFit.setRange(0, 8)
        self.spinBoxFit.setValue(0)
        self.hlayout.addWidget(self.spinBoxFit)
        self.spinBoxFit.valueChanged.connect(self.update_fit_result)

        self.labelFitResult = QtWidgets.QLabel("N/A")
        self.labelFitResult.setFont(global_font)
        self.hlayout.addWidget(self.labelFitResult)

        self.hlayout.setStretch(0, 0)
        self.hlayout.setStretch(1, 0)
        self.hlayout.setStretch(2, 0)
        self.hlayout.setStretch(3, 1)

        self.main_layout.addLayout(self.hlayout)

        self.x_data = []
        self.y_data = []

    def format_fit_result(self, result):
        result = list(result)
        for i in range(len(result)):
            if abs(result[i]) < 1e-9:
                result[i] = 0
        text = "y = ("
        for i, coef in enumerate(result):
            if i != 0:
                text += " + ("
            text += f"{coef:0.4g}"
            ml = len(result) - i - 1
            if ml > 1:
                text += f"x^{ml}"
            elif ml == 1:
                text += "x"
            text += ")"
        return text

    def update_fit_result(self, _=None):
        if len(self.x_data) + len(self.y_data) < 4 or self.spinBoxFit.value() < 1:
            self.labelFitResult.setText("N/A")
            self.curve_fit.setData([], [])
            return
        logger.info(
            f"fit {len(self.x_data)} points with {self.spinBoxFit.value()} order"
        )
        z = np.polyfit(self.x_data, self.y_data, self.spinBoxFit.value())

        y_pred = np.polyval(z, self.x_data)
        rmse = np.sqrt(np.mean((np.array(self.y_data) - y_pred) ** 2))
        logger.info(f"fit result: {z} with rmse={rmse:0.4g}")
        self.labelFitResult.setText(f"rmse={rmse:0.4f} {self.format_fit_result(z)}")
        SAMPLE_N = 1000
        x_fit = np.linspace(min(self.x_data), max(self.x_data), SAMPLE_N)
        y_fit = np.polyval(z, x_fit)
        self.curve_fit.setData(x_fit, y_fit)

    def showData(self, x, y, x_label, y_label, x_unit, y_unit, title, disable_swap):
        self.x_data = x
        self.y_data = y
        self.x_label = x_label
        self.y_label = y_label
        self.x_unit = x_unit
        self.y_unit = y_unit
        self.title = title
        self.curve.setData(x, y)
        self.plot_widget.setLabel("bottom", x_label, units=x_unit)
        self.plot_widget.setLabel("left", y_label, units=y_unit)
        self.plot_widget.autoRange()
        self.CustomTitleBar.set_name(title)
        if disable_swap:
            self.btnXYSwap.setVisible(False)
        else:
            self.btnXYSwap.setVisible(True)
        if hasattr(self, "vLine"):
            self.plot_widget.removeItem(self.vLine)
        if hasattr(self, "hLine"):
            self.plot_widget.removeItem(self.hLine)
        if not self.isVisible():
            self.spinBoxFit.setValue(0)
        self.update_fit_result()
        if not self.isVisible():
            self.show()
            center_window(self, 800, 600)

    def swapXY(self):
        self.x_data, self.y_data = self.y_data, self.x_data
        self.x_label, self.y_label = self.y_label, self.x_label
        self.x_unit, self.y_unit = self.y_unit, self.x_unit
        self.showData(
            self.x_data,
            self.y_data,
            self.x_label,
            self.y_label,
            self.x_unit,
            self.y_unit,
            self.title,
            False,
        )

    def highlightPoint(self, x, y):
        if hasattr(self, "vLine"):
            self.plot_widget.removeItem(self.vLine)
        if hasattr(self, "hLine"):
            self.plot_widget.removeItem(self.hLine)

        self.vLine = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(setting.get_color("line2")),
        )
        self.hLine = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(setting.get_color("line2")),
        )
        self.vLine.setPos(x)
        self.hLine.setPos(y)
        self.plot_widget.addItem(self.vLine)
        self.plot_widget.addItem(self.hLine)


DialogSettings = MDPSettings()
DialogGraphics = MDPGraphics()
DialogResult = ResultGraphWindow()
FloatingWindow = TransparentFloatingWindow()
MainWindow.ui.btnSettings.clicked.connect(DialogSettings.show)
MainWindow.ui.btnGraphics.clicked.connect(DialogGraphics.show)
DialogGraphics.set_max_fps_sig.connect(MainWindow.set_graph_max_fps)
DialogGraphics.state_fps_sig.connect(MainWindow.set_state_fps)
DialogGraphics.set_data_len_sig.connect(MainWindow.set_data_length)
DialogGraphics.set_interp_sig.connect(MainWindow.set_interp)
MainWindow.ui.btnRecordFloatWindow.clicked.connect(FloatingWindow.switch_visibility)
MainWindow.uip_values_signal.connect(FloatingWindow.update_values)
MainWindow.display_data_signal.connect(DialogResult.showData)
MainWindow.highlight_point_signal.connect(DialogResult.highlightPoint)
MainWindow.close_signal.connect(FloatingWindow.close)
MainWindow.close_signal.connect(DialogResult.close)
MainWindow.close_signal.connect(DialogGraphics.close)
MainWindow.close_signal.connect(DialogSettings.close)
app.setWindowIcon(QtGui.QIcon(ICON_PATH))


def set_theme(theme):
    setting.theme = theme
    if theme not in ("dark", "light"):
        sys_theme = setting.color_palette[theme]["based_on_dark_or_light"]
    else:
        sys_theme = theme
    additional_qss = (
        "QToolTip {"
        "   color: rgb(228, 231, 235);"
        "   background-color: rgb(32, 33, 36);"
        "   border: 1px solid rgb(63, 64, 66);"
        "   border-radius: 4px;"
        "}"
        "QSlider::add-page:horizontal {"
        "   background: #36ff8888;"
        "}"
        "QSlider::sub-page:horizontal {"
        "   background: #368888ff;"
        "}"
        if sys_theme == "dark"
        else "QToolTip {"
        "   color: rgb(32, 33, 36);"
        "   background-color: white;"
        "   border: 1px solid rgb(218, 220, 224);"
        "   border-radius: 4px;"
        "}"
        "QSlider::add-page:horizontal {"
        "   background: #36880000;"
        "}"
        "QSlider::sub-page:horizontal {"
        "   background: #36000088;"
        "}"
    )
    qdarktheme.setup_theme(
        sys_theme,
        additional_qss=additional_qss,
    )
    MainWindow.ui.widgetGraph1.setBackground(None)
    MainWindow.ui.widgetGraph2.setBackground(None)
    MainWindow.CustomTitleBar.set_theme(sys_theme)
    DialogSettings.CustomTitleBar.set_theme(sys_theme)
    DialogGraphics.CustomTitleBar.set_theme(sys_theme)
    set_color(
        DialogGraphics.ui.labelNumba,
        setting.get_color("general_green"),
    )
    if MainWindow.api is not None:
        set_color(
            MainWindow.ui.labelConnectState,
            setting.get_color("general_green"),
        )
    MainWindow.update_pen()
    DialogResult.pen.setColor(QtGui.QColor(setting.get_color("line1")))
    MainWindow.ui.horizontalSlider.setStyleSheet("background: none;")
    MainWindow.ui.horizontalSlider.setBarVisible(False)

    set_color(MainWindow.ui.lcdVoltage, setting.get_color("lcd_voltage"))
    set_color(MainWindow.ui.lcdCurrent, setting.get_color("lcd_current"))
    set_color(MainWindow.ui.lcdPower, setting.get_color("lcd_power"))
    set_color(MainWindow.ui.lcdEnerge, setting.get_color("lcd_energy"))
    set_color(
        MainWindow.ui.lcdAvgPower,
        setting.get_color("lcd_avg_power"),
    )
    set_color(
        MainWindow.ui.lcdResistence,
        setting.get_color("lcd_resistance"),
    )


set_theme(setting.theme)


def show_app():
    MainWindow.show()
    MainWindow.activateWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    show_app()
