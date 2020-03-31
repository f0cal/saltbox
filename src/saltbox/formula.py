import logging
import plugnparse
import yaml
import os
import tempfile
import argparse
import json
import shlex
import sys

from .api import SaltBox, SaltBoxConfig

cli_entrypoint = plugnparse.entrypoint
LOG = logging.getLogger(__name__)

class Formula:

    def __init__(self, blob):
        self._blob = blob
    def _verify_args(self, args_dict):
        required_args = set([x['dest'] for x in self._blob['args'] if hasattr(x, 'required') and x['required']])
        if required_args > set(args_dict.keys()):
            missing = required_args - set(args_dict.keys())
            raise TypeError(f"Missing the following arguments: {missing}")

    @property
    def config(self):
        return self._blob["config"]

    @property
    def name(self):
        return self._blob["name"]

    @property
    def runner(self):
        return self._blob["runner"]

    @classmethod
    def from_blob(cls, blob):
        return cls(blob)

    @property
    def runner(self):
        return self._blob["runner"]

    @property
    def saltenv(self):
        return self._blob["saltenv"]

    @property
    def _runner(self):
        return shlex.split(self.runner)

    def run(self, api, **run_args):
        self._verify_args(run_args)
        pillar = json.dumps(run_args)
        saltenv = self.saltenv
        return api.execute(*self._runner,
                           self.name,
                           f"pillar={pillar}",
                           f"saltenv={saltenv}",
                           )

    @property
    def parser(self):
        parser = argparse.ArgumentParser()
        for arg in self._blob["args"]:
            parser.add_argument(**arg)
        return parser

class Manifest:
    def __init__(self, blob):
        self._blob = blob

    @classmethod
    def from_path(cls, path):
        assert os.path.exists(path)
        assert os.path.isfile(path)
        with open(path) as manifest_file:
            return cls(yaml.load(manifest_file))

    @property
    def formulas(self):
        return {Formula.from_blob(entry).name: Formula.from_blob(entry) for entry in self._blob["formulas"]}

class Box:
    _MANIFEST_FILENAME = "saltbox.yaml"
    _MANIFEST_CLASS = Manifest

    def __init__(self, path):
        self._path = path

    @property
    def manifest(self):
        manifest_path = os.path.join(self._path, self._MANIFEST_FILENAME)
        return self._MANIFEST_CLASS.from_path(manifest_path)

    @classmethod
    def from_path(cls, path):
        box = cls(path)
        box.manifest
        return box

def logging_config(log_level):
    if log_level is not None:
        logging.basicConfig(level=log_level.upper())

def ___exec___args(parser):
    parser.add_argument("path")
    parser.add_argument("formula")
    parser.add_argument("exec_args", nargs=argparse.REMAINDER)

@cli_entrypoint(["_", "exec"], args=___exec___args)
def ___exec__(parser, log_level, path, formula, exec_args):
    logging_config(log_level)
    box = Box.from_path(path)
    assert formula in box.manifest.formulas, box.manifest.formulas
    formula = box.manifest.formulas[formula]
    ns = formula.parser.parse_args(exec_args)
    with tempfile.TemporaryDirectory() as tmp_dir:
        config = SaltBoxConfig.from_env(prefix=tmp_dir,
                                        bin_prefix=os.path.join(sys.prefix, "bin"),
                                        use_install_cache=False,
                                        **formula.config
                                        )
        with SaltBox.installer_factory(config) as api:
            api.add_package(path)
        with SaltBox.executor_factory(config) as api:
            formula.run(api, **vars(ns))
        # os.system(f"tree {tmp_dir}")
