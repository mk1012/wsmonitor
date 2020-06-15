import json


class JsonFormattable:
    __slots__ = ()



    def to_json(self):
        return {"type": self.__class__.__name__, "data": {slot: getattr(self, slot) for slot in self.__slots__}}

    @classmethod
    def from_json(cls, json_data):
        args = (json_data[slot] for slot in cls.__slots__)
        return cls(*args)

    def set_from_json(self, json_data):
        for slot in self.__slots__:
            setattr(self, slot, json_data[slot])

    def __str__(self):
        return self.to_json_str()

    def to_json_str(self):
        return json.dumps(self.to_json())


if __name__ == "__main__":
    jf = JsonFormattable.from_json({})
    print(jf)


    class Test(JsonFormattable):
        __slots__ = ("test",)

        def __init__(self, test):
            self.test = test


    print(Test.__slots__)
    t1 = Test.from_json({"test": 43})
    print(t1)
    jf = Test(22)
    jf.test = 12
    print(jf.test, jf.to_json())
    jf.from_json({"test": "fisch"})
    print(jf.test)
