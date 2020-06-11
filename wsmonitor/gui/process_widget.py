# -*- coding: utf-8 -*-
import logging

from PySide2 import QtCore, QtGui
from PySide2.QtCore import Signal, Slot
from PySide2.QtGui import QColor
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QPushButton, QSizePolicy

from wsmonitor.gui.process_list import ProcessListWidget
from wsmonitor.process.data import ProcessData

logger = logging.getLogger(__name__)


class ProcessWidget(QWidget):
    actionRequested = Signal(str, str)
    colors = {
        ProcessData.INITIALIZED: QColor(0, 0, 100, 50),
        ProcessData.STARTING: QColor(0, 100, 0, 25),
        ProcessData.STARTED: QColor(0, 100, 0, 50),
        ProcessData.STOPPING: QColor(100, 0, 0, 25),
        ProcessData.ENDED: QColor(100, 0, 0, 10),
        ProcessData.ENDED + "_success": QColor(0, 100, 0, 10),
    }

    def get_bg_color(self):
        return self.palette().background().color()

    def set_bg_color(self, color):
        palette = self.palette()
        palette.setColor(self.backgroundRole(), color)
        self.setPalette(palette)

    color = QtCore.Property(QtGui.QColor, get_bg_color, set_bg_color)

    def change_bg_color_with_blink(self, color: QColor):
        self.blink(self.background_color, color)
        self.background_color = color

    def blink(self, start_color, end_color):
        # make sure we apply any possible pending color changes
        self.blink_animation.stop()
        self.set_bg_color(self.background_color)

        self.blink_animation.setDuration(1000)
        self.blink_animation.setLoopCount(1)
        self.blink_animation.setStartValue(start_color)
        self.blink_animation.setEndValue(end_color)
        self.blink_animation.setKeyValueAt(0.33, end_color)
        self.blink_animation.setKeyValueAt(0.66, start_color)
        self.blink_animation.start()

    def __init__(self, process_data: ProcessData, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._awaiting_response = False
        self.__process_data: ProcessData = process_data
        self.setAutoFillBackground(True)
        self.background_color = self.get_bg_color()
        self.blink_animation = QtCore.QPropertyAnimation(self, b"color")

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self.layout = QGridLayout()
        self.layout.setColumnMinimumWidth(0, 120)
        self.layout.setColumnStretch(0, 10)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setVerticalSpacing(2)

        self.btn_restart = QPushButton(self, text="Restart")
        self.btn_start_stop = QPushButton(self, text="Start/Stop")
        self.btn_start_stop.setObjectName("btn_start_stop")
        self.btn_start_stop.setMinimumWidth(60)
        self.btn_restart.setMinimumWidth(60)
        self.txt_command = QLabel(self)
        # self.txt_command.setPlaceholderText("Your command")

        self.lbl_uid = QLabel(self, text=process_data.uid)
        self.lbl_uid.setStyleSheet("font-weight: bold")
        self.lbl_state = QLabel(self, text=process_data.state_info())

        self.layout.addWidget(self.lbl_uid, 0, 0)
        self.layout.addWidget(self.lbl_state, 0, 1, 1, 2)
        self.layout.addWidget(self.txt_command, 1, 0)
        self.layout.addWidget(self.btn_restart, 1, 1)
        self.layout.addWidget(self.btn_start_stop, 1, 2)
        self.setLayout(self.layout)

        self.btn_start_stop.clicked.connect(self._start_stop_clicked)

        self.on_update_process_data(process_data)

    def get_command_text(self):
        return self.txt_command.text()

    def _start_stop_clicked(self):
        action = "stop" if self.__process_data.is_in_state(ProcessData.STARTED) else "start"
        self.request_action(action)

    def request_action(self, action):
        print("Requesting action: ", action)
        self.disable_till_response()
        self.actionRequested.emit(self.__process_data.uid, action)

    @Slot(str)
    def on_action_completed(self, action_response):
        print("Completed:", action_response)
        self._disable_buttons(False)
        self._awaiting_response = False

    def disable_till_response(self):
        self._disable_buttons(True)
        self._awaiting_response = True

    def _disable_buttons(self, disable=True):
        if not disable and self._awaiting_response:
            logger.info("Awaiting response, cannot unlock buttons")
            return
        self.btn_start_stop.setDisabled(disable)
        self.btn_restart.setDisabled(disable)


    def on_update_process_data(self, process_data: ProcessData):
        logger.debug("Process data updated: %s", process_data)

        self._update_state(process_data.state, process_data.exit_code)

        # only update if not changed manually, i.e. __proc_data.cmd == text()
        current_cmd = self.txt_command.text()
        if current_cmd == "" or self.__process_data.command == current_cmd:
            self.txt_command.setText(process_data.command)
            self.txt_command.setStyleSheet("color: inherit;")
        else:
            self.txt_command.setStyleSheet("color: orange;")
        self.__process_data = process_data


    def _update_state(self, state, exit_code):
        self.__process_data.exit_code = exit_code

        if self.__process_data.state != state:
            self.__process_data.state = state
            self.lbl_state.setText(self.__process_data.state_info())

            self.set_color_from_state(state)

        is_running = state == ProcessData.STARTED
        if is_running:
            self.btn_start_stop.setText("Stop")
        else:
            self.btn_start_stop.setText("Start")

        self.btn_restart.setDisabled(not is_running)
        self.btn_start_stop.setDisabled(False)

    def set_color_from_state(self, state):
        if self.__process_data.has_ended_successfully():
            self.change_bg_color_with_blink(self.colors[ProcessData.ENDED + "_success"])
        else:
            self.change_bg_color_with_blink(self.colors[state])
