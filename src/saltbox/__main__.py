import argparse
import logging
import shlex
import subprocess
import sys

import plugnparse

from .api import SaltBox, SaltBoxConfig

cli_entrypoint = plugnparse.entrypoint

BIN_DIR = sys.exec_prefix
# SALTROOT = os.path.join(sys.prefix, "var", "run", "saltbox")
# RSYNC = shutil.which("rsync")
# HERE = os.path.dirname(__file__)

LOG = logging.getLogger(__name__)


def logging_config(log_level):
    logging.basicConfig(level=log_level)


def run(cmd_str):
    print(cmd_str)
    subprocess.run(shlex.split(cmd_str))


def _install_args(parser):
    parser.add_argument("package_dir")
    # parser.add_argument("--base", default=os.path.join(HERE, "template"))


@cli_entrypoint(["install"], args=_install_args)
def _install(parser, package_dir, log_level, editable=True):
    logging_config(log_level)
    config = SaltBoxConfig.from_env()
    with SaltBox.installer_factory(config) as api:
        api.add_package(package_dir)


def _exec_args(parser):
    parser.add_argument("-m", "--master", default=False, action="store_true")
    parser.add_argument("-n", "--minion", default=False, action="store_true")
    parser.add_argument("exec_args", nargs=argparse.REMAINDER)


@cli_entrypoint(["exec"], args=_exec_args)
def _salt_call(parser, exec_args, master, minion, log_level):
    logging_config(log_level)
    config = SaltBoxConfig.from_env(master=master, minion=minion)
    with SaltBox.executor_factory(config) as api:
        assert len(exec_args) > 1
        assert exec_args.pop(0) == "--"
        sys.exit(api.execute(*exec_args))

        # salt_exe = exec_args.pop(0)
        # exec_args = " ".join(exec_args)


# def _salt_call_args(parser):
#     parser.add_argument("args", nargs=argparse.REMAINDER)

# @cli_entrypoint(["call"], args=_salt_call_args)
# def _salt_call(parser, *args, **dargs):
#     with SaltBox.from_env() as api:
#         api.refresh()
#         rest = " ".join(sys.argv[2:])
#         run(f"{BIN_DIR}/bin/salt-call --config={api.salt_config_path} {rest}")

# @cli_entrypoint(["run"], args=_salt_call_args)
# def _salt_run(parser, *args, **dargs):
#     with SaltBox.from_env() as api:
#         api.refresh()
#         rest = " ".join(sys.argv[2:])
#         run(f"{BIN_DIR}/bin/salt-run --config={api.salt_config_path} {rest}")

# @cli_entrypoint(["ssh"], args=_salt_call_args)
# def _salt_ssh(parser, *args, **dargs):
#     with SaltBox.from_env() as api:
#         api.refresh()
#         rest = " ".join(sys.argv[2:])
#         run(f"{BIN_DIR}/bin/salt-ssh --config={api.salt_config_path} {rest}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--log-level", default=None)
    plugnparse.scan_and_run("saltbox", base_parser=parser)


if __name__ == "__main__":
    main()

# @cli_entrypoint(["install"], args=_install_args)
# def _install(parser, package_dir, base, editable=True):
#     if not os.path.exists(SALTROOT):
#         os.makedirs(SALTROOT)
#     if package_dir.endswith("/"):
#         package_dir = package_dir[:-1]
#     t_vars = dict(SALTROOT=SALTROOT)
#     with tempfile.TemporaryDirectory() as tmp_dir:
#         RecipeTemplate.render_to_path(package_dir, tmp_dir, template_vars=t_vars)
#         run(f"{RSYNC} -a {tmp_dir}/ {SALTROOT}")
