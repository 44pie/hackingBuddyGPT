from hackingBuddyGPT.capabilities import SSHRunCommand, SSHTestCredential, GsocketRunCommand, GsocketTestCredential
from hackingBuddyGPT.capabilities.local_shell import LocalShellCapability
from hackingBuddyGPT.usecases.base import AutonomousAgentUseCase, use_case
from hackingBuddyGPT.utils import SSHConnection
from hackingBuddyGPT.utils.local_shell import LocalShellConnection
from hackingBuddyGPT.utils.gsocket_connection import GsocketConnection
from typing import Union
from .common import Privesc


class LinuxPrivesc(Privesc):
    conn: Union[SSHConnection, LocalShellConnection, GsocketConnection] = None
    system: str = "linux"

    def init(self):
        super().init()
        if isinstance(self.conn, LocalShellConnection):
            self.add_capability(LocalShellCapability(conn=self.conn), default=True)
            self.add_capability(SSHTestCredential(conn=self.conn))
        elif isinstance(self.conn, GsocketConnection):
            self.add_capability(GsocketRunCommand(conn=self.conn), default=True)
            self.add_capability(GsocketTestCredential(conn=self.conn))
        else:
            self.add_capability(SSHRunCommand(conn=self.conn), default=True)
            self.add_capability(SSHTestCredential(conn=self.conn))


@use_case("Linux Privilege Escalation")
class LinuxPrivescUseCase(AutonomousAgentUseCase[LinuxPrivesc]):
    pass
