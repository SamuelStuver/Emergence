import shutil
import os
import json
from logger import logger


def get_project_root():
    return os.path.abspath(os.curdir)


def backup_file(file_path, new_path=None):
    ext = os.path.splitext(file_path)[1]
    if not new_path:
        new_path = f"{os.path.splitext(file_path)[0]}_backup{ext}"

    shutil.copyfile(file_path, new_path)
    logger.debug(f"backed up file {file_path} to {new_path}")
    return new_path


def delete_file(file_path):
    if os.path.isfile(file_path):

        os.remove(file_path)
        logger.debug(f"deleted file {file_path}")
        return True
    else:
        logger.warning(f"file does not exist to delete: {file_path}")
        return False

# VALIDATIONS


def validate_note(note, expected):
    logger.info("Verify that the note has the correct data")
    logger.debug(f"note: {note}")
    logger.debug(f"expected: {expected}")
    for param in expected.keys():
        assert getattr(note, param) == expected[param]


def validate_config(expected):
    config_path = os.path.join(get_project_root(), "config.json")

    logger.info(f"Verify that the correct values are used in config: {config_path}")
    logger.debug(f"expected: {expected}")
    with open(config_path, "r") as config_file:
        config = json.load(config_file)
        logger.debug(f"config: {config}")
    for param in expected.keys():
        assert config[param] == expected[param]


# if __name__ == "__main__":
#     # backup_file(r"C:\Users\samue\Projects\sjournal\config.json")
#     # delete_file(r"C:\Users\samue\Projects\sjournal\config_backup.json")
