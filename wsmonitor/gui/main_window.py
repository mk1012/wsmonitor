# -*- coding: utf-8 -*-
import json
import logging
import sys
from json import JSONDecodeError

from PySide2 import QtWebSockets
from PySide2.QtCore import (QUrl, Qt)
from PySide2.QtGui import QTextCursor
from PySide2.QtWidgets import *

from wsmonitor.gui.process_list import ProcessListWidget
from wsmonitor.process.data import ProcessSummaryEvent, StateChangedEvent, ActionResponse, OutputEvent

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessMonitorWindow(QMainWindow):
    def __init__(self):
        super(ProcessMonitorWindow, self).__init__()
        self.ui = ProcessMonitorUI(self)

        self._ws_connected = False
        self.client = QtWebSockets.QWebSocket("", QtWebSockets.QWebSocketProtocol.Version13, None)

        # Subscribe to events from the ws connection
        self.client.error.connect(self.on_ws_error)
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.textMessageReceived.connect(self.on_message)

        self.ui.process_list.action_requested.connect(self.on_action_requested)
        self.ui.btn_connect.clicked.connect(self.on_connect_clicked)

    def on_connect_clicked(self):
        if self._ws_connected:
            logger.warning("Already connected")
            return

        self.establish_connection()

    def establish_connection(self):
        server_url = self.ui.txt_conenction.text()
        logger.info("Connecting to: %s", server_url)
        self.client.open(QUrl(server_url))

    def on_message(self, message):
        # logger.info("Incomming msg: %s" % message)
        try:
            json_data = json.loads(message)
            type = json_data["type"]
            payload = json_data["data"]

            if type == "ProcessSummaryEvent":
                pdatas = ProcessSummaryEvent.from_json(payload)
                self.ui.process_list.update_process_data(set(pdatas.processes))
            if type == "StateChangedEvent":
                state: StateChangedEvent = StateChangedEvent.from_json(payload)
                self.ui.process_list.update_single_process_state(state)
            if type == "ActionResponse":
                response = ActionResponse.from_json(payload)
                self.ui.process_list.on_action_completed(response)
            if type == "OutputEvent":
                output = OutputEvent.from_json(payload)
                self.ui.handle_output(output)
        except JSONDecodeError as e:
            logger.error("Failed to parse message", exc_info=e)
        except KeyError as e:
            logger.error("Could not retrieve expected field from JSON", exc_info=e)
        except Exception as e:
            logger.error("Unexpected exception on incomming message", exc_info=e)

    def on_action_requested(self, uid, action):
        logger.info("New action request: %s, %s", uid, action)
        self.send_message(json.dumps({"action": action, "data": {"uid": uid}}))

    def on_connected(self):
        logger.info("connected")
        self._ws_connected = True
        self.ui.set_connected_ui()

    def on_disconnected(self):
        logger.info("Disconnected")
        self._ws_connected = False
        self.ui.set_disconnected_ui("Connection has been closed.")

    def send_message(self, msg):
        if not self._ws_connected:
            logger.warning("CLIENT NOT CONNECTED!")
            return
        logger.info("Sending message: %s", msg)
        self.client.sendTextMessage(msg)

    def on_ws_error(self, error_code):
        logger.error("WS Error, code: {}".format(error_code))
        error_msg = self.client.errorString()
        logger.error(error_msg)

        self.client.close()
        self.ui.set_disconnected_ui(error_msg)

    def close(self):
        self.client.close()


class ProcessMonitorUI(object):
    def __init__(self, window: ProcessMonitorWindow):
        self.window = window

        self.main_widget = QWidget(window)
        self.main_layout = QVBoxLayout()
        self.layout_connection = QHBoxLayout()
        self.txt_conenction = QLineEdit()
        self.btn_connect = QPushButton()
        self.layout_connection.addWidget(self.txt_conenction)
        self.layout_connection.addWidget(self.btn_connect)
        self.process_list = ProcessListWidget()

        self.txt_output = QTextEdit()

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setMinimumSize(820, 540)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.splitter.sizePolicy().hasHeightForWidth())
        self.splitter.setSizePolicy(sizePolicy)
        self.splitter.setStretchFactor(0, 10)
        self.splitter.setStretchFactor(1, 0)

        self.main_layout.addLayout(self.layout_connection)
        self.splitter.addWidget(self.process_list)
        self.splitter.addWidget(self.txt_output)
        self.main_layout.addWidget(self.splitter)

        self.main_widget.setLayout(self.main_layout)
        self.statusbar = QStatusBar(window)

        self.txt_conenction.setPlaceholderText("ws://127.0.0.1:8766")
        self.txt_conenction.setText("ws://127.0.0.1:8766")
        self.btn_connect.setText("Connect")

        window.setCentralWidget(self.main_widget)
        window.setStatusBar(self.statusbar)
        window.setWindowTitle("Process Monitor")
        self.set_disconnected_ui("Click on Connect to establish a connection")

    def set_disconnected_ui(self, msg:str):
        self.process_list.setDisabled(True)
        self.btn_connect.setDisabled(False)
        self.statusbar.showMessage(f"Disconnected. {msg}")

    def set_connected_ui(self):
        self.process_list.setDisabled(False)
        self.btn_connect.setDisabled(True)
        self.statusbar.showMessage("Connection established.")

    def handle_output(self, output):
        self.txt_output.moveCursor(QTextCursor.End)
        self.txt_output.insertPlainText(output.output)


def main():
    app = QApplication(sys.argv)

    window = ProcessMonitorWindow()
    window.show()

    sys.exit(app.exec_())
