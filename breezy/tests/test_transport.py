# Copyright (C) 2026 Breezy developers
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Compatibility shim for transport tests.

The transport tests have been moved to the :mod:`dromedary.tests.test_transport`
package; this shim re-exports its public surface so existing callers
(and type checkers) keep working. Enumerated imports rather than
``from X import *`` so ``mypy`` can see the attributes —
star imports don't propagate attribute visibility through the
type checker.
"""

from dromedary.tests.test_transport import (
    BackupTransportHandler,
    BadTransportHandler,
    ChrootDecoratorTransportTest,
    FakeNFSDecoratorTests,
    FakeVFATDecoratorTests,
    PathFilteringDecoratorTransportTest,
    ReadonlyDecoratorTransportTest,
    TestChrootServer,
    TestCoalesceOffsets,
    TestConnectedTransport,
    TestHooks,
    TestKind,
    TestLocalTransportMutation,
    TestLocalTransports,
    TestLocalTransportWriteStream,
    TestMemoryServer,
    TestMemoryTransport,
    TestReusedTransports,
    TestSSHConnections,
    TestTransport,
    TestTransportFromPath,
    TestTransportFromUrl,
    TestTransportImplementation,
    TestTransportTrace,
    TestWin32LocalTransport,
)

__all__ = [
    "BackupTransportHandler",
    "BadTransportHandler",
    "ChrootDecoratorTransportTest",
    "FakeNFSDecoratorTests",
    "FakeVFATDecoratorTests",
    "PathFilteringDecoratorTransportTest",
    "ReadonlyDecoratorTransportTest",
    "TestChrootServer",
    "TestCoalesceOffsets",
    "TestConnectedTransport",
    "TestHooks",
    "TestKind",
    "TestLocalTransportMutation",
    "TestLocalTransportWriteStream",
    "TestLocalTransports",
    "TestMemoryServer",
    "TestMemoryTransport",
    "TestReusedTransports",
    "TestSSHConnections",
    "TestTransport",
    "TestTransportFromPath",
    "TestTransportFromUrl",
    "TestTransportImplementation",
    "TestTransportTrace",
    "TestWin32LocalTransport",
]
