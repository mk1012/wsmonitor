# -*- coding: utf-8 -*-
import json
import sys
from json import JSONDecodeError

from PySide2 import QtWebSockets
from PySide2.QtCore import (QRect, QUrl, Qt)
from PySide2.QtGui import QTextCursor
from PySide2.QtWidgets import *
from gui.process_widget import ProcessListWidget
from process_data import ProcessData


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
            self.send_message()
            return

        self.establish_connection()

    def establish_connection(self):
        server_url = self.txt_conenction.text()
        print("Connecting to: ", server_url)
        self.client.open(QUrl(server_url))

    def on_message(self, message):
        print("text msg: ", message)
        try:
            json_data = json.loads(message)
        except JSONDecodeError:
            print("Invalid message: ", message)
            return

        typ = json_data["type"]
        if typ == "state":
            data = json_data["data"]
            pdatas = set([ProcessData.from_dict(entry) for entry in data])
            self.process_list.update_process_data(pdatas)
        if typ == "process_state_changed":
            state = json_data["data"]
            uid = json_data["uid"]
            self.process_list.update_single_process_state(uid, state)
        if typ == "action_response":
            response = json_data["data"]
            uid = response["uid"]
            result = response["result"]
            self.process_list.on_action_completed(uid, result)
        if typ == "outputevent":
            self.txt_output.moveCursor(QTextCursor.End)
            self.txt_output.insertPlainText(json_data["data"])

    def on_connected(self):
        print("connected")
        self._ws_connected = True
        self.set_connected_ui()

    def on_disconnected(self):
        print("disconnected")
        self._ws_connected = False
        self.set_disconnected_ui()

    def send_message(self, msg):
        if not self._ws_connected:
            print("CLIENT NOT CONENCTED!")
            return
        print("send_message", msg)
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
        print("New action request", uid, action)
        self.send_message(json.dumps({"type": "action", "action": action, "uid": uid}))

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
