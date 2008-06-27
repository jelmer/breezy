# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@samba.org>
 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from bzrlib.tests import TestCase

from bzrlib.plugins.svn.versionedfiles import (SvnTexts, FakeRevisionTexts, 
                                               FakeInventoryTexts)


class BasicSvnTextsTests:
    def test_add_lines(self):
        self.assertRaises(NotImplementedError, 
                self.texts.add_lines, "foo", [], [])

    def test_add_mpdiffs(self):
        self.assertRaises(NotImplementedError, 
                self.texts.add_mpdiffs, [])

    def test_check(self):
        self.assertTrue(self.texts.check())

    def test_insert_record_stream(self):
        self.assertRaises(NotImplementedError, self.texts.insert_record_stream,
                          [])


class SvnTextsTests(TestCase,BasicSvnTextsTests):
    def setUp(self):
        self.texts = SvnTexts()


class FakeRevisionTextsTests(TestCase,BasicSvnTextsTests):
    def setUp(self):
        self.texts = FakeRevisionTexts()


class FakeInventoryTextsTests(TestCase,BasicSvnTextsTests):
    def setUp(self):
        self.texts = FakeInventoryTexts()

