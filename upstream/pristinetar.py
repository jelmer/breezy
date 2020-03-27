#    pristinetar.py -- Providers of upstream source
#    Copyright (C) 2009-2011 Canonical Ltd.
#    Copyright (C) 2009 Jelmer Vernooij <jelmer@debian.org>
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


from base64 import (
    standard_b64decode,
    standard_b64encode,
    )
import configparser
from debian.copyright import globs_to_re
import errno
import os
import subprocess
import tempfile

from .... import debug
from ..errors import (
    PackageVersionNotPresent,
    )
from ..upstream import UpstreamSource
from ....export import export
from ..util import (
    subprocess_setup,
    )

from .... import (
    osutils,
    revision as _mod_revision,
    )
from ....commit import NullCommitReporter
from ....errors import (
    BzrError,
    NoSuchRevision,
    NoSuchTag,
    NoSuchFile,
    NotBranchError,
    )
from ....trace import (
    mutter,
    note,
    warning,
    )

from .tags import (
    GbpTagFormatError,
    gbp_expand_tag_name,
    mangle_version_for_git,
    upstream_tag_name,
    is_upstream_tag,
    possible_upstream_tag_names,
    search_for_upstream_version,
    upstream_tag_version,
    )


class PristineTarError(BzrError):
    _fmt = 'There was an error using pristine-tar: %(error)s.'

    def __init__(self, error):
        BzrError.__init__(self, error=error)


class PristineTarDeltaTooLarge(PristineTarError):
    _fmt = 'The delta generated was too large: %(error)s.'


class PristineTarDeltaAbsent(PristineTarError):
    _fmt = 'There is not delta present for %(version)s.'


class PristineTarDeltaExists(PristineTarError):
    _fmt = 'An existing pristine tar entry exists for %(filename)s'


def git_store_pristine_tar(branch, filename, tree_id, delta, force=False):
    tree = branch.create_memorytree()
    with tree.lock_write():
        id_filename = '%s.id' % filename
        delta_filename = '%s.delta' % filename
        try:
            existing_id = tree.get_file_text(id_filename)
            existing_delta = tree.get_file_text(delta_filename)
        except NoSuchFile:
            pass
        else:
            if existing_id.strip(b'\n') == tree_id and delta == existing_delta:
                # Nothing to do.
                return
            if not force:
                raise PristineTarDeltaExists(filename)
        tree.put_file_bytes_non_atomic(id_filename, tree_id + b'\n')
        tree.put_file_bytes_non_atomic(delta_filename, delta)
        tree.add([id_filename, delta_filename], [None, None], ['file', 'file'])
        revid = tree.commit(
            'Add pristine tar data for %s' % filename,
            reporter=NullCommitReporter())
        mutter('Added pristine tar data for %s: %s',
               filename, revid)


def reconstruct_pristine_tar(dest, delta, dest_filename):
    """Reconstruct a pristine tarball from a directory and a delta.

    :param dest: Directory to pack
    :param delta: pristine-tar delta
    :param dest_filename: Destination filename
    """
    command = ["pristine-tar", "gentar", "-",
               os.path.abspath(dest_filename)]
    try:
        proc = subprocess.Popen(
                command, stdin=subprocess.PIPE,
                cwd=dest, preexec_fn=subprocess_setup,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise PristineTarError("pristine-tar is not installed")
        else:
            raise
    (stdout, stderr) = proc.communicate(delta)
    if proc.returncode != 0:
        raise PristineTarError("Generating tar from delta failed: %s" % stdout)


def make_pristine_tar_delta(dest, tarball_path):
    """Create a pristine-tar delta for a tarball.

    :param dest: Directory to generate pristine tar delta for
    :param tarball_path: Path to the tarball
    :return: pristine-tarball
    """
    # If tarball_path is relative, the cwd=dest parameter to Popen will make
    # pristine-tar faaaail. pristine-tar doesn't use the VFS either, so we
    # assume local paths.
    tarball_path = osutils.abspath(tarball_path)
    command = ["pristine-tar", "gendelta", tarball_path, "-"]
    try:
        proc = subprocess.Popen(
                command, stdout=subprocess.PIPE,
                cwd=dest, preexec_fn=subprocess_setup,
                stderr=subprocess.PIPE)
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise PristineTarError("pristine-tar is not installed")
        else:
            raise
    (stdout, stderr) = proc.communicate()
    if proc.returncode != 0:
        if b'excessively large binary delta' in stderr:
            raise PristineTarDeltaTooLarge(stderr)
        else:
            raise PristineTarError(
                "Generating delta from tar failed: %s" % stderr)
    return stdout


def make_pristine_tar_delta_from_tree(
        tree, tarball_path, subdir=None, exclude=None):
    with tempfile.TemporaryDirectory(prefix="builddeb-pristine-") as tmpdir:
        dest = os.path.join(tmpdir, "orig")
        with tree.lock_read():
            export(tree, dest, format='dir', subdir=subdir)
        try:
            return make_pristine_tar_delta(dest, tarball_path)
        except PristineTarDeltaTooLarge:
            raise
        except PristineTarError:  # I.e. not PristineTarDeltaTooLarge
            if 'pristine-tar' in debug.debug_flags:
                revno, revid = tree.branch.last_revision_info()
                preserved = osutils.pathjoin(osutils.dirname(tarball_path),
                                             'orig-%s' % (revno,))
                mutter('pristine-tar failed for delta between %s rev: %s'
                       ' and tarball %s'
                       % (tree.basedir, (revno, revid), tarball_path))
                osutils.copy_tree(
                    dest, preserved)
                mutter('The failure can be reproduced with:\n'
                       '  cd %s\n'
                       '  pristine-tar -vdk gendelta %s -'
                       % (preserved, tarball_path))
            raise


def revision_has_pristine_tar_delta(rev):
    return (u'deb-pristine-delta' in rev.properties
            or u'deb-pristine-delta-bz2' in rev.properties
            or u'deb-pristine-delta-xz' in rev.properties)


def revision_pristine_tar_delta(rev):
    if u'deb-pristine-delta' in rev.properties:
        uuencoded = rev.properties[u'deb-pristine-delta']
    elif u'deb-pristine-delta-bz2' in rev.properties:
        uuencoded = rev.properties[u'deb-pristine-delta-bz2']
    elif u'deb-pristine-delta-xz' in rev.properties:
        uuencoded = rev.properties[u'deb-pristine-delta-xz']
    else:
        assert revision_has_pristine_tar_delta(rev)
        raise AssertionError(
            "Not handled new delta type in pristine_tar_delta")
    return standard_b64decode(uuencoded)


def revision_pristine_tar_format(rev):
    if u'deb-pristine-delta' in rev.properties:
        return 'gz'
    elif u'deb-pristine-delta-bz2' in rev.properties:
        return 'bz2'
    elif u'deb-pristine-delta-xz' in rev.properties:
        return 'xz'
    assert revision_has_pristine_tar_delta(rev)
    raise AssertionError(
        "Not handled new delta type in pristine_tar_format")


class PristineTarSource(UpstreamSource):
    """Source that uses the pristine-tar revisions in the packaging branch."""

    def __init__(self, branch, gbp_tag_format=None, pristine_tar=None):
        self.branch = branch
        self.gbp_tag_format = gbp_tag_format
        self.pristine_tar = pristine_tar

    def __repr__(self):
        return "<%s at %s>" % (self.__class__.__name__, self.branch.base)

    @classmethod
    def from_tree(cls, branch, tree):
        if tree and tree.has_filename('debian/gbp.conf'):
            parser = configparser.ConfigParser(defaults={
                'pristine-tar': 'false',
                'upstream-tag': 'upstream/%(version)s'},
                strict=False)
            parser.read_string(
                tree.get_file_text('debian/gbp.conf').decode(
                    'utf-8', errors='replace'),
                'debian/gbp.conf')
            try:
                gbp_tag_format = parser.get(
                    'import-orig', 'upstream-tag', raw=True)
            except configparser.Error:
                try:
                    gbp_tag_format = parser.get(
                        'DEFAULT', 'upstream-tag', raw=True)
                except configparser.Error:
                    gbp_tag_format = None
            try:
                pristine_tar = parser.getboolean(
                    'import-orig', 'pristine-tar')
            except configparser.Error:
                try:
                    pristine_tar = parser.getboolean(
                        'DEFAULT', 'pristine-tar')
                except configparser.Error:
                    pristine_tar = None
        else:
            gbp_tag_format = None
            pristine_tar = None
        return cls(branch, gbp_tag_format, pristine_tar)

    def tag_name(self, version, component=None, distro=None):
        """Gets the tag name for the upstream part of version.

        :param version: the Version object to extract the upstream
            part of the version number from.
        :param component: Name of the component (None for base)
        :param distro: Optional distribution name
        :return: a String with the name of the tag.
        """
        if self.gbp_tag_format is not None:
            return gbp_expand_tag_name(self.gbp_tag_format, version)
        git_style = bool(getattr(self.branch.repository, '_git', None))
        return upstream_tag_name(version, component, distro, git_style)

    def tag_version(self, version, revid, component=None):
        """Tags the upstream branch's last revision with an upstream version.

        Sets a tag on the last revision of the upstream branch and on the main
        branch with a tag that refers to the upstream part of the version
        provided.

        :param version: the upstream part of the version number to derive the
            tag name from.
        :param component: name of the component that is being imported
            (None for base)
        :param revid: the revid to associate the tag with, or None for the
            tip of self.pristine_upstream_branch.
        :return The tag name, revid of the added tag.
        """
        tag_name = self.tag_name(version, component=component)
        self.branch.tags.set_tag(tag_name, revid)
        return tag_name, revid

    def import_component_tarball(
            self, package, version, tree, parent_ids,
            component=None, md5=None, tarball=None, author=None,
            timestamp=None, subdir=None, exclude=None,
            force_pristine_tar=False, committer=None,
            files_excluded=None, reuse_existing=True):
        """Import a tarball.

        :param package: Package name
        :param version: Upstream version
        :param parent_ids: Dictionary mapping component names to revision ids
        :param component: Component name (None for base)
        :param exclude: Exclude directories
        :param force_pristine_tar: Whether to force creating a pristine-tar
            branch if one does not exist.
        :param committer: Committer identity to use
        :param reuse_existing: Whether to reuse existing tarballs, or raise
            an error
        """
        if exclude is None:
            exclude = []
        if files_excluded:
            files_excluded_re = globs_to_re(files_excluded)
        else:
            files_excluded_re = None

        def include_change(c):
            try:
                path = c.path[1]
            except AttributeError:  # breezy < 3.1
                path = c[1][1]
            if path is None:
                return True
            if exclude and osutils.is_inside_any(exclude, path):
                return False
            if files_excluded_re and files_excluded_re.match(path):
                return False
            return True
        message = "Import upstream version %s" % (version,)
        revprops = {}
        supports_custom_revprops = (
            tree.branch.repository._format.supports_custom_revision_properties)
        if component is not None:
            message += ", component %s" % component
            if supports_custom_revprops:
                revprops["deb-component"] = component
        git_delta = None
        if md5 is not None:
            if supports_custom_revprops:
                revprops["deb-md5"] = md5
            else:
                message += ", md5 %s" % md5
            delta = make_pristine_tar_delta_from_tree(
                tree, tarball, subdir=subdir, exclude=exclude)
            if supports_custom_revprops:
                uuencoded = standard_b64encode(delta).decode('ascii')
                if tarball.endswith(".tar.bz2"):
                    revprops[u"deb-pristine-delta-bz2"] = uuencoded
                elif tarball.endswith(".tar.xz"):
                    revprops[u"deb-pristine-delta-xz"] = uuencoded
                else:
                    revprops[u"deb-pristine-delta"] = uuencoded
            else:
                if getattr(tree.branch.repository, '_git', None):
                    git_delta = delta
                else:
                    warning('Not setting pristine tar revision properties '
                            'since the repository does not support it.')
        else:
            delta = None
        if author is not None:
            revprops['authors'] = author
        timezone = None
        if timestamp is not None:
            timezone = timestamp[1]
            timestamp = timestamp[0]
        if len(parent_ids) == 0:
            base_revid = _mod_revision.NULL_REVISION
        else:
            base_revid = parent_ids[0]
        basis_tree = tree.branch.repository.revision_tree(base_revid)
        with tree.lock_write():
            builder = tree.branch.get_commit_builder(
                    parents=parent_ids, revprops=revprops, timestamp=timestamp,
                    timezone=timezone, committer=committer)
            try:
                changes = [c for c in tree.iter_changes(basis_tree) if
                           include_change(c)]
                list(builder.record_iter_changes(tree, base_revid, changes))
                builder.finish_inventory()
            except BaseException:
                builder.abort()
                raise
            revid = builder.commit(message)
            tag_name = self.tag_name(version, component=component)
            tree.branch.tags.set_tag(tag_name, revid)
            tree.update_basis_by_delta(revid, builder.get_basis_delta())
        if git_delta is not None:
            revtree = tree.branch.repository.revision_tree(revid)
            tree_id = revtree._lookup_path(u'')[2]
            try:
                pristine_tar_branch = self.branch.controldir.open_branch(
                    name='pristine-tar')
            except NotBranchError:
                if force_pristine_tar:
                    note('Creating new pristine-tar branch.')
                    pristine_tar_branch = self.branch.controldir.create_branch(
                        name='pristine-tar')
                else:
                    note('Not storing pristine-tar metadata, '
                         'since there is no pristine-tar branch.')
                    pristine_tar_branch = None
            if pristine_tar_branch:
                try:
                    git_store_pristine_tar(
                        pristine_tar_branch, os.path.basename(tarball),
                        tree_id, git_delta)
                except PristineTarDeltaExists:
                    if reuse_existing:
                        note('Reusing existing tarball, since delta exists.')
                        return tag_name, revid
                    raise
        mutter(
            'imported %s version %s component %r as revid %s, tagged %s',
            package, version, component, revid, tag_name)
        return tag_name, revid

    def fetch_component_tarball(self, package, version, component, target_dir):
        revid = self.version_component_as_revision(package, version, component)
        try:
            rev = self.branch.repository.get_revision(revid)
        except NoSuchRevision:
            raise PackageVersionNotPresent(package, version, self)
        if revision_has_pristine_tar_delta(rev):
            format = revision_pristine_tar_format(rev)
        else:
            format = 'gz'
        target_filename = self._tarball_path(package, version, component,
                                             target_dir, format=format)
        note("Using pristine-tar to reconstruct %s.",
             os.path.basename(target_filename))
        try:
            self.reconstruct_pristine_tar(
                revid, package, version, target_filename)
        except PristineTarError:
            raise PackageVersionNotPresent(package, version, self)
        return target_filename

    def fetch_tarballs(self, package, version, target_dir, components=None):
        note("Looking for upstream tarball in local branch.")
        if components is None:
            # Scan tags for components
            try:
                components = self._components_by_version()[version].keys()
            except KeyError:
                raise PackageVersionNotPresent(package, version, self)
        return [
            self.fetch_component_tarball(
                package, version, component, target_dir)
            for component in components]

    def _has_revision(self, revid, md5=None):
        with self.branch.lock_read():
            graph = self.branch.repository.get_graph()
            if not graph.is_ancestor(revid, self.branch.last_revision()):
                return False
        if md5 is None:
            return True
        rev = self.branch.repository.get_revision(revid)
        try:
            return rev.properties['deb-md5'] == md5
        except KeyError:
            warning("tag present in branch, but there is no "
                    "associated 'deb-md5' property in associated "
                    "revision %s", revid)
            return True

    def version_as_revisions(self, package, version, tarballs=None):
        if tarballs is None:
            # FIXME: What if there are multiple tarballs?
            return {
                None: self.version_component_as_revision(
                    package, version, component=None)}
        ret = {}
        for (tarball, component, md5) in tarballs:
            ret[component] = self.version_component_as_revision(
                package, version, component, md5)
        return ret

    def version_component_as_revision(self, package, version, component,
                                      md5=None):
        for tag_name in self.possible_tag_names(version, component=component):
            try:
                revid = self.branch.tags.lookup_tag(tag_name)
            except NoSuchTag:
                continue
            else:
                if self._has_revision(revid, md5=md5):
                    return revid
        revid = search_for_upstream_version(
            self.branch, package, version, component, md5)
        tag_name = self.tag_name(version, component=component)
        if revid is not None:
            warning(
                "Upstream import of %s lacks a tag. Set one by running: "
                "brz tag -rrevid:%s %s", version, revid.decode('utf-8'),
                tag_name)
            return revid
        try:
            return self.branch.tags.lookup_tag(tag_name)
        except NoSuchTag:
            raise PackageVersionNotPresent(package, version, self)

    def has_version(self, package, version, tarballs=None):
        if tarballs is None:
            return self.has_version_component(package, version, component=None)
        else:
            for (tarball, component, md5) in tarballs:
                if not self.has_version_component(
                        package, version, component, md5):
                    return False
            return True

    def has_version_component(self, package, version, component, md5=None):
        for tag_name in self.possible_tag_names(version, component=component):
            try:
                revid = self.branch.tags.lookup_tag(tag_name)
            except NoSuchTag:
                continue
            else:
                if self._has_revision(revid, md5=md5):
                    return True
        return False

    def possible_tag_names(self, version, component):
        tags = []
        if self.gbp_tag_format:
            tags.append(gbp_expand_tag_name(self.gbp_tag_format, version))

        tags.extend(possible_upstream_tag_names(version, component))

        return tags

    def get_pristine_tar_delta(self, package, version, dest_filename,
                               revid=None):
        rev = self.branch.repository.get_revision(revid)
        if revision_has_pristine_tar_delta(rev):
            return revision_pristine_tar_delta(rev)
        try:
            pristine_tar_branch = self.branch.controldir.open_branch(
                'pristine-tar')
        except NotBranchError:
            pass
        else:
            revtree = pristine_tar_branch.repository.revision_tree(
                pristine_tar_branch.last_revision())
            try:
                return revtree.get_file_text(
                    '%s.delta' % osutils.basename(dest_filename))
            except NoSuchFile:
                raise PristineTarDeltaAbsent(version)
        raise PristineTarDeltaAbsent(version)

    def reconstruct_pristine_tar(self, revid, package, version, dest_filename):
        """Reconstruct a pristine-tar tarball from a bzr revision."""
        tree = self.branch.repository.revision_tree(revid)
        with tempfile.TemporaryDirectory(prefix="bd-pristine-") as tmpdir:
            dest = os.path.join(tmpdir, "orig")
            try:
                delta = self.get_pristine_tar_delta(
                    package, version, dest_filename, revid)
                export(tree, dest, format='dir')
                reconstruct_pristine_tar(dest, delta, dest_filename)
            except PristineTarDeltaAbsent:
                export(tree, dest_filename, per_file_timestamps=True)

    def _components_by_version(self):
        ret = {}
        for tag_name, tag_revid in self.branch.tags.get_tag_dict().items():
            if not is_upstream_tag(tag_name):
                continue
            (component, version) = upstream_tag_version(tag_name)
            ret.setdefault(version, {})[component] = tag_revid
        return ret

    def iter_versions(self):
        """Iterate over all upstream versions.

        :return: Iterator over (tag_name, version, revid) tuples
        """
        ret = self._components_by_version()
        return ret.items()



