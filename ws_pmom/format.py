class JsonFormattable():
    def __init__(self, data):
        self.data = data
        self.type = self.__class__.__name__  # .lower()

    def get_data(self):
        return {"type": self.type, "data": self.data}

    def __str__(self):
        return str(self.get_data())