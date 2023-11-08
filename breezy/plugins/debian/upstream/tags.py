#    tags.py -- Providers of upstream source - tag names
#    Copyright (C) 2016-2020 Jelmer Vernooij <jelmer@debian.org>
#
#    This file is part of bzr-builddeb.
#
#    bzr-builddeb is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    bzr-builddeb is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with bzr-builddeb; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from itertools import islice
from typing import Optional

from ....repository import Repository
from ....revision import Revision


from debmutate.versions import mangle_version_for_git


def possible_upstream_tag_names(package: Optional[str], version: str,
                                component: Optional[str] = None,
                                try_hard=True):
    tags = []
    if component is None:
        # compatibility with git-buildpackage
        tags.append("upstream/%s" % version)
        tags.append("upstream-%s" % version)
        manipulated = 'upstream/%s' % mangle_version_for_git(version)
        if manipulated not in tags:
            tags.append(manipulated)
        # compatibility with svn-buildpackage
        tags.append("upstream_%s" % version)

        if try_hard:
            # common upstream names
            tags.append("%s" % version)
            tags.append("v%s" % version)
            if '~' not in str(version) and '+' not in str(version):
                tags.append("release-%s" % version)
                tags.append("v%s-release" % version)
            if package:
                tags.append("{}-{}".format(package, version))
            tags.append("v/%s" % version)
            tags.append("v.%s" % version)
    else:
        tags.append('upstream-{}/{}'.format(version, component))
        tags.append('upstream/{}/{}'.format(
            mangle_version_for_git(version), component))
    return tags


def is_upstream_tag(tag):
    """Return true if tag is an upstream tag.

    :param tag: The string name of the tag.
    :return: True if the tag name is one generated by upstream tag operations.
    """
    return (tag.startswith('upstream-') or tag.startswith('upstream/') or
            tag.startswith('upstream_'))


def upstream_tag_version(tag):
    """Return the upstream version portion of an upstream tag name.

    :param tag: The string name of the tag.
    :return: tuple with version portion of the tag and component name
    """
    assert is_upstream_tag(tag), "Not an upstream tag: %s" % tag
    if tag.startswith('upstream/'):
        tag = tag[len('upstream/'):]
    elif tag.startswith('upstream_'):
        tag = tag[len('upstream_'):]
    elif tag.startswith('upstream-'):
        tag = tag[len('upstream-'):]
        if tag.startswith('debian-'):
            tag = tag[len('debian-'):]
        elif tag.startswith('ubuntu-'):
            tag = tag[len('ubuntu-'):]
    tag = tag.replace('_', '~')
    if '/' not in tag:
        return (None, tag)
    (version, component) = tag.rsplit('/', 1)
    if component == "":
        component = None
    return (component, version)


def _rev_is_upstream_import(
        revision: Revision, package: Optional[str], version: str):
    possible_messages = [
    ]
    if package is not None:
        possible_messages.extend([
            'Import {}_{}'.format(package, version),
            'import {}_{}'.format(package, version),
            'import {}-{}'.format(package.replace('-', '_'), version),
            '{}-{}'.format(package, version),
        ])
    possible_messages.extend([
        'Imported upstream version %s' % version,
        'Import upstream version %s' % version,
        'New upstream version %s' % version,
        'New upstream version v%s' % version,
        ])
    for possible_message in possible_messages:
        if revision.message.lower().startswith(possible_message.lower()):
            return True
    return False


def _rev_is_upstream_merge(
        revision: Revision, package: Optional[str], version: str) -> bool:
    if revision.message.lower().startswith(
            ("Merge tag 'v%s' into debian/" % version).lower()):
        return True
    if package is not None and revision.message.lower().startswith(
            ("Merge tag '{}-{}' into ".format(package, version)).lower()):
        return True
    return False


def upstream_version_tag_start_revids(
        tag_dict, package: Optional[str], version: str):
    """Find Debian tags related to a particular upstream version.

    This can be used by search_for_upstream_version
    """
    candidate_tag_start = [
        'debian/%s-' % mangle_version_for_git(version),
        'debian-%s' % version,
        # Epochs are sometimes replaced by underscores, rather than by %,
        # as DEP-14 suggests.
        'debian/%s-' % mangle_version_for_git(version.replace(':', '_')),
        # Haskell repo style
        "{}_v{}".format(package, version),
        ]
    if package:
        candidate_tag_start.append('debian-{}-{}'.format(package, version))
    for tag_name, revid in tag_dict.items():
        if any([tag_name.startswith(tag_start)
                for tag_start in candidate_tag_start]):
            yield (tag_name, revid)


def search_for_upstream_version(
        repository: Repository, start_revids, package: Optional[str],
        version: str, component: Optional[str] = None,
        md5: Optional[str] = None,
        scan_depth=None):
    """Find possible upstream revisions that don't have appropriate tags."""
    todo = []
    graph = repository.get_graph()
    for revid, parents in islice(
            graph.iter_ancestry(start_revids), scan_depth):
        todo.append(revid)
    for revid, rev in repository.iter_revisions(todo):
        if rev is None:
            continue
        if _rev_is_upstream_import(rev, package, version):
            return revid

    # Try again, but this time search for merge revisions
    for revid, rev in repository.iter_revisions(todo):
        if rev is None:
            continue
        if _rev_is_upstream_merge(rev, package, version):
            return rev.parent_ids[1]
    return None
