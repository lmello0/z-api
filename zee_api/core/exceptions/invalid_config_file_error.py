class InvalidConfigFileError(Exception):
    def __init__(self, file: str) -> None:
        super().__init__(f"File '{file}' is not a valid yaml file")
