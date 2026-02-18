import os
import re
import select
import time
import uuid
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Tuple

from hackingBuddyGPT.utils.configurable import configurable


@configurable("gsocket", "connects to a remote host via gsocket (gs-netcat)")
@dataclass
class GsocketConnection:
    gsocket_secret: str
    hostname: str = "target"
    username: str = "unknown"
    password: str = ""
    host: str = ""
    port: int = 0
    keyfilename: str = ""
    gs_netcat_path: str = "gs-netcat"
    timeout: int = 30

    _process: subprocess.Popen = field(default=None, init=False, repr=False)  # type: ignore[assignment]
    _initialized: bool = field(default=False, init=False)

    def init(self):
        self._start_gsocket()
        self._initialized = True

    def _start_gsocket(self):
        if self._process and self._process.poll() is None:
            return

        self._process = subprocess.Popen(
            [self.gs_netcat_path, "-s", self.gsocket_secret, "-i"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )

        time.sleep(2)

        if self._process.poll() is not None:
            out = self._process.stdout.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"gs-netcat failed to start: {out}")

        self._drain_initial_output()

    def _drain_initial_output(self):
        while True:
            ready, _, _ = select.select([self._process.stdout], [], [], 1.5)
            if not ready:
                break
            data = self._read_available()
            if not data:
                break

    def _read_available(self) -> bytes:
        fd = self._process.stdout.fileno()
        data = b""
        while True:
            ready, _, _ = select.select([self._process.stdout], [], [], 0.05)
            if not ready:
                break
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data += chunk
        return data

    def _send(self, data: str):
        if self._process is None or self._process.poll() is not None:
            self._start_gsocket()
        self._process.stdin.write((data + "\n").encode("utf-8"))
        self._process.stdin.flush()

    def _read_until_marker(self, marker: str, timeout: int = None) -> Tuple[str, bool]:
        if timeout is None:
            timeout = self.timeout
        output = b""
        marker_bytes = marker.encode("utf-8")
        deadline = time.time() + timeout
        found = False
        fd = self._process.stdout.fileno()

        while time.time() < deadline:
            remaining = max(0.1, deadline - time.time())
            ready, _, _ = select.select([self._process.stdout], [], [], min(remaining, 0.5))
            if ready:
                chunk = os.read(fd, 65536)
                if chunk:
                    output += chunk
                    if marker_bytes in output:
                        found = True
                        break
            if self._process.poll() is not None:
                try:
                    remaining_data = os.read(fd, 65536)
                    if remaining_data:
                        output += remaining_data
                except OSError:
                    pass
                break

        return output.decode("utf-8", errors="replace"), found

    def run(self, cmd: str, *args, **kwargs) -> Tuple[str, str, int]:
        if not self._initialized:
            self.init()

        if not cmd.strip():
            return "", "", 0

        end_marker = f"__GSEND_{uuid.uuid4().hex[:12]}__"
        rc_marker = f"__GSRC_{uuid.uuid4().hex[:12]}__"

        full_cmd = f"{cmd}; echo {rc_marker}$?{rc_marker}; echo {end_marker}"
        self._send(full_cmd)

        raw_output, marker_found = self._read_until_marker(end_marker, self.timeout)

        lines = raw_output.split("\n")
        result_lines = []
        return_code = 0
        stderr_text = ""

        if not marker_found:
            stderr_text = f"TIMEOUT: end marker not found after {self.timeout}s, output may be incomplete"
            return_code = -1

        for line in lines:
            if end_marker in line:
                break
            if rc_marker in line:
                rc_match = re.search(rf"{re.escape(rc_marker)}(\d+){re.escape(rc_marker)}", line)
                if rc_match:
                    return_code = int(rc_match.group(1))
                continue
            if full_cmd.strip() in line.strip():
                continue
            result_lines.append(line)

        stdout = "\n".join(result_lines).strip()

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        stdout = ansi_escape.sub("", stdout)

        return stdout, stderr_text, return_code

    def new_with(self, *, gsocket_secret=None, hostname=None, username=None, password=None, **kwargs) -> "GsocketConnection":
        return GsocketConnection(
            gsocket_secret=gsocket_secret or self.gsocket_secret,
            hostname=hostname or self.hostname,
            username=username or self.username,
            password=password or self.password,
            gs_netcat_path=self.gs_netcat_path,
            timeout=self.timeout,
        )

    def close(self):
        if self._process and self._process.poll() is None:
            self._process.stdin.close()
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None

    def __del__(self):
        self.close()
