import logging
from typing import Dict

from PySide2 import QtCore, QtGui
from PySide2.QtCore import Signal, Slot
from PySide2.QtGui import QColor, QTextCursor, Qt
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QPushButton, QSizePolicy, QStyle, QVBoxLayout, QTextEdit, \
    QCheckBox, QTabWidget, QHBoxLayout

from wsmonitor.process.data import ProcessData

logger = logging.getLogger(__name__)

colors = {
    ProcessData.INITIALIZED: QColor(0, 0, 120, 25),
    ProcessData.STARTING: QColor(120, 120, 0, 15),
    ProcessData.STARTED: QColor(0, 120, 0, 25),
    ProcessData.STOPPING: QColor(120, 120, 0, 50),
    ProcessData.ENDED: QColor(120, 120, 0, 50),
    ProcessData.ENDED + "_success": QColor(0, 120, 0, 50),
    ProcessData.ENDED + "_failure": QColor(120, 0, 0, 50),
}


def get_color_for_process(data: ProcessData):
    if data.has_ended_successfully():
        return colors[ProcessData.ENDED + "_success"]
    if data.is_in_state(ProcessData.ENDED):
        return colors[ProcessData.ENDED + "_failure"]

    return colors[data.state]


class BlinkBackgroundWidget(QWidget):

    # Fake bg_color property to use in the animation
    def get_bg_color(self):
        return self.palette().background().color()

    def set_bg_color(self, color):
        palette = self.palette()
        palette.setColor(self.backgroundRole(), color)
        self.setPalette(palette)

    bg_color = QtCore.Property(QtGui.QColor, get_bg_color, set_bg_color)

    def change_bg_color_with_blink(self, color: QColor):
        self.blink_bg_color(self.background_color, color)
        self.background_color = color

    def blink_bg_color(self, start_color, end_color):
        # make sure we apply any possible pending color changes
        self.blink_animation.stop()
        self.set_bg_color(self.background_color)

        self.blink_animation.setDuration(800)
        self.blink_animation.setLoopCount(1)
        self.blink_animation.setStartValue(start_color)
        self.blink_animation.setEndValue(end_color)
        self.blink_animation.setKeyValueAt(0.33, end_color)
        self.blink_animation.setKeyValueAt(0.66, start_color)
        self.blink_animation.start()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAutoFillBackground(True)
        self.background_color = self.get_bg_color()
        self.blink_animation = QtCore.QPropertyAnimation(self, b"bg_color")


class ProcessWidget(BlinkBackgroundWidget):
    actionRequested = Signal(str, str)
    process_state_changed = Signal(str, str)

    def __init__(self, process_data: ProcessData, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._awaiting_response = False
        self._process_data: ProcessData = process_data

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
        self.txt_command = QLabel(self, text=process_data.command)
        # self.txt_command.setPlaceholderText("Your command")

        self.lbl_uid = QLabel(self, text=process_data.uid)
        self.lbl_uid.setStyleSheet("font-weight: bold")
        self.lbl_state = QLabel(self, text=process_data.state_info())

        self.layout.addWidget(self.lbl_uid, 0, 0)
        self.layout.addWidget(self.lbl_state, 0, 1, 1, 2)
        self.layout.addWidget(self.txt_command, 1, 0)
        self.layout.addWidget(self.btn_start_stop, 1, 1)
        self.layout.addWidget(self.btn_restart, 1, 2)
        self.setLayout(self.layout)

        self.btn_start_stop.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.btn_restart.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))

        self.btn_start_stop.clicked.connect(self._start_stop_clicked)
        self.btn_restart.clicked.connect(lambda: self.request_action("restart"))

        self.update_state(process_data.state, process_data.exit_code, True)

    def get_command_text(self):
        return self.txt_command.text()

    def _start_stop_clicked(self):
        action = "stop" if self._process_data.is_in_state(ProcessData.STARTED) else "start"
        self.request_action(action)

    def request_action(self, action: str):
        logger.debug("Requesting action: %s", action)
        self._disable_buttons(True)
        self.actionRequested.emit(self._process_data.uid, action)

    @Slot(str)
    def on_action_completed(self, action_response: str):
        logger.debug("Action completed: %s", action_response)
        self._set_button_ui(self._process_data.state)  # make sure the conform to state

    def _disable_buttons(self, disable=True):
        self.btn_start_stop.setDisabled(disable)
        self.btn_restart.setDisabled(disable)

    def on_update_process_data(self, process_data: ProcessData):
        logger.debug("Process data updated: %s", process_data)
        self.update_state(process_data.state, process_data.exit_code)

    def update_state(self, state: str, exit_code: int, state_changed=False):
        self._process_data.exit_code = exit_code
        self._set_button_ui(state)

        if self._process_data.state != state or state_changed:
            self._process_data.state = state
            self.lbl_state.setText(self._process_data.state_info())

            self.change_bg_color_with_blink(get_color_for_process(self._process_data))
            self.process_state_changed.emit(self._process_data.uid, state)

    def _set_button_ui(self, state: str):
        is_running = state == ProcessData.STARTED
        self.btn_start_stop.setDisabled(False)

        if is_running:
            self.btn_start_stop.setText("Stop")
            self.btn_start_stop.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        elif state in (ProcessData.INITIALIZED, ProcessData.ENDED):
            self.btn_start_stop.setText("Start")
            self.btn_start_stop.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            self.btn_start_stop.setDisabled(True)
        self.btn_restart.setDisabled(not is_running)


class ProcessOutputTabsWidget(QTabWidget):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tabs: Dict[str, ProcessOutputTabWidget] = {}

    def add_process_tab(self, uid: str):
        logger.info("Added output tab for %s", uid)
        output = ProcessOutputTabWidget(self)
        self.tabs[uid] = output
        self.addTab(output, uid)

    def append_output(self, uid: str, output: str):
        tab = self.tabs[uid]
        tab.append(output)

    def process_state_changed(self, uid: str, state: str):
        tab = self.tabs[uid]
        tab.process_state_changed(state)
        # Show output on process start
        if state == ProcessData.STARTED:
            self.setCurrentWidget(tab)


class ProcessOutputTabWidget(QWidget):
    STARTED_OUTPUT_LINE = "\n" + "-" * 19 + " OUTPUT STARTED " + "-" * 19 + "\n\n"
    ENDED_OUTPUT_LINE = "\n" + "-" * 20 + " OUTPUT ENDED " + "-" * 20 + "\n"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.layout = QVBoxLayout(self)
        self.txt_output = QTextEdit(self)

        policy = self.txt_output.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.MinimumExpanding)
        policy.setHorizontalStretch(1)
        policy.setVerticalPolicy(QSizePolicy.MinimumExpanding)
        policy.setVerticalStretch(1)
        self.txt_output.setSizePolicy(policy)
        self.txt_output.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # self.layout.setStretch(0,True)
        self.layout.addWidget(self.txt_output)

        sub_layout = QHBoxLayout(self)
        self.chb_clear_on_start = QCheckBox(self, text="Clear on start")
        self.btn_clear = QPushButton(self, text="Clear output")
        sub_layout.addWidget(self.chb_clear_on_start)
        sub_layout.addStretch()
        sub_layout.addWidget(self.btn_clear)

        self.layout.addLayout(sub_layout)
        self.setLayout(self.layout)
        self.txt_output.setReadOnly(True)

        self.btn_clear.clicked.connect(self.clear)

    def clear(self) -> None:
        self.txt_output.clear()

    def append(self, output: str):
        self.txt_output.moveCursor(QTextCursor.End)
        self.txt_output.insertPlainText(output)

    def process_state_changed(self, state: str) -> None:
        if state == ProcessData.STARTED:
            if self.chb_clear_on_start.isChecked():
                self.clear()
            else:
                self.append(self.STARTED_OUTPUT_LINE)

        elif state == ProcessData.ENDED:
            if not self.chb_clear_on_start.isChecked():
                self.append(self.ENDED_OUTPUT_LINE)
