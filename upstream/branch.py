#    upstream/branch.py -- Upstream branch source provider
#    Copyright (C) 2010-2011 Canonical Ltd.
#    Copyright (C) 2009 Jelmer Vernooij
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

from bzrlib.errors import InvalidRevisionId
from bzrlib.revisionspec import RevisionSpec
from bzrlib.trace import note

from bzrlib.plugins.builddeb.errors import PackageVersionNotPresent
from bzrlib.plugins.builddeb.upstream import UpstreamSource
from bzrlib.plugins.builddeb.util import (
    export,
    get_snapshot_revision,
    )


def upstream_tag_to_version(tag_name, package=None):
    """Take a tag name and return the upstream version, or None."""
    if (package is not None and (
          tag_name.startswith("%s-" % package) or
          tag_name.startswith("%s_" % package))):
        return tag_name[len(package)+1:]
    if tag_name.startswith("release-"):
        return tag_name[len("release-"):]
    if tag_name[0] == "v" and tag_name[1].isdigit():
        return tag_name[1:]
    if all([c.isdigit() or c in (".", "~") for c in tag_name]):
        return tag_name
    return None


def _upstream_branch_version(revhistory, reverse_tag_dict, package, 
                            previous_version, add_rev):
    """Determine the version string of an upstream branch.

    The upstream version is determined from the most recent tag
    in the upstream branch. If that tag does not point at the last revision, 
    the revision number is added to it (<version>+bzr<revno>).

    If there are no tags set on the upstream branch, the previous Debian 
    version is used and combined with the bzr revision number 
    (usually <version>+bzr<revno>).

    :param revhistory: Branch revision history.
    :param reverse_tag_dict: Reverse tag dictionary (revid -> list of tags)
    :param package: Name of package.
    :param previous_version: Previous upstream version in debian changelog.
    :param add_rev: Function that can add a revision suffix to a version string.
    :return: Name of the upstream revision.
    """
    if revhistory == []:
        # No new version to merge
        return previous_version
    for r in reversed(revhistory):
        if r in reverse_tag_dict:
            # If there is a newer version tagged in branch,
            # convert to upstream version
            # return <upstream_version>+bzr<revno>
            for tag in reverse_tag_dict[r]:
                upstream_version = upstream_tag_to_version(tag,
                                                   package=package)
                if upstream_version is not None:
                    if r != revhistory[-1]:
                        upstream_version = add_rev(
                          upstream_version, revhistory[-1])
                    return upstream_version
    return add_rev(previous_version, revhistory[-1])


def extract_svn_revno(rev):
    """Extract the Subversion number of a revision from a revision.

    :param rev: Revision object
    :return: Revision number, None if this was not a Subversion revision or
         if the revision number could not be determined (bzr-svn not available).
    """
    try:
        from bzrlib.plugins.svn import extract_svn_foreign_revid
    except ImportError:
        # No svn support
        return None
    else:
        try:
            (svn_uuid, branch_path, svn_revno) = extract_svn_foreign_revid(rev)
        except InvalidRevisionId:
            return None
        else:
            return svn_revno


def upstream_version_add_revision(upstream_branch, version_string, revid):
    """Update the revision in a upstream version string.

    :param branch: Branch in which the revision can be found
    :param version_string: Original version string
    :param revid: Revision id of the revision
    """
    revno = upstream_branch.revision_id_to_revno(revid)

    if "+bzr" in version_string:
        return "%s+bzr%d" % (version_string[:version_string.rfind("+bzr")], revno)

    if "~bzr" in version_string:
        return "%s~bzr%d" % (version_string[:version_string.rfind("~bzr")], revno)

    rev = upstream_branch.repository.get_revision(revid)
    svn_revno = extract_svn_revno(rev)

    # FIXME: Raise error if +svn/~svn is present and svn_revno is not set?
    if "+svn" in version_string and svn_revno:
        return "%s+svn%d" % (version_string[:version_string.rfind("+svn")], svn_revno)
    if "~svn" in version_string and svn_revno:
        return "%s~svn%d" % (version_string[:version_string.rfind("~svn")], svn_revno)

    if svn_revno:
        return "%s+svn%d" % (version_string, svn_revno)
    else:
        return "%s+bzr%d" % (version_string, revno)


def upstream_branch_version(upstream_branch, upstream_revision, package,
        previous_version):
    """Determine the version string for a revision in an upstream branch.

    :param upstream_branch: The upstream branch object
    :param upstream_revision: The revision id of the upstream revision
    :param package: The name of the package
    :param previous_version: The previous upstream version string
    :return: Upstream version string for `upstream_revision`.
    """
    dotted_revno = upstream_branch.revision_id_to_dotted_revno(upstream_revision)
    if len(dotted_revno) > 1:
        revno = -2
    else:
        revno = dotted_revno[0]
    revhistory = upstream_branch.revision_history()
    previous_revision = get_snapshot_revision(previous_version)
    if previous_revision is not None:
        previous_revspec = RevisionSpec.from_string(previous_revision)
        previous_revno, _ = previous_revspec.in_history(upstream_branch)
        # Trim revision history - we don't care about any revisions
        # before the revision of the previous version
    else:
        previous_revno = 0
    revhistory = revhistory[previous_revno:revno+1]
    return _upstream_branch_version(revhistory,
            upstream_branch.tags.get_reverse_tag_dict(), package,
            previous_version,
            lambda version, revision: upstream_version_add_revision(upstream_branch, version, revision))


class UpstreamBranchSource(UpstreamSource):
    """Upstream source that uses the upstream branch.

    :ivar upstream_branch: Branch with upstream sources
    :ivar upstream_version_map: Map from version strings to revids
    """

    def __init__(self, upstream_branch, upstream_revision_map=None,
                 config=None):
        self.upstream_branch = upstream_branch
        self.config = config
        if upstream_revision_map is None:
            self.upstream_revision_map = {}
        else:
            self.upstream_revision_map = upstream_revision_map

    def version_as_revision(self, package, version):
        if version in self.upstream_revision_map:
             return self.upstream_revision_map[version]
        revspec = get_snapshot_revision(version)
        if revspec is not None:
            return RevisionSpec.from_string(
                revspec).as_revision_id(self.upstream_branch)
        return None

    def get_latest_version(self, package, current_version):
        return self.get_version(package, current_version,
            self.upstream_branch.last_revision())

    def get_version(self, package, current_version, revision):
        version = str(upstream_branch_version(self.upstream_branch,
            revision, package, current_version))
        return version

    def fetch_tarball(self, package, version, target_dir):
        self.upstream_branch.lock_read()
        try:
            revid = self.version_as_revision(package, version)
            if revid is None:
                raise PackageVersionNotPresent(package, version, self)
            note("Exporting upstream branch revision %s to create the tarball",
                 revid)
            target_filename = self._tarball_path(package, version, target_dir)
            tarball_base = "%s-%s" % (package, version)
            rev_tree = self.upstream_branch.repository.revision_tree(revid)
            export(rev_tree, target_filename, 'tgz', tarball_base)
        finally:
            self.upstream_branch.unlock()
        return target_filename

    def __repr__(self):
        return "<%s for %r>" % (self.__class__.__name__,
            self.upstream_branch.base)
