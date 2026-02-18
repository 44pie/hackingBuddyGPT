from dataclasses import dataclass
from typing import Tuple

from hackingBuddyGPT.utils.gsocket_connection import GsocketConnection

from .capability import Capability


@dataclass
class GsocketTestCredential(Capability):
    conn: GsocketConnection

    def describe(self) -> str:
        return "give credentials to be tested by attempting su on the gsocket shell. Note: credential testing over gsocket is best-effort since su may require a TTY."

    def get_name(self):
        return "test_credential"

    def __call__(self, username: str, password: str) -> Tuple[str, bool]:
        try:
            test_cmd = (
                f"python3 -c \"import pty,os; "
                f"pid=os.fork(); "
                f"exec('if pid==0:\\n"
                f" os.execlp(\\\"su\\\",\\\"su\\\",\\\"-c\\\",\\\"whoami\\\",\\\"{username}\\\")') "
                f"if pid!=0 else None; "
                f"import time; time.sleep(0.5); "
                f"os.write(1,b'{password}\\\\n'); "
                f"os.waitpid(pid,0)\" 2>/dev/null"
            )
            stdout_py, _, rc_py = self.conn.run(test_cmd)

            if stdout_py.strip():
                user = stdout_py.strip().split("\n")[-1].strip()
                if user == "root":
                    return "Login as root was successful\n", True
                elif user == username:
                    return f"Authentication successful as {username}, but user is not root\n", False

            stdout_script, _, rc_script = self.conn.run(
                f"echo '{password}' | script -qc 'su - {username} -c whoami' /dev/null 2>/dev/null"
            )
            if stdout_script.strip():
                user = stdout_script.strip().split("\n")[-1].strip()
                if user == "root":
                    return "Login as root was successful\n", True
                elif user == username:
                    return f"Authentication successful as {username}, but user is not root\n", False

            stdout_sudo, _, rc_sudo = self.conn.run(
                f"echo '{password}' | sudo -S -u {username} whoami 2>/dev/null"
            )
            if stdout_sudo.strip():
                user = stdout_sudo.strip().split("\n")[-1].strip()
                if user == "root":
                    return "Login as root was successful\n", True
                elif user == username:
                    return f"Authentication successful as {username}, but user is not root\n", False

            return "Authentication error, credentials are wrong or su requires TTY\n", False
        except Exception as e:
            return f"Error testing credentials: {str(e)}\n", False
