class ProcessData(object):
    UNKNONW = "unknown"
    RUNNING = "running"
    STOPPED = "stopped"

    INITIALIZED = "initialized"
    STARTING = "starting"
    BEING_KILLED = "being_killed"
    ENDED = "ended"

    def __init__(self, uid: str, command: str, as_process_group=False):
        self.uid = uid
        self.command = command
        self.as_process_group = as_process_group
        self.state = None
        self.exit_code = None

    @staticmethod
    def from_dict(data):
        uid = data["uid"]
        command = data["command"]
        as_process_group = data["as_process_group"]
        pdata = ProcessData(uid, command, as_process_group)
        if "state" in data:
            pdata.state = data["state"]
        return pdata

    def as_dict(self):
        return {"uid": self.uid, "command": self.command,
                "as_process_group": self.as_process_group,
                "type": self.__class__.__name__}

    def __str__(self):
        return str(self.as_dict())

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

    def ensure_exit_code(self, code=-1):
        # ensure there is an exit code
        if self.exit_code is None:
            self._exit_code = code
