from typing import Set, Dict

from PySide2.QtCore import Signal, Qt
from PySide2.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QLabel, QSizePolicy

from wsmonitor.gui.process_widget import logger, ProcessWidget
from wsmonitor.process.data import ActionResponse, StateChangedEvent, ProcessData


class ProcessListWidget(QScrollArea):
    action_requested = Signal(str, str)
    process_state_changed = Signal(str, str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_data = set()
        self.process_widget_map = {}  # type: Dict[str, ProcessWidget]

        self.main_widget = QWidget()
        self.process_layout = QVBoxLayout()
        self.process_layout.setContentsMargins(2, 2, 2, 2)
        self.main_widget.setLayout(self.process_layout)

        self.lbl_default = QLabel(text="No processes found")
        self.process_layout.addWidget(self.lbl_default)
        self.process_layout.addStretch()

        # Configure ScrollArea
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setWidgetResizable(True)
        self.setWidget(self.main_widget)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.setMinimumWidth(380)

    def on_action_completed(self, response: ActionResponse):
        logger.info("Action completed: %s", response)
        self.process_widget_map[response.uid].on_action_completed(response.action)

    def update_single_process_state(self, event: StateChangedEvent):
        self.process_widget_map[event.uid].update_state(event.state, event.exit_code)

    def update_process_data(self, updated_process_data: Set[ProcessData]):
        potentially_updated = set()
        for process_data in updated_process_data:
            if process_data in self.process_data:
                potentially_updated.add(process_data)

        new_processes = updated_process_data - self.process_data
        unknown_processes = self.process_data - updated_process_data
        print(potentially_updated, new_processes, unknown_processes)
        # TODO(mark): update process data sets with new data
        for known_process in potentially_updated:
            widget = self.process_widget_map[known_process.uid]
            widget.on_update_process_data(known_process)

        for new_process in new_processes:
            widget = ProcessWidget(new_process)
            self.process_widget_map[new_process.uid] = widget
            widget.actionRequested.connect(self.action_requested)
            widget.process_state_changed.connect(self.process_state_changed)
            self.process_layout.insertWidget(0, widget)

        # TODO(mark): unknown processes
        for process in unknown_processes:
            widget = self.process_widget_map[process.uid]
            logger.info("Removing widget: %s", process.uid)
            self.process_layout.removeWidget(widget)
            del self.process_widget_map[process.uid]
            widget.deleteLater()

        self.process_data = new_processes | potentially_updated
        self.lbl_default.setVisible(len(self.process_data) == 0)

        return new_processes, unknown_processes
