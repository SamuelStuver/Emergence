import argparse
import json
import re
import os
import shutil
import PySimpleGUI as sg
from datetime import datetime
import sqlite3
from sqlite3 import Error
from rich.table import Table
from rich.console import Console
from utils import count_backups, get_newest_file, range_parser, copy_to_clipboard


class SJournal:
    def __init__(self, args):
        self.db_file = ""
        self.journal_dir = ""
        self.journal_name = ""
        self.args = args
        self.load()

        self.create_connection()
        self.console = Console()
        self.table = Table(title="Notes")
        self.setup_table()

    def setup_table(self):
        self.table.add_column("ID", style="cyan")
        self.table.add_column("Timestamp")
        self.table.add_column("Category", style="bold green")
        self.table.add_column("Content", style="white")

    def handle_args(self):
        # If a command was specified, use it. Otherwise, assume List command
        if self.args.command:
            if self.args.command != "load":
                return getattr(self, self.args.command)
        else:
            return self.list

    def create_connection(self):
        try:
            conn = sqlite3.connect(self.db_file)
            self.connection = conn
        except Error:
            print(Error)
            self.connection = None

    def close_connection(self):
        self.connection.close()

    def run(self):
        self.setup()
        action = self.handle_args()
        if action:
            action()
        self.close_connection()

    def setup(self):
        if not self.table_exists("notes"):
            self.create_table("notes", "id integer PRIMARY KEY, timestamp text, category text, content text")

        return self

    def table_exists(self, table_name):
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        # if the count is 1, then table exists
        if cursor.fetchone()[0] == 1:
            return True
        else:
            return False

    def create_table(self, name, table_string):
        cursor = self.connection.cursor()
        query = f"CREATE TABLE {name}({table_string})"
        cursor.execute(query)
        self.connection.commit()

    def insert_into_database_table(self, table_name, note):
        cursor = self.connection.cursor()
        cursor.execute(f"INSERT INTO {table_name} (id, timestamp, category, content) VALUES (:id, :timestamp, :category, :content)", note.dict)
        self.connection.commit()

    def add_gui(self):
        sg.theme('DarkGrey')

        layout = [
            [sg.Text(f"Add note to table \"{self.table.title}\" at {self.db_file}")],
            [
              sg.Text('{:10}'.format('Category:')),
              sg.InputText(key="category",
                           default_text="General",
                           size=(25, 1))
            ],
            [
              sg.Text('{:10}'.format('Style:')), sg.InputText(key="style", size=(25, 1))
            ],
            [
              sg.Text('{:10}'.format('Content:')), sg.InputText(key="content", size=(50, 1))
            ],
            [
              sg.Button('Save Note'), sg.Button('Cancel')
            ]
        ]

        window = sg.Window('Window Title', layout, font='Courier')

        while True:
            event, values = window.read()
            if event == sg.WIN_CLOSED or event == 'Cancel':
                break
            elif event == "Save Note":
                break
        window.close()

        if event == "Save Note":
            return values
        else:
            return None

    def add(self):

        if len(self.args.content) == 0:
            values = self.add_gui()
            if values:
                self.args.style = values['style']
                self.args.category = values['category']
                self.args.content = [values['content']]
            else:
                exit()
        note_content = ' '.join(self.args.content)
        if self.args.style:
            note_content = f"[{self.args.style}]{note_content}[/]"

        note_data = {"category": self.args.category, "content": note_content}
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT id FROM notes ORDER BY id DESC LIMIT 1")
        try:
            most_recent_id = cursor.fetchone()[0]
        except TypeError:
            most_recent_id = 0
        note = Note(most_recent_id+1, note_data["category"], note_data["content"])
        self.insert_into_database_table("notes", note)
        self.connection.commit()

    def insert_into_print_table(self, note):
        self.table.add_row(str(note.id), str(note.timestamp), str(note.category), str(note.content))

    def show_print_table(self):
        self.console.print(self.table)

    def edit(self):
        cursor = self.connection.cursor()
        if self.args.id:
            id_to_edit = self.args.id
        else:
            cursor.execute(f"SELECT id FROM notes ORDER BY id DESC LIMIT 1")
            id_to_edit = cursor.fetchone()[0]

        cursor.execute(f"SELECT category, content, timestamp FROM notes WHERE id={id_to_edit} ORDER BY id DESC LIMIT 1")
        old_category, old_content, old_timestamp = cursor.fetchone()

        copy_to_clipboard(old_content)
        print(f'Editing Note #{id_to_edit} (copied to clipboard): "{old_content}"')

        new_content = input("Enter new note text: ")

        new_note = Note(id_to_edit, old_category, new_content)
        new_note.timestamp = old_timestamp
        cursor.execute(f'DELETE FROM notes WHERE id={id_to_edit}')
        self.insert_into_database_table("notes", new_note)
        self.connection.commit()

    def list(self):
        cursor = self.connection.cursor()

        query = "SELECT * FROM notes"
        if hasattr(self.args, 'category') and self.args.category is not None:
            query += f" WHERE category='{self.args.category}'"
        query += " ORDER BY id DESC"

        if hasattr(self.args, "quantity") and not self.args.all:
            try:
                query += f" LIMIT {self.args.quantity[0]}"
            except TypeError:
                query += f" LIMIT {self.args.quantity}"
        elif not hasattr(self.args, "all"):
            query += f" LIMIT 5"

        cursor.execute(query)
        items_to_show = cursor.fetchall()
        if hasattr(self.args, "reverse") and self.args.reverse:
            items_to_show = items_to_show[::-1]
        for item in items_to_show:
            note = Note(item[0], item[2], item[3], date_time=datetime.strptime(item[1], "%m-%d-%y %H:%M:%S"))
            self.insert_into_print_table(note)
            # print(note)
        self.show_print_table()

    def delete(self):
        ids_to_delete = range_parser(self.args.delete_criteria)
        print(ids_to_delete)
        cursor = self.connection.cursor()
        for id in ids_to_delete:
            print(id)
            if isinstance(id, int):
                print(f"DELETING NOTE #{id}")
                cursor.execute(f'DELETE FROM notes WHERE id={id}')
            else:
                regex_below = r"\W(\d*)"
                regex_above = r"(\d*)\W"
                match_below = re.search(regex_below, id)
                match_above = re.search(regex_above, id)

                if match_below and match_below.group(1).isnumeric():
                    for i in range(0, int(match_below.group(1))+1):
                        print(f"DELETING NOTE #{i}")
                        cursor.execute(f'DELETE FROM notes WHERE id={i}')
                elif match_above and match_above.group(1).isnumeric():
                    cursor.execute('SELECT max(id) FROM notes')
                    max_id = cursor.fetchone()[0]
                    for i in range(int(match_above.group(1)), max_id+1):
                        print(f"DELETING NOTE #{i}")
                        cursor.execute(f'DELETE FROM notes WHERE id={i}')
        self.connection.commit()

    def erase(self):
        cursor = self.connection.cursor()
        cursor.execute('DELETE FROM notes')
        self.connection.commit()

    def search(self):

        if hasattr(self.args, 'search_criteria'):
            regex = f".*{self.args.search_criteria[0]}.*"
        else:
            regex = ".*"

        cursor = self.connection.cursor()
        query = "SELECT * FROM notes"
        if hasattr(self.args, 'category') and self.args.category is not None:
            query += f" WHERE category='{self.args.category}'"
        query += " ORDER BY id DESC"

        if hasattr(self.args, "quantity") and not self.args.all:
            query += f" LIMIT {self.args.quantity}"

        cursor.execute(query)
        for item in cursor.fetchall():
            id = item[0]
            category = item[2]
            content = item[3]
            match = re.search(regex.lower(), content.lower())
            if match:
                note = Note(id, category, content, date_time=datetime.strptime(item[1], "%m-%d-%y %H:%M:%S"))
                self.insert_into_print_table(note)
                # print(note)
        self.show_print_table()

    def fetch(self):
        notes = []
        cursor = self.connection.cursor()
        query = "SELECT * FROM notes ORDER BY id DESC"
        cursor.execute(query)

        for item in cursor.fetchall():
            note = Note(item[0], item[2], item[3], date_time=datetime.strptime(item[1], "%m-%d-%y %H:%M:%S"))
            notes.append(note)

        return notes

    def backup(self):
        backup_dir = os.path.join(self.journal_dir, "backups", self.journal_name)

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        if self.args.filename is None:
            timestamp = datetime.now().strftime("%y_%m_%d_%H_%M_%S")
            new_filename = os.path.join(backup_dir, f"backup_{self.journal_name}_{timestamp}.db")
        else:
            new_filename = os.path.join(backup_dir, self.args.filename)

        new_filename = new_filename.replace(".db", "") + ".db"
        print(f"BACKING UP {self.db_file} TO FILE {new_filename}")
        shutil.copy(self.db_file, new_filename)

    def restore(self):
        backup_dir = os.path.join(self.journal_dir, "backups", self.journal_name)

        if self.args.filename is None:
            filename = get_newest_file(backup_dir)
        else:
            filename = os.path.join(backup_dir, self.args.filename)

        if filename and os.path.exists(filename.replace(".db", "") + ".db"):
            filename = filename.replace(".db", "") + ".db"
            print(f"RESTORING BACKUP FROM {filename}. REPLACING {self.db_file}")
            shutil.copy(filename, self.db_file)
            # self.db_file = filename
        else:
            print(f"Failed to restore backup: file not found.")

    def load(self):
        if hasattr(self.args, 'journal_name'):
            # configure the json file to use the new name
            with open("config.json", "r") as config_file:
                config = json.load(config_file)

            config["journal_name"] = self.args.journal_name
            confstring = json.dumps(config)
            with open("config.json", "w") as config_file:
                config_file.write(confstring)
            msg = "Set journal to"

        else:
            # Use the file specified in the config file
            with open("config.json", "r") as config_file:
                config = json.load(config_file)
            msg = "Using journal at"

        self.db_file = os.path.join(config["journal_dir"], f"{config['journal_name']}.db")
        self.journal_dir = config["journal_dir"]
        self.journal_name = config["journal_name"]
        if not os.path.exists(self.journal_dir):
            os.makedirs(self.journal_dir)
        print(f"{msg} {self.db_file}")


class Note:
    def __init__(self, id, category, content, date_time=None):
        self.id = id
        self.category = category
        self.content = content
        if not date_time:
            self.date_time = datetime.now()
        else:
            self.date_time = date_time
        self.timestamp = datetime.strftime(self.date_time, "%m-%d-%y %H:%M:%S")

    @property
    def dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "content": self.content,
            "timestamp": self.timestamp
        }

    @property
    def values(self):
        return [self.id, self.timestamp, self.category, self.content]

    def __str__(self):
        return f"[{self.id}] [{datetime.strftime(self.date_time, '%m-%d-%Y %H:%M:%S')}] [{self.category}] - {self.content}"

    def __repr__(self):
        return self.__str__()


def parse_args():

    # Read environment from command line args
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', help='Commands', title='Commands')

    # Test/Dev argument
    parser.add_argument('-t', '--test', action='store_true',
                        help='Run the program against a test database for testing features')

    # Add command
    parser_add = subparsers.add_parser('add', help='Add a note to the database')
    parser_add.add_argument('content', nargs='*', action='store', type=str, default=None,
                            help="Content of note")
    parser_add.add_argument('-c', '--category', default='General', action='store',
                            help="Choose a category for the note to be added under")
    parser_add.add_argument('-s', '--style', default=None, action='store',
                            help="Specify a rich console markup style to the note for display")

    # Edit command
    parser_edit = subparsers.add_parser('edit', help='Edit a note to the database')
    parser_edit.add_argument('id', nargs='?', action='store', type=int, default=None,
                             help="ID of note to edit")

    # List command
    parser_list = subparsers.add_parser('list', help='List notes in the database')
    parser_list.add_argument('quantity', nargs='*', action='store', default=5, type=int,
                             help="Specify the amount of results to list")

    parser_list.add_argument('-a', '--all', action='store_true',
                             help="List all notes under given criteria")

    parser_list.add_argument('-c', '--category', nargs='?', default=None, action='store',
                             help="Choose a category of notes to list")
    parser_list.add_argument('-r', '--reverse', action='store_true',
                             help="Display notes in reverse chronological order")

    # Delete command
    parser_delete = subparsers.add_parser('delete', help='Delete one or multiple notes from the database')
    parser_delete.add_argument('delete_criteria', nargs='*', action='store', type=str)

    # Erase command
    parser_erase = subparsers.add_parser('erase', help='Delete all notes from the database')

    # Backup command
    parser_backup = subparsers.add_parser('backup', help='Backup the database. 10 backups are stored at a time')
    parser_backup.add_argument('-f', '--filename', action='store', default=None,
                               help='Choose a filename to use for the backup file. By default, the current timestamp will be used')

    # Restore command
    parser_restore = subparsers.add_parser('restore', help='Restore the database from a file. If --filename is not given, restore the latest backup')
    parser_restore.add_argument('-f', '--filename', action='store', default=None,
                               help='Specify a file to backup data from. If not specified, the latest backup file will be used')

    # Help command
    parser_help = subparsers.add_parser('help', help='Display help text')
    parser_help.add_argument('help_command', nargs='?', action='store', default=None)

    # Search command
    parser_search = subparsers.add_parser('search', help='List notes matching search term')
    parser_search.add_argument('search_criteria', nargs='*', action='store', type=str)

    # Load command
    parser_load = subparsers.add_parser('load', help="Load a journal or create a new one if it doesn't exist")
    parser_load.add_argument('journal_name', action='store', type=str)

    args = parser.parse_args()
    parsers = {
        'add':parser_add,
        'edit':parser_edit,
        'list':parser_list,
        'delete':parser_delete,
        'erase':parser_erase,
        'backup':parser_backup,
        'restore':parser_restore,
        'search':parser_search,
        'load':parser_load,
        'help':parser_help
    }

    if args.test:
        print(args)

    if args.command == "help":
        if not args.help_command or args.help_command not in parsers.keys():
            parser.print_help()
        else:
            parsers[args.help_command].print_help()
        exit()

    return args


if __name__ == "__main__":
    args = parse_args()
    print(args)
    # if args.test:
    #     db_file = r"C:\sqlite\db\notes_test.db"
    # else:
    #     db_file = r"C:\sqlite\db\notes.db"
    scratchpad = SJournal(args)
    scratchpad.run()
    # scratchpad.add_note()
