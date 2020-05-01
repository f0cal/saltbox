import logging
import plugnparse
import yaml
import os
import tempfile
import argparse
import json
import shlex
import sys
import jinja2
import types
import site

from .api import SaltBox, SaltBoxConfig

cli_entrypoint = plugnparse.entrypoint
LOG = logging.getLogger(__name__)

class Formula:

    def __init__(self, blob):
        self._blob = blob

    @property
    def config(self):
        return self._blob["config"]

    @property
    def name(self):
        return self._blob["name"]

    @property
    def runner(self):
        return self._blob["runner"]

    @property
    def cmd(self):
        return self._blob.get("cmd", None)

    @property
    def template(self):
        return self._blob.get("template", None)

    @property
    def saltargs(self):
        return self._blob.get("saltargs", {})

    @classmethod
    def from_blob(cls, blob):
        return cls(blob)

    @property
    def runner(self):
        return self._blob.get("runner", None)

    @property
    def saltenv(self):
        return self._blob["saltenv"]

    @property
    def _runner(self):
        return shlex.split(self.runner)

    @property
    def descr(self):
        return self._blob.get("descr", "")

    def run(self, api, *run_args):
        _test = lambda _: int(_ is not None)
        _fields = list(map(_test, [self.cmd, self.runner, self.template]))
        assert sum(_fields) == 1, _fields
        if self.cmd:
            return self._run_cmd(api, *run_args)
        if self.runner:
            return self._run_runner(api, *run_args)
        if self.template:
            return self._run_template(api, *run_args)

    def _run_runner(self, api, *run_args):
        ns = self.parser.parse_args(run_args)
        pillar = json.dumps(vars(ns))
        saltenv = self.saltenv
        return api.execute(*self._runner,
                           self.name,
                           f"pillar={pillar}",
                           f"saltenv={saltenv}",
                           )

    def _run_cmd(self, api, *run_args):
        ns = self.parser.parse_args(run_args)
        ns.saltargs = " ".join(f"{k}={v}" for k, v in self.saltargs.items()).format(**vars(ns))
        cmd_str = self.cmd.format(**vars(ns))
        _cmd = shlex.split(cmd_str)
        _cmd = [_c for _c in _cmd if _c != '\n']
        return api.execute(*_cmd)

    def _run_template(self, api, *run_args):
        ns = self.parser.parse_args(run_args)
        template = jinja2.Template(self.template)
        _saltbox = types.SimpleNamespace(formula=self, api=api, cli=vars(ns))
        cmd_str = template.render(saltbox=_saltbox)
        _cmd = shlex.split(cmd_str)
        _cmd = [_c for _c in _cmd if _c != '\n']
        return api.execute(*_cmd)

    @property
    def parser(self):
        parser = argparse.ArgumentParser()
        for blob in self._blob["args"]:
            kwargs = blob.copy()
            args = kwargs.pop("name", [])
            if not isinstance(args, list):
                args = [args]
            if "type" in kwargs:
                kwargs["type"] = eval(kwargs["type"])
            parser.add_argument(*args, **kwargs)
        return parser

class Manifest:
    def __init__(self, blob):
        self._blob = blob or {}

    @classmethod
    def from_path(cls, path):
        assert os.path.exists(path), path
        assert os.path.isfile(path), path
        with open(path) as manifest_file:
            return cls(yaml.load(manifest_file))

    @property
    def formulas(self):
        return {Formula.from_blob(entry).name: Formula.from_blob(entry) for
                entry in self._blob.get("formulas", [])}

    @property
    def name(self):
        return self._blob.get("name")

class Box:
    _MANIFEST_FILENAME = "saltbox.yaml"
    _MANIFEST_CLASS = Manifest

    def __init__(self, path):
        self._path = path

    @property
    def path(self):
        return self._path

    @property
    def name(self):
        return self.manifest.name

    @property
    def manifest(self):
        manifest_path = os.path.join(self._path, self._MANIFEST_FILENAME)
        return self._MANIFEST_CLASS.from_path(manifest_path)

    @classmethod
    def from_path(cls, path):
        box = cls(path)
        box.manifest
        return box

    def to_path(self, path):
        pass

    # @classmethod
    # def merge(cls, box1, box2):
    #     pass

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
    with tempfile.TemporaryDirectory() as tmp_dir:
        formula = box.manifest.formulas[formula]
        config = SaltBoxConfig.from_env(prefix=tmp_dir,
                                        bin_prefix=os.path.join(sys.prefix, "bin"),
                                        use_install_cache=False,
                                        **formula.config
                                        )
        with SaltBox.installer_factory(config) as api:
            api.add_package(path)
        with SaltBox.executor_factory(config) as api:
            formula.run(api, *exec_args)
