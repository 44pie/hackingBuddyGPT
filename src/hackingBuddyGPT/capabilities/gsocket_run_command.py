import re
from dataclasses import dataclass
from typing import Tuple

from hackingBuddyGPT.utils.gsocket_connection import GsocketConnection
from hackingBuddyGPT.utils.shell_root_detection import got_root

from .capability import Capability


@dataclass
class GsocketRunCommand(Capability):
    conn: GsocketConnection
    timeout: int = 10

    def describe(self) -> str:
        return "give a command to be executed and I will respond with the terminal output when running this command over gsocket on the linux machine. The given command must not require user interaction. Do not use quotation marks in front and after your command."

    def get_name(self):
        return "exec_command"

    def __call__(self, command: str) -> Tuple[str, bool]:
        if command.startswith(self.get_name()):
            cmd_parts = command.split(" ", 1)
            if len(cmd_parts) == 1:
                command = ""
            else:
                command = cmd_parts[1]

        try:
            stdout, stderr, rc = self.conn.run(command)
        except Exception:
            print("TIMEOUT! Could we have become root?")
            stdout = ""

        lines = stdout.split("\n")
        last_line = lines[-1] if lines else ""

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        last_line = ansi_escape.sub("", last_line)

        return stdout, got_root(self.conn.hostname, last_line)
