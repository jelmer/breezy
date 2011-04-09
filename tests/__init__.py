# Copyright (C) 2006, 2007 Canonical Ltd
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

"""The basic test suite for bzr-git."""

from cStringIO import StringIO

import time

from bzrlib import (
    errors as bzr_errors,
    tests,
    )
from bzrlib.plugins.git import (
    import_dulwich,
    )
from fastimport import (
    commands,
    )

TestCase = tests.TestCase
TestCaseInTempDir = tests.TestCaseInTempDir
TestCaseWithTransport = tests.TestCaseWithTransport
TestCaseWithMemoryTransport = tests.TestCaseWithMemoryTransport

class _DulwichFeature(tests.Feature):

    def _probe(self):
        try:
            import_dulwich()
        except bzr_errors.DependencyNotPresent:
            return False
        return True

    def feature_name(self):
        return 'dulwich'


DulwichFeature = _DulwichFeature()


class GitBranchBuilder(object):

    def __init__(self, stream=None):
        self.commit_info = []
        self.orig_stream = stream
        if stream is None:
            self.stream = StringIO()
        else:
            self.stream = stream
        self._counter = 0
        self._branch = 'refs/heads/master'

    def set_branch(self, branch):
        """Set the branch we are committing."""
        self._branch = branch

    def _write(self, text):
        self.stream.write(text)

    def _writelines(self, lines):
        self.stream.writelines(lines)

    def _create_blob(self, content):
        self._counter += 1
        blob = commands.BlobCommand(str(self._counter), content)
        self._write(str(blob)+"\n")
        return self._counter

    def set_symlink(self, path, content):
        """Create or update symlink at a given path."""
        mark = self._create_blob(content)
        mode = '120000'
        self.commit_info.append('M %s :%d %s\n'
                % (mode, mark, self._encode_path(path)))

    def set_file(self, path, content, executable):
        """Create or update content at a given path."""
        mark = self._create_blob(content)
        if executable:
            mode = '100755'
        else:
            mode = '100644'
        self.commit_info.append('M %s :%d %s\n'
                                % (mode, mark, self._encode_path(path)))

    def set_link(self, path, link_target):
        """Create or update a link at a given path."""
        mark = self._create_blob(link_target)
        self.commit_info.append('M 120000 :%d %s\n'
                                % (mark, self._encode_path(path)))

    def delete_entry(self, path):
        """This will delete files or symlinks at the given location."""
        self.commit_info.append('D %s\n' % (self._encode_path(path),))

    @staticmethod
    def _encode_path(path):
        if '\n' in path or path[0] == '"':
            path = path.replace('\\', '\\\\')
            path = path.replace('\n', '\\n')
            path = path.replace('"', '\\"')
            path = '"' + path + '"'
        return path.encode('utf-8')

    # TODO: Author
    # TODO: Author timestamp+timezone
    def commit(self, committer, message, timestamp=None,
               timezone='+0000', author=None,
               merge=None, base=None):
        """Commit the new content.

        :param committer: The name and address for the committer
        :param message: The commit message
        :param timestamp: The timestamp for the commit
        :param timezone: The timezone of the commit, such as '+0000' or '-1000'
        :param author: The name and address of the author (if different from
            committer)
        :param merge: A list of marks if this should merge in another commit
        :param base: An id for the base revision (primary parent) if that
            is not the last commit.
        :return: A mark which can be used in the future to reference this
            commit.
        """
        self._counter += 1
        mark = str(self._counter)
        if timestamp is None:
            timestamp = int(time.time())
        self._write('commit %s\n' % (self._branch,))
        self._write('mark :%s\n' % (mark,))
        self._write('committer %s %s %s\n'
                    % (committer, timestamp, timezone))
        message = message.encode('UTF-8')
        self._write('data %d\n' % (len(message),))
        self._write(message)
        self._write('\n')
        if base is not None:
            self._write('from :%s\n' % (base,))
        if merge is not None:
            for m in merge:
                self._write('merge :%s\n' % (m,))
        self._writelines(self.commit_info)
        self._write('\n')
        self.commit_info = []
        return mark

    def reset(self, ref=None, mark=None):
        """Create or recreate the named branch.

        :param ref: branch name, defaults to the current branch.
        :param mark: commit the branch will point to.
        """
        if ref is None:
            ref = self._branch
        self._write('reset %s\n' % (ref,))
        if mark is not None:
            self._write('from :%s\n' % mark)
        self._write('\n')

    def finish(self):
        """We are finished building, close the stream, get the id mapping"""
        self.stream.seek(0)
        if self.orig_stream is None:
            from dulwich.repo import Repo
            r = Repo(".")
            from dulwich.fastexport import GitImportProcessor
            importer = GitImportProcessor(r)
            return importer.import_stream(self.stream)


def test_suite():
    loader = tests.TestUtil.TestLoader()

    suite = tests.TestUtil.TestSuite()

    testmod_names = [
        'test_blackbox',
        'test_builder',
        'test_branch',
        'test_cache',
        'test_dir',
        'test_fetch',
        'test_mapping',
        'test_object_store',
        'test_push',
        'test_remote',
        'test_repository',
        'test_refs',
        'test_revspec',
        'test_roundtrip',
        'test_transportgit',
        'test_versionedfiles',
        ]
    testmod_names = ['%s.%s' % (__name__, t) for t in testmod_names]
    suite.addTests(loader.loadTestsFromModuleNames(testmod_names))

    return suite