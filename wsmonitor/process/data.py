from typing import Optional, List, Union, Dict, Any
from wsmonitor.format import JsonFormattable


class ProcessData(JsonFormattable):
    UNKNOWN = "Unknown"
    INITIALIZED = "Initialized"
    STARTING = "Starting"
    STARTED = "Started"
    STOPPING = "Stopping"
    ENDED = "Ended"

    __slots__ = ('uid', 'command', 'as_process_group', 'state', 'exit_code')

    def __init__(self, uid: str, command: str, as_process_group=False, state="Initialized", exit_code=None) -> None:
        JsonFormattable.__init__(self)
        self.uid = uid
        self.command: str = command
        self.as_process_group: bool = as_process_group
        self.state: str = state
        self.exit_code: Optional[int] = exit_code

    def __hash__(self):
        return self.uid.__hash__()

    def __eq__(self, other):
        if not isinstance(other, ProcessData):
            return False
        return self.uid == other.uid

    def is_in_state(self, state):
        return self.state == state

    def reset(self):
        self.state = ProcessData.INITIALIZED
        self.exit_code = None

    def ensure_exit_code(self, code=-1):
        # ensure there is an exit code
        if self.exit_code is None:
            self.exit_code = code

    def state_info(self):
        if self.state == ProcessData.ENDED:
            return f"State: {self.state} with {self.exit_code}"
        return f"State: {self.state}"

    def has_ended_successfully(self):
        return self.state == ProcessData.ENDED and self.exit_code == 0


class ProcessSummaryEvent(JsonFormattable):
    __slots__ = ("processes",)

    def __init__(self, processes: List[ProcessData]):
        super().__init__()
        self.processes = processes

    def to_json(self):
        return {"type": self.__class__.__name__, "data": [proc.to_json() for proc in self.processes]}

    @classmethod
    def from_json(cls, json_data):
        return ProcessSummaryEvent([ProcessData.from_json(proc_data["data"]) for proc_data in json_data])


class StateChangedEvent(JsonFormattable):
    __slots__ = ("uid", 'state', 'exit_code')

    def __init__(self, uid: str, state: str, exit_code: Optional[int] = None):
        super().__init__()
        self.uid = uid
        self.state = state
        self.exit_code = exit_code


class OutputEvent(JsonFormattable):
    __slots__ = ('uid', 'output')

    def __init__(self, uid: str, output: str):
        super().__init__()
        self.uid = uid
        self.output = output


class ActionResponse(JsonFormattable):
    __slots__ = ('uid', 'action', 'success', 'data')

    def __init__(self, uid: str, action: str, success=True, data: Any = None):
        self.action = action
        self.success = success
        self.uid = uid
        self.data = data


class ActionFailure(ActionResponse):

    def __init__(self, uid: Optional[str], action: str, msg: Union[Dict, str]):
        super().__init__(uid, action, False, data=msg)
