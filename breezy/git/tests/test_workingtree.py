# Copyright (C) 2010-2018 Jelmer Vernooij <jelmer@jelmer.uk>
# Copyright (C) 2011 Canonical Ltd.
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

"""Tests for Git working trees."""

from __future__ import absolute_import

import os
import stat

from dulwich.index import IndexEntry
from dulwich.objects import (
    S_IFGITLINK,
    Blob,
    Tree,
    ZERO_SHA,
    )

from ... import (
    conflicts as _mod_conflicts,
    )
from ...delta import TreeDelta
from ..mapping import (
    default_mapping,
    GitFileIdMap,
    )
from ..tree import (
    changes_between_git_tree_and_working_copy,
    tree_delta_from_git_changes,
    )
from ..workingtree import (
    FLAG_STAGEMASK,
    )
from ...tests import (
    TestCase,
    TestCaseWithTransport,
    )


class GitWorkingTreeTests(TestCaseWithTransport):

    def setUp(self):
        super(GitWorkingTreeTests, self).setUp()
        self.tree = self.make_branch_and_tree('.', format="git")

    def test_conflict_list(self):
        self.assertIsInstance(
                self.tree.conflicts(),
                _mod_conflicts.ConflictList)

    def test_add_conflict(self):
        self.build_tree(['conflicted'])
        self.tree.add(['conflicted'])
        with self.tree.lock_tree_write():
            self.tree.index[b'conflicted'] = self.tree.index[b'conflicted'][:9] + (FLAG_STAGEMASK, )
            self.tree._index_dirty = True
        conflicts = self.tree.conflicts()
        self.assertEqual(1, len(conflicts))

    def test_revert_empty(self):
        self.build_tree(['a'])
        self.tree.add(['a'])
        self.assertTrue(self.tree.is_versioned('a'))
        self.tree.revert(['a'])
        self.assertFalse(self.tree.is_versioned('a'))

    def test_is_ignored_directory(self):
        self.assertFalse(self.tree.is_ignored('a'))
        self.build_tree(['a/'])
        self.assertFalse(self.tree.is_ignored('a'))
        self.build_tree_contents([('.gitignore', 'a\n')])
        self.tree._ignoremanager = None
        self.assertTrue(self.tree.is_ignored('a'))
        self.build_tree_contents([('.gitignore', 'a/\n')])
        self.tree._ignoremanager = None
        self.assertTrue(self.tree.is_ignored('a'))


class TreeDeltaFromGitChangesTests(TestCase):

    def test_empty(self):
        delta = TreeDelta()
        changes = []
        self.assertEqual(
            delta,
            tree_delta_from_git_changes(changes, default_mapping,
                (GitFileIdMap({}, default_mapping),
                 GitFileIdMap({}, default_mapping))))

    def test_missing(self):
        delta = TreeDelta()
        delta.removed.append(('a', b'a-id', 'file'))
        changes = [((b'a', b'a'), (stat.S_IFREG | 0o755, 0), (b'a' * 40, b'a' * 40))]
        self.assertEqual(
            delta,
            tree_delta_from_git_changes(changes, default_mapping,
                (GitFileIdMap({u'a': b'a-id'}, default_mapping),
                 GitFileIdMap({u'a': b'a-id'}, default_mapping))))


class ChangesBetweenGitTreeAndWorkingCopyTests(TestCaseWithTransport):

    def setUp(self):
        super(ChangesBetweenGitTreeAndWorkingCopyTests, self).setUp()
        self.wt = self.make_branch_and_tree('.', format='git')
        self.store = self.wt.branch.repository._git.object_store

    def expectDelta(self, expected_changes,
                    expected_extras=None, want_unversioned=False,
                    tree_id=None):
        if tree_id is None:
            try:
                tree_id = self.store[self.wt.branch.repository._git.head()].tree
            except KeyError:
                tree_id = None
        with self.wt.lock_read():
            changes, extras = changes_between_git_tree_and_working_copy(
                self.store, tree_id, self.wt, want_unversioned=want_unversioned)
            self.assertEqual(expected_changes, list(changes))
        if expected_extras is None:
            expected_extras = set()
        self.assertEqual(set(expected_extras), set(extras))

    def test_empty(self):
        self.expectDelta(
            [((None, b''), (None, stat.S_IFDIR), (None, Tree().id))])

    def test_added_file(self):
        self.build_tree(['a'])
        self.wt.add(['a'])
        a = Blob.from_string(b'contents of a\n')
        t = Tree()
        t.add(b"a", stat.S_IFREG | 0o644, a.id)
        self.expectDelta(
            [((None, b''), (None, stat.S_IFDIR), (None, t.id)),
             ((None, b'a'), (None, stat.S_IFREG | 0o644), (None, a.id))])

    def test_added_unknown_file(self):
        self.build_tree(['a'])
        t = Tree()
        self.expectDelta(
            [((None, b''), (None, stat.S_IFDIR), (None, t.id))])
        a = Blob.from_string(b'contents of a\n')
        t = Tree()
        t.add(b"a", stat.S_IFREG | 0o644, a.id)
        self.expectDelta(
            [((None, b''), (None, stat.S_IFDIR), (None, t.id)),
             ((None, b'a'), (None, stat.S_IFREG | 0o644), (None, a.id))],
            [b'a'],
            want_unversioned=True)

    def test_missing_added_file(self):
        self.build_tree(['a'])
        self.wt.add(['a'])
        os.unlink('a')
        a = Blob.from_string(b'contents of a\n')
        t = Tree()
        t.add(b"a", 0, ZERO_SHA)
        self.expectDelta(
            [((None, b''), (None, stat.S_IFDIR), (None, t.id)),
             ((None, b'a'), (None, 0), (None, ZERO_SHA))],
            [])

    def test_missing_versioned_file(self):
        self.build_tree(['a'])
        self.wt.add(['a'])
        self.wt.commit('')
        os.unlink('a')
        a = Blob.from_string(b'contents of a\n')
        oldt = Tree()
        oldt.add(b"a", stat.S_IFREG | 0o644, a.id)
        newt = Tree()
        newt.add(b"a", 0, ZERO_SHA)
        self.expectDelta(
                [((b'', b''), (stat.S_IFDIR, stat.S_IFDIR), (oldt.id, newt.id)),
                 ((b'a', b'a'), (stat.S_IFREG|0o644, 0), (a.id, ZERO_SHA))])

    def test_versioned_replace_by_dir(self):
        self.build_tree(['a'])
        self.wt.add(['a'])
        self.wt.commit('')
        os.unlink('a')
        os.mkdir('a')
        olda = Blob.from_string(b'contents of a\n')
        oldt = Tree()
        oldt.add(b"a", stat.S_IFREG | 0o644, olda.id)
        newt = Tree()
        newa = Tree()
        newt.add(b"a", stat.S_IFDIR, newa.id)
        self.expectDelta([
            ((b'', b''),
            (stat.S_IFDIR, stat.S_IFDIR),
            (oldt.id, newt.id)),
            ((b'a', b'a'), (stat.S_IFREG | 0o644, stat.S_IFDIR), (olda.id, newa.id))
            ], want_unversioned=False)
        self.expectDelta([
            ((b'', b''),
            (stat.S_IFDIR, stat.S_IFDIR),
            (oldt.id, newt.id)),
            ((b'a', b'a'), (stat.S_IFREG | 0o644, stat.S_IFDIR), (olda.id, newa.id))
            ], want_unversioned=True)

    def test_extra(self):
        self.build_tree(['a'])
        newa = Blob.from_string(b'contents of a\n')
        newt = Tree()
        newt.add(b"a", stat.S_IFREG | 0o644, newa.id)
        self.expectDelta([
            ((None, b''),
            (None, stat.S_IFDIR),
            (None, newt.id)),
            ((None, b'a'), (None, stat.S_IFREG | 0o644), (None, newa.id))
            ], [b'a'], want_unversioned=True)

    def test_submodule(self):
        self.build_tree(['a/'])
        a = Blob.from_string(b'irrelevant\n')
        with self.wt.lock_tree_write():
            (index, index_path) = self.wt._lookup_index(b'a')
            index[b'a'] = IndexEntry(
                    0, 0, 0, 0, S_IFGITLINK, 0, 0, 0, a.id, 0)
            self.wt._index_dirty = True
        t = Tree()
        t.add(b"a", S_IFGITLINK , a.id)
        self.store.add_object(t)
        self.expectDelta([], tree_id=t.id)
