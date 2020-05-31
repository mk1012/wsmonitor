# -*- coding: utf-8 -*-
from typing import Dict, Set

from PySide2.QtCore import Signal, Slot, Qt
from PySide2.QtWidgets import QWidget, QGridLayout, QLabel, QPushButton, QLineEdit, QSizePolicy, QVBoxLayout, \
    QScrollArea

from process_data import ProcessData


class ProcessWidget(QWidget):
    actionRequested = Signal(str, str)

    @Slot(str)
    def on_request_completed(self, result_state):
        print("Completed:", result_state)
        self._set_state(result_state)

    def on_update_process_data(self, process_data: ProcessData):
        print("Date update:", process_data)
        self.__process_data = process_data
        self._set_state(process_data.state)
        self.txt_command.setText(process_data.command)

    def get_command_text(self):
        return self.txt_command.text()

    def _start_stop_clicked(self):
        print("start_stop clicked")

        self._disable_buttons()
        action = "stop" if self.__process_data.state == ProcessData.RUNNING else "start"
        print("Requested action: ", action)
        self.actionRequested.emit(self.__process_data.uid, action)

    def _disable_buttons(self, disable=True):
        self.btn_start_stop.setDisabled(disable)
        self.btn_restart.setDisabled(disable)

    def _set_state(self, state):
        self.__process_data.state = state
        self.lbl_state.setText("State: %s"% state)

        is_running = state == ProcessData.RUNNING
        if is_running:
            self.btn_start_stop.setText("Stop")
        else:
            self.btn_start_stop.setText("Start")

        self.btn_restart.setDisabled(not is_running)

    def __init__(self, process_data: ProcessData, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__process_data = process_data

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self.layout = QGridLayout()
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setVerticalSpacing(2)
        self.layout.setObjectName("layout_grid")
        self.btn_restart = QPushButton(self, text="Restart")
        self.btn_restart.setObjectName("btn_restart")
        self.btn_start_stop = QPushButton(self, text="Start/Stop")
        self.btn_start_stop.setObjectName("btn_start_stop")
        self.txt_command = QLineEdit(self)
        self.txt_command.setPlaceholderText("Your command")
        self.txt_command.setObjectName("txt_command")

        self.lbl_uid = QLabel(self, text="ID: %s" % self.__process_data.uid)
        self.lbl_uid.setMinimumWidth(100)
        self.lbl_command = QLabel(self, text="Command")
        self.lbl_command.setObjectName("lbl_command")
        self.lbl_state = QLabel(self, text="State")
        self.lbl_state.setObjectName("lbl_state")

        self.layout.addWidget(self.lbl_uid, 1, 0, 1, 1)
        self.layout.addWidget(self.txt_command, 1, 1, 1, 1)
        self.layout.addWidget(self.btn_restart, 1, 3, 1, 1)
        self.layout.addWidget(self.btn_start_stop, 1, 2, 1, 1)
        self.layout.addWidget(self.lbl_command, 0, 1, 1, 1)
        self.layout.addWidget(self.lbl_state, 0, 2, 1, 3)
        self.setLayout(self.layout)

        self.btn_start_stop.clicked.connect(self._start_stop_clicked)

        self.on_update_process_data(process_data)


class ProcessListWidget(QScrollArea):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_data = set()
        self.process_widget_map = {}  # type: Dict[str, ProcessWidget]

        self.main_widget = QWidget()
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)

        self.lbl_default = QLabel(text="No processes found")
        self.layout.addWidget(self.lbl_default)

        # Configure ScrollArea
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setWidget(self.main_widget)

    def on_action_requested(self, p_uid, action):
        print("Action requested: ", p_uid, action)

    @Slot(str)
    def on_action_completed(self, p_uid, action):
        print("Action completed: ", p_uid, action)
        self.process_widget_map[p_uid].on_request_completed(action)

    def update_process_data(self, updated_process_data: Set[ProcessData]):
        known_processes = updated_process_data & self.process_data
        new_processes = updated_process_data - self.process_data
        unknown_processes = updated_process_data - self.process_data

        for known_process in known_processes:
            widget = self.process_widget_map[known_process.uid]
            widget.on_update_process_data(known_process)

        for new_process in new_processes:
            widget = ProcessWidget(new_process)
            self.process_widget_map[new_process.uid] = widget
            widget.actionRequested.connect(self.on_action_requested)
            self.layout.addWidget(widget)

        # TODO(mark): unknown processes

        self.process_data = self.process_data | updated_process_data
        self.lbl_default.setVisible(len(self.process_data) == 0)


if __name__ == '__main__':
    import sys
    from PySide2.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # serverObject = QtWebSockets.QWebSocketServer('My Socket', QtWebSockets.QWebSocketServer.NonSecureMode)
    # server = MyServer(serverObject)
    # serverObject.closed.connect(app.quit)

    test = ProcessListWidget()
    test.update_process_data(set([ProcessData("bubber", "ls *", False),
                                  ProcessData("fisch", "htop", False)]))


    def say_something(name):
        print("aa", name)


    test.show()

    app.exec_()
