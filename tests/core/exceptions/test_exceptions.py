import pytest

from zee_api.core.exceptions.invalid_config_file_error import InvalidConfigFileError


def test_invalid_config_file_error():
    with pytest.raises(InvalidConfigFileError) as e:
        raise InvalidConfigFileError("filename.txt")

    assert str(e.value) == "File 'filename.txt' is not a valid yaml file"
