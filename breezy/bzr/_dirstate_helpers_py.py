# Copyright (C) 2007, 2008 Canonical Ltd
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

"""Python implementations of Dirstate Helper functions."""

import binascii
import struct

# We cannot import the dirstate module, because it loads this module
# All we really need is the IN_MEMORY_MODIFIED constant
from .dirstate import DirState, DirstateCorrupt


def pack_stat(st, _b64=binascii.b2a_base64, _pack=struct.Struct('>6L').pack):
    """Convert stat values into a packed representation

    Not all of the fields from the stat included are strictly needed, and by
    just encoding the mtime and mode a slight speed increase could be gained.
    However, using the pyrex version instead is a bigger win.
    """
    # base64 encoding always adds a final newline, so strip it off
    return _b64(_pack(st.st_size & 0xFFFFFFFF, int(st.st_mtime) & 0xFFFFFFFF,
                      int(st.st_ctime) & 0xFFFFFFFF, st.st_dev & 0xFFFFFFFF,
                      st.st_ino & 0xFFFFFFFF, st.st_mode))[:-1]


def bisect_dirblock(dirblocks, dirname, lo=0, hi=None, cache={}):
    """Return the index where to insert dirname into the dirblocks.

    The return value idx is such that all directories blocks in dirblock[:idx]
    have names < dirname, and all blocks in dirblock[idx:] have names >=
    dirname.

    Optional args lo (default 0) and hi (default len(dirblocks)) bound the
    slice of a to be searched.
    """
    if hi is None:
        hi = len(dirblocks)
    try:
        dirname_split = cache[dirname]
    except KeyError:
        dirname_split = dirname.split(b'/')
        cache[dirname] = dirname_split
    while lo < hi:
        mid = (lo + hi) // 2
        # Grab the dirname for the current dirblock
        cur = dirblocks[mid][0]
        try:
            cur_split = cache[cur]
        except KeyError:
            cur_split = cur.split(b'/')
            cache[cur] = cur_split
        if cur_split < dirname_split:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _read_dirblocks(state):
    """Read in the dirblocks for the given DirState object.

    This is tightly bound to the DirState internal representation. It should be
    thought of as a member function, which is only separated out so that we can
    re-write it in pyrex.

    :param state: A DirState object.
    :return: None
    """
    state._state_file.seek(state._end_of_header)
    text = state._state_file.read()
    # TODO: check the crc checksums. crc_measured = zlib.crc32(text)

    fields = text.split(b'\0')
    # Remove the last blank entry
    trailing = fields.pop()
    if trailing != b'':
        raise DirstateCorrupt(state,
                              'trailing garbage: {!r}'.format(trailing))
    # consider turning fields into a tuple.

    # skip the first field which is the trailing null from the header.
    cur = 1
    # Each line now has an extra '\n' field which is not used
    # so we just skip over it
    # entry size:
    #  3 fields for the key
    #  + number of fields per tree_data (5) * tree count
    #  + newline
    num_present_parents = state._num_present_parents()
    tree_count = 1 + num_present_parents
    entry_size = state._fields_per_entry()
    expected_field_count = entry_size * state._num_entries
    field_count = len(fields)
    # this checks our adjustment, and also catches file too short.
    if field_count - cur != expected_field_count:
        raise DirstateCorrupt(state,
                              'field count incorrect %s != %s, entry_size=%s, '
                              'num_entries=%s fields=%r' % (
                                  field_count - cur, expected_field_count, entry_size,
                                  state._num_entries, fields))

    if num_present_parents == 1:
        # Bind external functions to local names
        _int = int
        # We access all fields in order, so we can just iterate over
        # them. Grab an straight iterator over the fields. (We use an
        # iterator because we don't want to do a lot of additions, nor
        # do we want to do a lot of slicing)
        _iter = iter(fields)
        # Get a local reference to the compatible next method
        next = getattr(_iter, '__next__', None)
        if next is None:
            next = _iter.next
        # Move the iterator to the current position
        for x in range(cur):
            next()
        # The two blocks here are deliberate: the root block and the
        # contents-of-root block.
        state._dirblocks = [(b'', []), (b'', [])]
        current_block = state._dirblocks[0][1]
        current_dirname = b''
        append_entry = current_block.append
        for count in range(state._num_entries):
            dirname = next()
            name = next()
            file_id = next()
            if dirname != current_dirname:
                # new block - different dirname
                current_block = []
                current_dirname = dirname
                state._dirblocks.append((current_dirname, current_block))
                append_entry = current_block.append
            # we know current_dirname == dirname, so re-use it to avoid
            # creating new strings
            entry = ((current_dirname, name, file_id),
                     [(  # Current Tree
                         next(),                # minikind
                         next(),                # fingerprint
                         _int(next()),          # size
                         next() == b'y',        # executable
                         next(),                # packed_stat or revision_id
                     ),
                (  # Parent 1
                         next(),                # minikind
                         next(),                # fingerprint
                         _int(next()),          # size
                         next() == b'y',        # executable
                         next(),                # packed_stat or revision_id
                     ),
                ])
            trailing = next()
            if trailing != b'\n':
                raise ValueError("trailing garbage in dirstate: %r" % trailing)
            # append the entry to the current block
            append_entry(entry)
        state._split_root_dirblock_into_contents()
    else:
        fields_to_entry = state._get_fields_to_entry()
        entries = [fields_to_entry(fields[pos:pos + entry_size])
                   for pos in range(cur, field_count, entry_size)]
        state._entries_to_current_state(entries)
    # To convert from format 2  => format 3
    # state._dirblocks = sorted(state._dirblocks,
    #                          key=lambda blk:blk[0].split('/'))
    # To convert from format 3 => format 2
    # state._dirblocks = sorted(state._dirblocks)
    state._dirblock_state = DirState.IN_MEMORY_UNMODIFIED
