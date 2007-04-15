# Copyright (C) 2006-2007 Jelmer Vernooij <jelmer@samba.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from bzrlib.bzrdir import BzrDir
from bzrlib.errors import NoRepositoryPresent
from bzrlib.tests import TestCase

from convert import SvnConverter
from checkout import SvnWorkingTreeFormat, SvnWorkingTreeDirFormat
from tests import TestCaseWithSubversionRepository

class TestWorkingTreeFormat(TestCase):
    def setUp(self):
        super(TestWorkingTreeFormat, self).setUp()
        self.format = SvnWorkingTreeFormat()

    def test_get_format_desc(self):
        self.assertEqual("Subversion Working Copy", 
                         self.format.get_format_description())

    def test_initialize(self):
        self.assertRaises(NotImplementedError, self.format.initialize, None)

    def test_open(self):
        self.assertRaises(NotImplementedError, self.format.open, None)

class TestCheckoutFormat(TestCase):
    def setUp(self):
        super(TestCheckoutFormat, self).setUp()
        self.format = SvnWorkingTreeDirFormat()

    def test_get_converter(self):
        self.assertIsInstance(self.format.get_converter(), SvnConverter)


class TestCheckout(TestCaseWithSubversionRepository):
    def test_not_for_writing(self):
        self.make_client("d", "dc")
        x = self.create_branch_convenience("dc/foo")
        self.assertFalse(hasattr(x.repository, "uuid"))

    def test_open_repository(self):
        self.make_client("d", "dc")
        x = self.open_checkout_bzrdir("dc")
        self.assertRaises(NoRepositoryPresent, x.open_repository)

    def test_find_repository(self):
        self.make_client("d", "dc")
        x = self.open_checkout_bzrdir("dc")
        self.assertTrue(hasattr(x.find_repository(), "uuid"))

