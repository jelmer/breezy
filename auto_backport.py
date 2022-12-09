#!/usr/bin/python3
# Copyright (C) 2020 Jelmer Vernooij <jelmer@jelmer.uk>
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

from distro_info import DebianDistroInfo

import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Optional

from breezy.plugins.debian.cmds import _build_helper
from breezy.plugins.debian.changelog import (
    debcommit,
    )
from breezy.plugins.debian.info import (
    versions_dict,
    )
from breezy.plugins.debian.util import (
    dput_changes,
)
from breezy.workspace import check_clean_tree
from breezy.workingtree import WorkingTree

from debian.changelog import format_date, get_maintainer
from debmutate.changelog import ChangelogEditor, changeblock_add_line
from debmutate.reformatting import GeneratedFile


DEFAULT_BUILDER = "sbuild --no-clean-source"


class MissingChangelogFile(Exception):
    """The debian/changelog file is missing"""


class ChangelogGeneratedFile(Exception):
    """The changelog file is generated."""

    def __init__(self, path, template_path, template_type):
        self.path = path
        self.template_path = template_path
        self.template_type = template_type


def debsign(path, keyid=None):
    (bd, changes_file) = os.path.split(path)
    args = ["debsign"]
    if keyid:
        args.append("-k%s" % keyid)
    args.append(changes_file)
    subprocess.check_call(args, cwd=bd)


# See https://backports.debian.org/Contribute/


class BackportResult(object):
    def __init__(self, source, target_release, version, since_version):
        self.source = source
        self.target_release = target_release
        self.version = version
        self.since_version = since_version


def backport_suffix(release):
    distro_info = DebianDistroInfo()
    version = distro_info.version(release)
    return "bpo%s" % version


def backport_distribution(release):
    distro_info = DebianDistroInfo()
    if distro_info.codename("stable") == release:
        return "%s-backports" % release
    elif distro_info.codename("oldstable") == release:
        return "%s-backports-sloppy" % release
    else:
        raise Exception("unable to determine target suite for %s" % release)


def create_bpo_version(orig_version, bpo_suffix):
    m = re.fullmatch(r"(.*)\~" + bpo_suffix + r"\+([0-9]+)", str(orig_version))
    if m:
        base = m.group(1)
        buildno = int(m.group(2)) + 1
    else:
        base = str(orig_version)
        buildno = 1
    return "%s~%s+%d" % (base, bpo_suffix, buildno)


def backport_package(local_tree, subpath, target_release, author=None):
    changes = []
    # TODO(jelmer): Iterate Build-Depends and verify that depends are
    # satisfied by target_distribution
    # TODO(jelmer): Update Vcs-Git/Vcs-Browser header?
    target_distribution = backport_distribution(target_release)
    version_suffix = backport_suffix(target_release)
    logging.info(
        "Using target distribution %s, version suffix %s",
        target_distribution,
        version_suffix,
    )
    clp = local_tree.abspath(os.path.join(subpath, "debian/changelog"))

    if author is None:
        author = "%s <%s>" % get_maintainer()

    try:
        with ChangelogEditor(clp) as cl:
            # TODO(jelmer): If there was an existing backport, use that version
            since_version = cl[0].version
            cl.new_block(
                package=cl[0].package,
                distributions=target_distribution,
                urgency="low",
                author=author,
                date=format_date(),
                version=create_bpo_version(since_version, version_suffix),
                changes=[''],
            )
            changeblock_add_line(
                cl[0],
                ["Backport to %s." % target_release] +
                [" +" + line for line in changes],
            )
    except FileNotFoundError:
        raise MissingChangelogFile()
    except GeneratedFile as e:
        raise ChangelogGeneratedFile(e.path, e.template_path, e.template_type)

    debcommit(local_tree, subpath=subpath)

    return BackportResult(
        source=cl[0].package,
        version=cl[0].version,
        target_release=target_release,
        since_version=since_version)


def report_fatal(
        code: str, description: str, upstream_version: Optional[str] = None,
        conflicts=None, hint: Optional[str] = None):
    if os.environ.get('SVP_API') == '1':
        context = {}
        if upstream_version is not None:
            context['upstream_version'] = str(upstream_version)
        if conflicts is not None:
            context['conflicts'] = conflicts
        with open(os.environ['SVP_RESULT'], 'w') as f:
            json.dump({
                'result_code': code,
                'hint': hint,
                'description': description,
                'versions': versions_dict(),
                'context': context}, f)
    logging.fatal('%s', description)
    if hint:
        logging.info('%s', hint)


def main(argv=None):
    import argparse

    import breezy.bzr  # noqa: F401
    import breezy.git  # noqa: F401

    parser = argparse.ArgumentParser()
    distro_info = DebianDistroInfo()
    parser.add_argument(
        "--target-release",
        type=str,
        help="Target release",
        default=distro_info.stable(),
    )
    parser.add_argument("--dry-run", action="store_true", help="Do a dry run.")
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--version', type=str, help='Version to backport')
    parser.add_argument(
        "--builder",
        type=str,
        help="Build command",
        default=(
            DEFAULT_BUILDER + " --source --source-only-changes "
            "--debbuildopt=-v${LAST_VERSION}"
        ),
    )

    args = parser.parse_args(argv)

    committer = os.environ.get('COMMITTER')

    local_tree, subpath = WorkingTree.open_containing('.')

    check_clean_tree(local_tree, subpath=subpath)

    if args.version:
        from .import_dsc import DistributionBranch
        db = DistributionBranch(local_tree.branch, None)
        revid = db.revid_of_version(args.version)
        local_tree.pull(local_tree.branch, stop_revision=revid, overwrite=True)

    try:
        with local_tree.lock_write():
            result = backport_package(
                local_tree, subpath, args.target_release, author=committer)
    except MissingChangelogFile:
        report_fatal("missing-changelog", "Missing changelog file")
        return 1
    except ChangelogGeneratedFile as e:
        report_fatal(
            "changelog-generated-file",
            "changelog file can't be updated because it is generated. "
            "(template type: %s, path: %s)" % (
                e.template_type, e.template_path))
        return 1

    if args.build:
        with tempfile.TemporaryDirectory() as td:
            builder = args.builder.replace(
                "${LAST_VERSION}", str(result.since_version))
            target_changes = _build_helper(
                local_tree, subpath, local_tree.branch, td, builder=builder
            )
            debsign(target_changes['source'])

            if not args.dry_run:
                dput_changes(target_changes['source'])

    if os.environ.get('SVP_API') == '1':
        with open(os.environ['SVP_RESULT'], 'w') as f:
            json.dump({
                'description': 'Backport %s to %s' % (
                    result.source, result.target_release),
                'versions': versions_dict(),
                'context': {
                    'source': result.source,
                    'version': str(result.version),
                    'since_version': str(result.since_version),
                    'target_release': result.target_release,
                }}, f)
    logging.info('Backported %s to %s', result.source, result.target_release)


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))
