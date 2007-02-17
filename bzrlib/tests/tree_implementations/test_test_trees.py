# Copyright (C) 2006 Canonical Ltd
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

"""Tests for the test trees used by the tree_implementations tests."""

from bzrlib.tests.tree_implementations import TestCaseWithTree


class TestTreeShapes(TestCaseWithTree):

    def test_empty_tree_no_parents(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_no_parents_no_content(tree)
        self.assertEqual([], tree.get_parent_ids())
        self.assertEqual([], tree.conflicts())
        self.assertEqual([], list(tree.unknowns()))
        self.assertEqual(['empty-root-id'], list(iter(tree)))
        self.assertEqual(
            [('', 'empty-root-id')],
            [(path, node.file_id) for path, node in tree.iter_entries_by_dir()])

    def test_abc_tree_no_parents(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_no_parents_abc_content(tree)
        self.assertEqual([], tree.get_parent_ids())
        self.assertEqual([], tree.conflicts())
        self.assertEqual([], list(tree.unknowns()))
        # __iter__ has no strongly defined order
        self.assertEqual(
            set(['root-id', 'a-id', 'b-id', 'c-id']),
            set(iter(tree)))
        self.assertEqual(
            [('', 'root-id'), ('a', 'a-id'), ('b', 'b-id'), ('b/c', 'c-id')],
            [(path, node.file_id) for path, node in tree.iter_entries_by_dir()])
        self.assertEqualDiff('contents of a\n', tree.get_file_text('a-id'))
        self.assertFalse(tree.is_executable('c-id'))

    def test_abc_tree_content_2_no_parents(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_no_parents_abc_content_2(tree)
        self.assertEqual([], tree.get_parent_ids())
        self.assertEqual([], tree.conflicts())
        self.assertEqual([], list(tree.unknowns()))
        # __iter__ has no strongly defined order
        self.assertEqual(
            set(['root-id', 'a-id', 'b-id', 'c-id']),
            set(iter(tree)))
        self.assertEqual(
            [('', 'root-id'), ('a', 'a-id'), ('b', 'b-id'), ('b/c', 'c-id')],
            [(path, node.file_id) for path, node in tree.iter_entries_by_dir()])
        self.assertEqualDiff('foobar\n', tree.get_file_text('a-id'))
        self.assertFalse(tree.is_executable('c-id'))
        
    def test_abc_tree_content_3_no_parents(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_no_parents_abc_content_3(tree)
        self.assertEqual([], tree.get_parent_ids())
        self.assertEqual([], tree.conflicts())
        self.assertEqual([], list(tree.unknowns()))
        # __iter__ has no strongly defined order
        self.assertEqual(
            set(['root-id', 'a-id', 'b-id', 'c-id']),
            set(iter(tree)))
        self.assertEqual(
            [('', 'root-id'), ('a', 'a-id'), ('b', 'b-id'), ('b/c', 'c-id')],
            [(path, node.file_id) for path, node in tree.iter_entries_by_dir()])
        self.assertEqualDiff('contents of a\n', tree.get_file_text('a-id'))
        self.assertTrue(tree.is_executable('c-id'))
        
    def test_abc_tree_content_4_no_parents(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_no_parents_abc_content_4(tree)
        self.assertEqual([], tree.get_parent_ids())
        self.assertEqual([], tree.conflicts())
        self.assertEqual([], list(tree.unknowns()))
        # __iter__ has no strongly defined order
        self.assertEqual(
            set(['root-id', 'a-id', 'b-id', 'c-id']),
            set(iter(tree)))
        self.assertEqual(
            [('', 'root-id'), ('b', 'b-id'), ('d', 'a-id'), ('b/c', 'c-id')],
            [(path, node.file_id) for path, node in tree.iter_entries_by_dir()])
        self.assertEqualDiff('contents of a\n', tree.get_file_text('a-id'))
        self.assertFalse(tree.is_executable('c-id'))
        
    def test_abc_tree_content_5_no_parents(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_no_parents_abc_content_5(tree)
        self.assertEqual([], tree.get_parent_ids())
        self.assertEqual([], tree.conflicts())
        self.assertEqual([], list(tree.unknowns()))
        # __iter__ has no strongly defined order
        self.assertEqual(
            set(['root-id', 'a-id', 'b-id', 'c-id']),
            set(iter(tree)))
        self.assertEqual(
            [('', 'root-id'), ('b', 'b-id'), ('d', 'a-id'), ('b/c', 'c-id')],
            [(path, node.file_id) for path, node in tree.iter_entries_by_dir()])
        self.assertEqualDiff('bar\n', tree.get_file_text('a-id'))
        self.assertFalse(tree.is_executable('c-id'))
        
    def test_abc_tree_content_6_no_parents(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_no_parents_abc_content_6(tree)
        self.assertEqual([], tree.get_parent_ids())
        self.assertEqual([], tree.conflicts())
        self.assertEqual([], list(tree.unknowns()))
        # __iter__ has no strongly defined order
        self.assertEqual(
            set(['root-id', 'a-id', 'b-id', 'c-id']),
            set(iter(tree)))
        self.assertEqual(
            [('', 'root-id'), ('a', 'a-id'), ('b', 'b-id'), ('e', 'c-id')],
            [(path, node.file_id) for path, node in tree.iter_entries_by_dir()])
        self.assertEqualDiff('contents of a\n', tree.get_file_text('a-id'))
        self.assertTrue(tree.is_executable('c-id'))

    def test_tree_with_utf8(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_with_utf8(tree)

        revision_id = u'r\xe9v-1'.encode('utf8')
        path_and_ids = [(u'', u'TREE_ROOT'),
                        (u'b\xe5r', u'b\xe5-r-id'),
                        (u'f\xf6', u'f\xf6-id'),
                        (u'b\xe5r/b\xe1z', u'b\xe1z-id'),
                       ]
        tree.lock_read()
        try:
            path_entries = list(tree.iter_entries_by_dir())
        finally:
            tree.unlock()

        for expected, actual in zip(path_and_ids, path_entries):
            self.assertEqual(expected[0], actual[0]) # Paths should match
            self.assertEqual(expected[1], actual[1].file_id)
            if isinstance(actual[1].file_id, str):
                # file_ids might be plain strings, but only if they are ascii
                actual[1].file_id.decode('ascii')
            else:
                self.assertIsInstance(actual[1].file_id, unicode)
            # WorkingTree's return None for the last modified revision
            if actual[1].revision is not None:
                self.assertIsInstance(actual[1].revision, str)
                if expected[0] == '':
                    # Some trees will preserve the revision id of the tree root,
                    # but not all will
                    continue
                self.assertEqual(revision_id, actual[1].revision)
        self.assertEqual(len(path_and_ids), len(path_entries))
        get_revision_id = getattr(tree, 'get_revision_id', None)
        if get_revision_id is not None:
            self.assertIsInstance(get_revision_id(), str)
        last_revision = getattr(tree, 'last_revision', None)
        if last_revision is not None:
            self.assertIsInstance(last_revision(), str)

    def test_tree_with_merged_utf8(self):
        tree = self.make_branch_and_tree('.')
        tree = self.get_tree_with_merged_utf8(tree)

        revision_id_1 = u'r\xe9v-1'.encode('utf8')
        revision_id_2 = u'r\xe9v-2'.encode('utf8')
        path_and_ids = [(u'', u'TREE_ROOT', None),
                        (u'b\xe5r', u'b\xe5-r-id', revision_id_1),
                        (u'f\xf6', u'f\xf6-id', revision_id_1),
                        (u'b\xe5r/b\xe1z', u'b\xe1z-id', revision_id_1),
                        (u'b\xe5r/z\xf7z', u'z\xf7z-id', revision_id_2),
                       ]
        tree.lock_read()
        try:
            path_entries = list(tree.iter_entries_by_dir())
        finally:
            tree.unlock()

        for expected, actual in zip(path_and_ids, path_entries):
            self.assertEqual(expected[0], actual[0]) # Paths should match
            self.assertEqual(expected[1], actual[1].file_id)
            if isinstance(actual[1].file_id, str):
                # file_ids might be plain strings, but only if they are ascii
                actual[1].file_id.decode('ascii')
            else:
                self.assertIsInstance(actual[1].file_id, unicode)
            # WorkingTree's return None for the last modified revision
            if actual[1].revision is not None:
                self.assertIsInstance(actual[1].revision, str)
                if expected[0] == '':
                    # Some trees will preserve the revision id of the tree root,
                    # but not all will
                    continue
                self.assertEqual(expected[2], actual[1].revision)
        self.assertEqual(len(path_and_ids), len(path_entries))
        get_revision_id = getattr(tree, 'get_revision_id', None)
        if get_revision_id is not None:
            self.assertIsInstance(get_revision_id(), str)
        last_revision = getattr(tree, 'last_revision', None)
        if last_revision is not None:
            self.assertIsInstance(last_revision(), str)
