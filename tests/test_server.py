# Copyright (C) 2011 Jelmer Vernooij <jelmer@samba.org>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Test for git server."""

from dulwich.client import TCPGitClient
from dulwich.repo import Repo
import threading

from bzrlib import trace
from bzrlib.transport import transport_server_registry
from bzrlib.tests import (
    TestCase,
    TestCaseWithTransport,
    )

from bzrlib.plugins.git.server import (
    BzrBackend,
    TCPGitServer,
    )

class TestPresent(TestCase):

    def test_present(self):
        # Just test that the server is registered.
        transport_server_registry.get('git')


class GitServerTestCase(TestCaseWithTransport):

    def start_server(self, t):
        backend = BzrBackend(t)
        server = TCPGitServer(backend, 'localhost', port=0)
        self.addCleanup(server.shutdown)
        thread = threading.Thread(target=server.serve).start()
        self._server = server
        _, port = self._server.socket.getsockname()
        return port


class TestPlainFetch(GitServerTestCase):

    def test_fetch_simple(self):
        wt = self.make_branch_and_tree('t')
        self.build_tree(['t/foo'])
        wt.add('foo')
        wt.commit(message="some data")
        t = self.get_transport('t')
        port = self.start_server(t)
        c = TCPGitClient('localhost', port=port)
        gitrepo = Repo.init('gitrepo', mkdir=True)
        refs = c.fetch('/', gitrepo)
        self.assertEquals(refs.keys(), ["HEAD", "refs/heads/master"])