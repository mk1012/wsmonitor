# -*- coding: utf-8 -*-
import json
import logging
import sys
from json import JSONDecodeError

from PySide2 import QtWebSockets
from PySide2.QtCore import (QUrl, Qt)
from PySide2.QtGui import QTextCursor
from PySide2.QtWidgets import *
from ws_pmom.gui.process_widget import ProcessListWidget
from ws_pmom.process_data import ProcessData

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self._ws_connected = False
        self.client = QtWebSockets.QWebSocket("", QtWebSockets.QWebSocketProtocol.Version13, None)

        self.setup_ui()

        self.client.error.connect(self.on_ws_error)
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.textMessageReceived.connect(self.on_message)
        self.btn_connect.clicked.connect(self.on_connect_clicked)

    def on_connect_clicked(self):
        if self._ws_connected:
            logger.warning("Already connected")
            return

        self.establish_connection()

    def establish_connection(self):
        server_url = self.txt_conenction.text()
        logger.info("Connecting to: %s", server_url)
        self.client.open(QUrl(server_url))

    def on_message(self, message):
        logger.info("Incomming msg: %s" % message)
        try:
            json_data = json.loads(message)
        except JSONDecodeError as e:
            logger.error("Failed to parse message", exc_info=e)
            return

        type = json_data["type"]
        if type == "ProcessSummaryEvent":
            data = json_data["data"]
            pdatas = set([ProcessData.from_dict(entry) for entry in data])
            self.process_list.update_process_data(pdatas)
        if type == "StateChangedEvent":
            payload = json_data["data"]
            state = payload["data"]
            uid = payload["uid"]
            self.process_list.update_single_process_state(uid, state)
        if type == "ActionResponse":
            payload = json_data["data"]
            action = json_data.get("action", None)
            if action is None:
                logger.info("Request failed")
                return
            args = (payload[key] for key in ["uid", "action", "success", "data"])
            self.process_list.on_action_completed(*args)
        if type == "OutputEvent":
            self.txt_output.moveCursor(QTextCursor.End)
            self.txt_output.insertPlainText(json_data["data"]["data"])

    def on_connected(self):
        logger.info("connected")
        self._ws_connected = True
        self.set_connected_ui()

    def on_disconnected(self):
        logger.info("disconnected")
        self._ws_connected = False
        self.set_disconnected_ui()

    def send_message(self, msg):
        if not self._ws_connected:
            logger.warning("CLIENT NOT CONENCTED!")
            return
        logger.info("Send_message: %s", msg)
        self.client.sendTextMessage(msg)

    def onPong(self, elapsedTime, payload):
        print("onPong - time: {} ; payload: {}".format(elapsedTime, payload))

    def on_ws_error(self, error_code):
        print("error code: {}".format(error_code))
        print(self.client.errorString())
        self.client.close()
        self.set_disconnected_ui()

    def close(self):
        self.client.close()

    def setup_ui(self):
        self.main_widget = QWidget(self)
        self.main_layout = QVBoxLayout()
        self.layout_connection = QHBoxLayout()
        self.txt_conenction = QLineEdit()
        self.btn_connect = QPushButton()
        self.layout_connection.addWidget(self.txt_conenction)
        self.layout_connection.addWidget(self.btn_connect)
        self.process_list = ProcessListWidget()

        self.txt_output = QTextEdit()
        self.txt_output.setMinimumWidth(100)
        self.process_list.setMinimumWidth(100)

        self.splitter = QSplitter()
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.splitter.sizePolicy().hasHeightForWidth())
        self.splitter.setSizePolicy(sizePolicy)
        self.splitter.setOrientation(Qt.Horizontal)

        self.main_layout.addLayout(self.layout_connection)
        self.splitter.addWidget(self.process_list)
        self.splitter.addWidget(self.txt_output)
        self.main_layout.addWidget(self.splitter)

        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName(u"statusbar")
        self.setStatusBar(self.statusbar)
        self.setWindowTitle("Process Monitor")
        self.txt_conenction.setPlaceholderText("ws://127.0.0.1:8766")
        self.txt_conenction.setText("ws://127.0.0.1:8766")
        self.btn_connect.setText("Connect")

        self.process_list.action_requested.connect(self.on_action_requested)

        self.set_disconnected_ui()

    def on_action_requested(self, uid, action):
        logger.info("New action request: %s, %s", uid, action)
        self.send_message(json.dumps({"action": action, "data": {"uid": uid}}))

    def set_disconnected_ui(self):
        self.process_list.setDisabled(True)
        self.btn_connect.setDisabled(False)
        self.statusbar.showMessage("Disconnected. Connected to a websocket server")

    def set_connected_ui(self):
        self.process_list.setDisabled(False)
        self.btn_connect.setDisabled(True)
        self.statusbar.showMessage("Connected.")


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
