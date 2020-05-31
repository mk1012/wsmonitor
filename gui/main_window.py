# -*- coding: utf-8 -*-

import sys

from PySide2 import QtWebSockets
from PySide2.QtCore import (QRect, QUrl)
from PySide2.QtWidgets import *
from gui.process_widget import ProcessListWidget


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

    def on_connected(self):
        print("connected")
        self._ws_connected = True
        self.set_connected_ui()

    def on_disconnected(self):
        print("disconnected")
        self._ws_connected = False
        self.set_disconnected_ui()

    def send_message(self):
        print("client: send_message")
        self.client.sendTextMessage("Mark")

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
        self.main_layout.addLayout(self.layout_connection)
        self.main_layout.addWidget(self.process_list)
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName(u"statusbar")
        self.setStatusBar(self.statusbar)
        self.setWindowTitle("Process Monitor")
        self.txt_conenction.setPlaceholderText("ws://127.0.0.1:8766")
        self.txt_conenction.setText("ws://127.0.0.1:8766")
        self.btn_connect.setText("Connect")
        self.set_disconnected_ui()

    def set_disconnected_ui(self):
        self.process_list.setDisabled(True)
        self.statusbar.showMessage("Disconnected. Connected to a websocket server")

    def set_connected_ui(self):
        self.process_list.setDisabled(False)
        self.statusbar.showMessage("Connected.")


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
