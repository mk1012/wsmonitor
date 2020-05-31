# -*- coding: utf-8 -*-

import sys

from PySide2.QtCore import (QRect)
from PySide2.QtWidgets import *
from process_widget import ProcessListWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setup_ui()

    def setup_ui(self):
        self.main_widget = QWidget(self)
        self.main_layout = QVBoxLayout()
        self.layout_connection = QHBoxLayout()
        self.lbl_conenction = QLineEdit()
        self.btn_connect = QPushButton()
        self.layout_connection.addWidget(self.lbl_conenction)
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
        self.lbl_conenction.setPlaceholderText("Websocket Server")
        self.btn_connect.setText("Connect")
        self.set_disconnected_ui()


    def set_disconnected_ui(self):
        self.process_list.setDisabled(True)
        self.statusbar.showMessage("Disconnected. Connected to a websocket server")

    def set_connected_ui(self):
        self.process_list.setDisabled(False)
        self.statusbar.showMessage("Connected.")

if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
