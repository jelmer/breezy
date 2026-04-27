# Copyright (C) 2005, 2006, 2009 Canonical Ltd
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

"""Set of flags that enable different debug behaviour.

These are set with eg ``-Dlock`` on the bzr command line or in
~/.config/breezy/breezy.conf debug_flags.

See `bzr help debug-flags` or `breezy/help_topics/en/debug-flags.txt`
for a list of the available options.
"""

debug_flags = set()


def debug_flag_enabled(flag):
    """Return True if the given debug flag is enabled."""
    return flag in debug_flags


def get_debug_flags():
    """Return a copy of the set of enabled debug flags."""
    return set(debug_flags)


def set_debug_flag(flag):
    """Enable a debug flag."""
    debug_flags.add(flag)


def unset_debug_flag(flag):
    """Disable a debug flag."""
    debug_flags.discard(flag)


def clear_debug_flags():
    """Disable all debug flags."""
    debug_flags.clear()


def set_debug_flags(flags):
    """Replace the set of enabled debug flags with the given iterable."""
    clear_debug_flags()
    for f in flags:
        set_debug_flag(f)


def set_debug_flags_from_config():
    """Turn on debug flags based on the global configuration."""
    from breezy import config

    c = config.GlobalStack()
    for f in c.get("debug_flags"):
        set_debug_flag(f)


def set_trace():
    """Pdb using original stdin and stdout.

    When debugging blackbox tests, sys.stdin and sys.stdout are captured for
    test purposes and cannot be used for interactive debugging. This class uses
    the origianl stdin/stdout to allow such use.

    Instead of doing:

       import pdb; pdb.set_trace()

    you can do:

       from breezy import debug; debug.set_trace()
    """
    import pdb
    import sys

    pdb.Pdb(stdin=sys.__stdin__, stdout=sys.__stdout__).set_trace(
        sys._getframe().f_back
    )
