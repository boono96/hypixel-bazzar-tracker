import json


class file_handeler:

    @staticmethod
    def load_json_file(file):
        with open(file, 'r') as f:
            return json.load(f)

    @staticmethod
    def write_file( information, file):
        with open(file, "w") as f:
            f.write(information)

    @staticmethod
    def write_file_json( information, file):
        with open(file, "w") as f:
            info = json.dumps(information)
            f.write(str(info))

