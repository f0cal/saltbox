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
# import site
import glob
import functools
import tabulate

from .api import SaltBox, SaltBoxConfig
from .formula import Box

cli_entrypoint = plugnparse.entrypoint
LOG = logging.getLogger(__name__)

def logging_config(log_level):
    if log_level is not None:
        logging.basicConfig(level=log_level.upper())

class Venv:
    GLOB = "{path}/*/saltbox.yaml"

    def find_yaml(self, search_path):
        return glob.glob(self.GLOB.format(path=search_path))

    @classmethod
    def from_env(cls):
        return cls()

    @property
    def site_package_paths(self):
        return sys.path

    @property
    def yamls(self):
        # print(self.site_package_paths)
        return sum((self.find_yaml(path) for path in self.site_package_paths), [])

    @property
    def box_paths(self):
        return (os.path.dirname(p) for p in self.yamls)

    @property
    def box_names(self):
        return (os.path.basename(p) for p in self.box_paths)

    # @property
    # def registry(self):
    #     return dict(zip(self.box_names, self.box_paths))

    @property
    def _boxes(self):
        return (self.box_from_path(p) for p in self.box_paths)

    @property
    def boxes(self):
        return dict(zip(self.box_names, self._boxes))

    @classmethod
    def box_from_path(self, path):
        return Box.from_path(path)

def _venv_list_args(parser):
    pass

@cli_entrypoint(["venv", "list"], args=_venv_list_args)
def _venv_list(parser, log_level):
    logging_config(log_level)
    table = []
    for box_name, box_obj in Venv.from_env().boxes.items():
        for formula_name, formula_obj in box_obj.manifest.formulas.items():
            table.append((box_name, box_obj.name, formula_name, formula_obj.descr))
    print(tabulate.tabulate(table))

def _venv_exec_args(parser):
    parser.add_argument("box_name")
    parser.add_argument("formula_name")
    parser.add_argument("exec_args", nargs=argparse.REMAINDER)

@cli_entrypoint(["venv", "exec"], args=_venv_exec_args)
def _venv_exec(parser, log_level, box_name, formula_name, exec_args):
    logging_config(log_level)
    box = Venv.from_env().boxes[box_name]
    assert formula_name in box.manifest.formulas, box.manifest.formulas
    with tempfile.TemporaryDirectory() as tmp_dir:
        formula = box.manifest.formulas[formula_name]
        config = SaltBoxConfig.from_env(prefix=sys.prefix,
                                        use_install_cache=False,
                                        **formula.config
                                        )
        with SaltBox.installer_factory(config) as api:
            api.add_package(box.path)
        with SaltBox.executor_factory(config) as api:
            formula.run(api, *exec_args)
