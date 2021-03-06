"""
This module tests the test API.  These are high-level integration tests.  Lower level unit tests
should go in test_render.py
"""

import os
import re

import mock
import pytest

from conda_build import api, render
from conda_build.conda_interface import subdir

from .utils import metadata_dir


def test_render_need_download(testing_workdir, testing_config):
    # first, test that the download/render system renders all it can,
    #    and accurately returns its needs

    with pytest.raises((ValueError, SystemExit)):
        metadata, need_download, need_reparse_in_env = api.render(
            os.path.join(metadata_dir, "source_git_jinja2"),
            config=testing_config,
            no_download_source=True)[0]
        assert need_download
        assert need_reparse_in_env

    # Test that allowing source download lets it to the right thing.
    metadata, need_download, need_reparse_in_env = api.render(
        os.path.join(metadata_dir, "source_git_jinja2"),
        config=testing_config,
        no_download_source=False,
        finalize=False)[0]
    assert not need_download
    assert metadata.meta["package"]["version"] == "1.20.2"


def test_render_yaml_output(testing_workdir, testing_config):
    metadata, need_download, need_reparse_in_env = api.render(
        os.path.join(metadata_dir, "source_git_jinja2"),
        config=testing_config)[0]
    yaml_metadata = api.output_yaml(metadata)
    assert "package:" in yaml_metadata

    # writes file with yaml data in it
    api.output_yaml(metadata, os.path.join(testing_workdir, "output.yaml"))
    assert "package:" in open(os.path.join(testing_workdir, "output.yaml")).read()


def test_get_output_file_path(testing_workdir, testing_metadata):
    testing_metadata = render.finalize_metadata(testing_metadata)
    api.output_yaml(testing_metadata, 'recipe/meta.yaml')

    build_path = api.get_output_file_paths(os.path.join(testing_workdir, 'recipe'),
                                          config=testing_metadata.config,
                                          no_download_source=True)[0]
    _hash = testing_metadata.hash_dependencies()
    python = ''.join(testing_metadata.config.variant['python'].split('.')[:2])
    assert build_path == os.path.join(testing_metadata.config.croot,
                                      testing_metadata.config.host_subdir,
                                      "test_get_output_file_path-1.0-py{}{}_1.tar.bz2".format(
                                          python, _hash))


def test_get_output_file_path_metadata_object(testing_metadata):
    testing_metadata.final = True
    build_path = api.get_output_file_paths(testing_metadata)[0]
    _hash = testing_metadata.hash_dependencies()
    python = ''.join(testing_metadata.config.variant['python'].split('.')[:2])
    assert build_path == os.path.join(testing_metadata.config.croot,
                                      testing_metadata.config.host_subdir,
                "test_get_output_file_path_metadata_object-1.0-py{}{}_1.tar.bz2".format(
                    python, _hash))


def test_get_output_file_path_jinja2(testing_workdir, testing_config):
    # If this test does not raise, it's an indicator that the workdir is not
    #    being cleaned as it should.
    recipe = os.path.join(metadata_dir, "source_git_jinja2")

    # First get metadata with a recipe that is known to need a download:
    with pytest.raises((ValueError, SystemExit)):
        build_path = api.get_output_file_paths(recipe,
                                               config=testing_config,
                                               no_download_source=True)[0]

    metadata, need_download, need_reparse_in_env = api.render(
        recipe,
        config=testing_config,
        no_download_source=False)[0]
    build_path = api.get_output_file_paths(metadata)[0]
    _hash = metadata.hash_dependencies()
    python = ''.join(metadata.config.variant['python'].split('.')[:2])
    assert build_path == os.path.join(testing_config.croot, testing_config.host_subdir,
                                      "conda-build-test-source-git-jinja2-1.20.2-"
                                      "py{0}{1}_0_g262d444.tar.bz2".format(python, _hash))


@mock.patch('conda_build.source')
def test_output_without_jinja_does_not_download(mock_source, testing_workdir, testing_config):
        api.get_output_file_path(os.path.join(metadata_dir, "source_git"),
                                              config=testing_config)[0]
        mock_source.provide.assert_not_called()


def test_pin_compatible_semver(testing_config):
    recipe_dir = os.path.join(metadata_dir, '_pin_compatible')
    metadata = api.render(recipe_dir, config=testing_config)[0][0]
    assert 'zlib  >=1.2.8,<2.0a0' in metadata.get_value('requirements/run')


def test_host_entries_finalized(testing_config):
    recipe = os.path.join(metadata_dir, '_host_entries_finalized')
    metadata = api.render(recipe, config=testing_config)
    assert len(metadata) == 2
    outputs = api.get_output_file_paths(recipe, config=testing_config)
    assert any('py27h' in out for out in outputs)
    assert any('py36h' in out for out in outputs)


def test_hash_no_apply_to_custom_build_string(testing_metadata, testing_workdir):
    testing_metadata.meta['build']['string'] = 'steve'
    testing_metadata.meta['requirements']['build'] = ['zlib 1.2.8']

    api.output_yaml(testing_metadata, 'meta.yaml')
    metadata = api.render(testing_workdir)[0][0]

    assert metadata.build_id() == 'steve'


def test_pin_depends(testing_config):
    """This is deprecated functionality - replaced by the more general variants pinning scheme"""
    recipe = os.path.join(metadata_dir, '_pin_depends_strict')
    m = api.render(recipe, config=testing_config)[0][0]
    # the recipe python is not pinned, but having pin_depends set will force it to be.
    assert any(re.search('python\s+[23]\.', dep) for dep in m.meta['requirements']['run'])


def test_cross_recipe_with_only_build_section(testing_config):
    recipe = os.path.join(metadata_dir, '_cross_prefix_elision')
    metadata = api.render(recipe, config=testing_config, bypass_env_check=True)[0][0]
    assert metadata.config.host_subdir != subdir
    assert metadata.config.build_prefix == metadata.config.host_prefix
    assert metadata.config.build_prefix_override
    recipe = os.path.join(metadata_dir, '_cross_prefix_elision_compiler_used')
    metadata = api.render(recipe, config=testing_config, bypass_env_check=True)[0][0]
    assert metadata.config.host_subdir != subdir
    assert metadata.config.build_prefix != metadata.config.host_prefix
    assert not metadata.config.build_prefix_override
