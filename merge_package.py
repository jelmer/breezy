#    merge_package.py -- The plugin for bzr
#    Copyright (C) 2009 Canonical Ltd.
#    Copyright (C) 2022 Jelmer Vernooĳ
#
#    :Author: Muharem Hrnjadovic <muharem@ubuntu.com>
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
#

import json
import logging
import os
import tempfile

from debian.changelog import Version

from breezy.errors import (
    BzrError,
    ConflictsInTree,
    NoSuchTag,
    )

from .changelog import debcommit
from .errors import (
    MultipleUpstreamTarballsNotSupported,
)
from .import_dsc import DistributionBranch
from .util import find_changelog


class SharedUpstreamConflictsWithTargetPackaging(BzrError):

    _fmt = ('The upstream branches for the merge source and target have '
            'diverged. Unfortunately, the attempt to fix this problem '
            'resulted in conflicts. Please resolve these, commit and '
            're-run the "%(cmd)s" command to finish. '
            'Alternatively, until you commit you can use "bzr revert" to '
            'restore the state of the unmerged branch.')

    def __init__(self, cmd):
        self.cmd = cmd


def _upstream_version_data(branch, revid):
    """Most recent upstream versions/revision IDs of the merge source/target.

    Please note: both packaging branches must have been read-locked
    beforehand.

    :param branch: The merge branch.
    :param revid: The revision in the branch to consider
    :param tree: Optional tree for the revision
    """
    db = DistributionBranch(branch, branch)
    tree = branch.repository.revision_tree(revid)
    changelog, _ignore = find_changelog(tree, '', False)
    uver = changelog.version.upstream_version
    upstream_revids = db.pristine_upstream_source.version_as_revisions(
        None, uver)
    if list(upstream_revids.keys()) != [None]:
        raise MultipleUpstreamTarballsNotSupported()
    upstream_revid = upstream_revids[None]
    return (Version(uver), upstream_revid)


def fix_ancestry_as_needed(tree, source, source_revid=None):
    r"""Manipulate the merge target's ancestry to avoid upstream conflicts.

    Merging J->I given the following ancestry tree is likely to result in
    upstream merge conflicts:

    debian-upstream                 ,------------------H
                       A-----------B                    \
    ubuntu-upstream     \           \`-------G           \
                         \           \        \           \
    debian-packaging      \ ,---------D--------\-----------J
                           C           \        \
    ubuntu-packaging        `----E------F--------I

    Here there was a new upstream release (G) that Ubuntu packaged (I), and
    then another one that Debian packaged, skipping G, at H and J.

    Now, the way to solve this is to introduce the missing link.

    debian-upstream                 ,------------------H------.
                       A-----------B                    \      \
    ubuntu-upstream     \           \`-------G-----------\------K
                         \           \        \           \
    debian-packaging      \ ,---------D--------\-----------J
                           C           \        \
    ubuntu-packaging        `----E------F--------I

    at K, which isn't a real merge, as we just use the tree from H, but add
    G as a parent and then we merge that in to Ubuntu.

    debian-upstream                 ,------------------H------.
                       A-----------B                    \      \
    ubuntu-upstream     \           \`-------G-----------\------K
                         \           \        \           \      \
    debian-packaging      \ ,---------D--------\-----------J      \
                           C           \        \                  \
    ubuntu-packaging        `----E------F--------I------------------L

    At this point we can merge J->L to merge the Debian and Ubuntu changes.

    :param tree: The `WorkingTree` of the merge target branch.
    :param source: The merge source (packaging) branch.
    """
    upstreams_diverged = False
    t_upstream_reverted = False
    target = tree.branch

    with source.lock_read():
        if source_revid is None:
            source_revid = source.last_revision()
        with tree.lock_write():
            # "Unpack" the upstream versions and revision ids for the merge
            # source and target branch respectively.
            (us_ver, us_revid) = _upstream_version_data(source, source_revid)
            (ut_ver, ut_revid) = _upstream_version_data(
                target, target.last_revision())

            # Did the upstream branches of the merge source/target diverge?
            graph = source.repository.get_graph(target.repository)
            upstreams_diverged = (len(graph.heads([us_revid, ut_revid])) > 1)

            # No, we're done!
            if not upstreams_diverged:
                return (upstreams_diverged, t_upstream_reverted)

            # Instantiate a `DistributionBranch` object for the merge target
            # (packaging) branch.
            db = DistributionBranch(tree.branch, tree.branch)
            with tempfile.TemporaryDirectory(
                    dir=os.path.join(tree.basedir, '..')) as tempdir:
                # Extract the merge target's upstream tree into a temporary
                # directory.
                db.extract_upstream_tree({None: ut_revid}, tempdir)
                tmp_target_utree = db.pristine_upstream_tree

                # Merge upstream branch tips to obtain a shared upstream
                # parent.  This will add revision K (see graph above) to a
                # temporary merge target upstream tree.
                with tmp_target_utree.lock_write():
                    if us_ver > ut_ver:
                        # The source upstream tree is more recent and the
                        # temporary target tree needs to be reshaped to match
                        # it.
                        tmp_target_utree.revert(
                            None, source.repository.revision_tree(us_revid))
                        t_upstream_reverted = True

                    tmp_target_utree.set_parent_ids((ut_revid, us_revid))
                    new_revid = tmp_target_utree.commit(
                        'Prepared upstream tree for merging into target '
                        'branch.')

                    # Repository updates during a held lock are not visible,
                    # hence the call to refresh the data in the /target/ repo.
                    tree.branch.repository.refresh_data()

                    tree.branch.fetch(source, us_revid)
                    tree.branch.fetch(tmp_target_utree.branch, new_revid)

                    # Merge shared upstream parent into the target merge
                    # branch. This creates revison L in the digram above.
                    conflicts = tree.merge_from_branch(tmp_target_utree.branch)
                    if conflicts:
                        cmd = "bzr merge"
                        raise SharedUpstreamConflictsWithTargetPackaging(cmd)
                    else:
                        tree.commit(
                            'Merging shared upstream rev into target branch.')

    return (upstreams_diverged, t_upstream_reverted)


def report_fatal(code, description, *, hint=None):
    if os.environ.get('SVP_API') == '1':
        with open(os.environ['SVP_RESULT'], 'w') as f:
            json.dump({
                'result_code': code,
                'description': description}, f)
    logging.fatal('%s', description)
    if hint:
        logging.info('%s', hint)


def main(argv=None):
    import argparse
    import breezy.bzr  # noqa: F401
    import breezy.git  # noqa: F401
    from breezy.workingtree import WorkingTree
    from breezy.branch import Branch

    from .apt_repo import RemoteApt, LocalApt
    from .directory import source_package_vcs_url
    from .import_dsc import DistributionBranch
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--directory', '-d', type=str, help="Working directory")
    parser.add_argument('--apt-repository', type=str,
                        help='APT Repository to fetch from')
    parser.add_argument('--apt-repository-key', type=str,
                        help='Repository key to use for verification')
    parser.add_argument('--version', type=str,
                        help='Version to use')
    parser.add_argument("--vendor", type=str,
                        help="Name of vendor to merge from")
    args = parser.parse_args()

    logging.basicConfig(format='%(message)s', level=logging.INFO)

    wt, subpath = WorkingTree.open_containing(args.directory)

    vendor = args.vendor

    if args.apt_repository is not None:
        apt = RemoteApt.from_string(
            args.apt_repository, args.apt_repository_key)
    else:
        apt = LocalApt()

    logging.info('Using apt repository %r', apt)

    cl, _ignore = find_changelog(wt, subpath)

    with apt:
        versions = []
        for source in apt.iter_source_by_name(cl.package):
            versions.append((source['Version'], source))

    versions.sort()
    try:
        version, source = versions[-1]
    except IndexError:
        report_fatal(
            'not-present-in-apt',
            f'The APT repository {apt} does not contain {cl.package}')
        return 1
    if args.version:
        version = args.version

    if Version(version) == cl.version:
        report_fatal(
            'tree-version-is-newer',
            f'Local tree already contains remote version {cl.version}')
        return 1

    if Version(version) < cl.version:
        report_fatal(
            'nothing-to-do',
            f'Local tree contains newer version ({version}) '
            f'than apt repo ({cl.version})')
        return 1

    logging.info('Importing version: %s (current: %s)', version, cl.version)

    vcs_type, vcs_url = source_package_vcs_url(source)

    logging.info('Found vcs %s %s', vcs_type, vcs_url)

    source_branch = Branch.open(vcs_url)

    db = DistributionBranch(source_branch, None)

    # Find the appropriate tag
    for tag_name in db.possible_tags(version, vendor=vendor):
        try:
            to_merge = db.branch.tags.lookup_tag(tag_name)
        except NoSuchTag:
            pass
        else:
            break
    else:
        report_fatal(
            'missing-remote-tag',
            'Unable to find tag for version %s in branch %s' % (
                version, db.branch))
        return 1

    logging.info('Merging tag %s', tag_name)
    try:
        wt.merge_from_branch(source_branch, to_revision=to_merge)
    except ConflictsInTree as e:
        report_fatal('merged-conflicted', str(e))
        return 1
    if vendor is not None:
        message = f"Sync with {vendor}."
    else:
        revtree = wt.revision_tree(to_merge)
        mcl, _ignore = find_changelog(revtree)
        message = f"Sync with {mcl.distributions}."
    debcommit(wt, subpath=subpath, message=message)

    if os.environ.get('SVP_API') == '1':
        with open(os.environ['SVP_RESULT'], 'w') as f:
            json.dump({
                'description': f"Merged from {vendor or mcl.distributions}",
                'value': 80,
                'commit-message': message,
                'context': {
                    'vendor': vendor,
                    'package': cl.package,
                    'distributions': mcl.distributions,
                    'version': version,
                    'tag': tag_name,
                },
            }, f)


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
