import argparse
# import threading
import concurrent.futures
import logging
import os
import shlex
import sys
import tempfile
import time

import saltbox

logging.basicConfig(level=logging.DEBUG)

HERE = os.path.dirname(__file__)
TEST_SALTBOX = os.path.join(HERE, "a_saltbox")


class TempDir(tempfile.TemporaryDirectory):
    pass


# def run(t, prefix):
#     time.sleep(t)
#     cmd = shlex.split('salt-run state.orchestrate test saltenv=foobarbaz')
#     config = saltbox.SaltBoxConfig.from_env(block=False, prefix=prefix)
#     with saltbox.SaltBox.executor_factory(config) as api:
#         assert api.execute(*cmd) == 0, "Nonzero return code"

# def install_test_saltbox(prefix, editable):
#     config = saltbox.SaltBoxConfig.from_env(prefix=prefix, use_install_cache=not editable)
#     with saltbox.SaltBox.installer_factory(config) as api:
#         api.add_package(TEST_SALTBOX)

# def test_concurrency(max_workers=15):
#     with TempDir(prefix="saltbox-pytest-") as tmp_dir:
#         salt_root = tmp_dir
#         os.makedirs(os.path.join(tmp_dir, "bin"))
#         os.symlink(os.path.join(sys.prefix, "bin/salt-run"), os.path.join(tmp_dir, "bin/salt-run"))
#         install_test_saltbox(salt_root, True)
#         with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
#             futures = [pool.submit(run, i, salt_root) for i in range(max_workers)]
#             for future in concurrent.futures.as_completed(futures):
#                 exc = future.exception()
#                 if exc is not None:
#                     raise exc

# if __name__ == '__main__':
#     test_concurrency()
