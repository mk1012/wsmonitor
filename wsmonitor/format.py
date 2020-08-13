import json


class JsonFormattable:
    __slots__ = ()

    def to_json(self):
        return {"type": self.__class__.__name__, "data": {slot: getattr(self, slot) for slot in self.__slots__}}

    @classmethod
    def from_json(cls, json_data):
        args = (None if not slot in json_data else json_data[slot] for slot in cls.__slots__)
        return cls(*args)

    def set_from_json(self, json_data):
        for slot in self.__slots__:
            setattr(self, slot, json_data[slot])

    def __str__(self):
        return self.to_json_str()

    def to_json_str(self):
        return json.dumps(self.to_json())
