import argparse
import logging
import sys

import plugnparse

from .api import SaltBox, SaltBoxConfig

cli_entrypoint = plugnparse.entrypoint
LOG = logging.getLogger(__name__)


def logging_config(log_level):
    if log_level is not None:
        logging.basicConfig(level=log_level.upper())


def _install_args(parser):
    parser.add_argument("package_dir")
    parser.add_argument("-e", "--editable", default=False, action="store_true")
    # parser.add_argument("--base", default=os.path.join(HERE, "template"))


@cli_entrypoint(["install"], args=_install_args)
def _install(parser, package_dir, log_level, editable=False):
    logging_config(log_level)
    use_install_cache = not editable
    config = SaltBoxConfig.from_env(use_install_cache=use_install_cache)
    with SaltBox.installer_factory(config) as api:
        api.add_package(package_dir)


def _exec_args(parser):
    parser.add_argument("-m", "--master", default=False, action="store_true")
    parser.add_argument("-n", "--minion", default=False, action="store_true")
    parser.add_argument("exec_args", nargs=argparse.REMAINDER)


@cli_entrypoint(["exec"], args=_exec_args)
def _exec(parser, exec_args, master, minion, log_level):
    logging_config(log_level)
    config = SaltBoxConfig.from_env(master=master, minion=minion)
    with SaltBox.executor_factory(config) as api:
        assert len(exec_args) > 1
        assert exec_args.pop(0) == "--"
        sys.exit(api.execute(*exec_args))


def _refresh_args(parser):
    pass


@cli_entrypoint(["refresh"], args=_refresh_args)
def _refresh(parser, log_level):
    logging_config(log_level)
    config = SaltBoxConfig.from_env()
    with SaltBox.refresh_factory(config):
        sys.exit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log-level", default=None)
    plugnparse.scan_and_run("saltbox", base_parser=parser)


if __name__ == "__main__":
    main()
