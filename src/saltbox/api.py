import contextlib
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import types

import salt

from .salt_helpers import SaltMaster, SaltMinion
from .template import RecipeTemplate

HERE = os.path.dirname(__file__)
RSYNC = shutil.which("rsync")
LOG = logging.getLogger(__name__)


def call(arg_list):
    LOG.debug(f"RUN {arg_list}")
    return subprocess.call(arg_list)


def run(cmd_str):
    LOG.debug(f"RUN {cmd_str}")
    return subprocess.run(shlex.split(cmd_str)).returncode


class Registry:
    def __init__(self, template_roots):
        self._template_roots = template_roots

    def append(self, template_root):
        assert os.path.exists(template_root), template_root
        assert os.path.isdir(template_root), template_root
        template_root = os.path.abspath(template_root)
        if template_root in self._template_roots:
            LOG.debug(f"'{template_root}' is duplicate. Skipping.")
            return
        self._template_roots.append(template_root)

    @property
    def template_roots(self):
        return self._template_roots

    @classmethod
    def from_list(cls, template_roots):
        return cls(template_roots)

    @classmethod
    def from_file(cls, registry_path):
        if not os.path.exists(registry_path):
            return cls([])
        roots = open(registry_path, "r").readlines()
        roots = (line.strip() for line in roots)
        roots = (line for line in roots if len(line) > 0)
        roots = list(roots)
        return cls.from_list(roots)

    def to_file(self, registry_path):
        dirname = os.path.dirname(registry_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(registry_path, "w") as registry_file:
            for template_root in self._template_roots:
                registry_file.write(f"{template_root}\n")

    # @classmethod
    # def _hash(cls, path_str):
    #     hsh = hashlib.md5()
    #     hsh.update(path_str.encode())
    #     return hsh.hexdigest()

    # @classmethod
    # def _to_dir(cls, template_root, config_dir):
    #     link_path = os.path.join(config_dir, cls._hash(template_root))
    #     if not os.path.exists(link_path):
    #         os.symlink(template_root, link_path)


# class ServiceFactory():
#     def __init__(self, config_path, *args, **dargs):
#         self.__svc = self.__FACTORY(config_path)
#         super().__init__(config_path, *args, **dargs)
#     def __enter__(self, *args, **dargs):
#         self.__svc.start()
#     def __exit__(self, *args, **dargs):
#         self.__svc.kill()


class Base(contextlib.AbstractContextManager):
    def __init__(self, config_obj):
        self._config_obj = config_obj

    def __enter__(self, *args, **dargs):
        return self

    def __exit__(self, *args, **dargs):
        pass


class MinionFactory(Base):
    MINION_FACTORY = SaltMinion
    # CONFIG_FACTORY = SaltConfig

    def __init__(self, config_obj):
        super().__init__(config_obj)
        self._minion_svc = self.MINION_FACTORY.from_config(config_obj)
        self._block = hasattr(self._config_obj, "block") and getattr(
            self._config_obj, "block"
        )

    def __enter__(self, *args, **dargs):
        self._minion_svc.start()
        return super().__enter__(*args, **dargs)

    def __exit__(self, *args, **dargs):
        result = super().__exit__(*args, **dargs)
        if self._block:
            self._minion_svc.wait()
        if self._minion_svc.running:
            self._minion_svc.stop()
        return result


class MasterFactory(Base):
    MASTER_FACTORY = SaltMaster
    # CONFIG_FACTORY = SaltConfig

    def __init__(self, config_obj, *args, **dargs):
        super().__init__(config_obj, *args, **dargs)
        self._master_svc = self.MASTER_FACTORY.from_config(config_obj)
        self._block = hasattr(self._config_obj, "block") and getattr(
            self._config_obj, "block"
        )

    def __enter__(self, *args, **dargs):
        self._master_svc.start()
        return super().__enter__(*args, **dargs)

    def __exit__(self, *args, **dargs):
        result = super().__exit__(*args, **dargs)
        if self._block:
            self._master_svc.wait()
        if self._master_svc.running:
            self._master_svc.stop()
        return result


class RegistryWriter(Base):
    def __init__(self, config_obj):
        super().__init__(config_obj)

    def add_package(self, package_dir):
        self._registry.append(package_dir)

    def _load(self):
        self._registry = Registry.from_file(self._config_obj.saltbox_registry_path)

    def _save(self):
        self._registry.to_file(self._config_obj.saltbox_registry_path)

    def __enter__(self, *args, **dargs):
        self._load()
        return super().__enter__(*args, **dargs)

    def __exit__(self, *args, **dargs):
        self._save()
        self._registry = None
        return super().__exit__(*args, **dargs)

    # @property
    # def template_paths(self):
    #     return self._template_paths

    # @property
    # def salt_config_path(self):
    #     return os.path.join(self._dst_path, *self.DEFAULT_SALT_CONFIG)

    # @classmethod
    # def _resolve_prefix(cls):
    #     return sys.prefix # TODO (br): This only works if you're in a venv

    # @classmethod
    # def create_config(cls, config_path):
    #     assert not os.path.exists(config_path)
    #     os.makedirs(os.path.dirname(config_path))
    #     open(config_path, 'w').close()


class TemplateRenderer(Base):

    # def __init__(self, *args, **dargs):
    #     self._registry = None
    #     super().__init__(*args, **dargs)

    @classmethod
    def render_all(cls, template_roots, salt_root):
        template_vars = dict(SALTROOT=salt_root)
        for template_root in template_roots:
            cls.render_one(template_root, salt_root, template_vars)

    @classmethod
    def render_one(cls, template_root, salt_root, template_vars):
        _t_vars = template_vars
        with cls._cache_path() as tmp_dir:
            LOG.debug(f"Rendering templates under '{template_root}' -> '{tmp_dir}'")
            RecipeTemplate.render_to_path(template_root, tmp_dir, template_vars=_t_vars)
            cls._merge(tmp_dir, salt_root)

    @classmethod
    def _merge(cls, tmp_dir, dst_root):
        run(f"{RSYNC} -a {tmp_dir}/ {dst_root}")

    @classmethod
    def _cache_path(cls):
        return tempfile.TemporaryDirectory()

    def __enter__(self, *args, **dargs):
        registry = Registry.from_file(self._config_obj.saltbox_registry_path)
        self.render_all(registry.template_roots, self._config_obj.salt_root_path)
        return super().__enter__(*args, **dargs)

    # def __exit__(self, *args, **dargs):
    #     return super().__exit__(*args, **dargs)


class Executor(Base):
    def execute(self, *args, **dargs):
        assert len(args) > 0
        LOG.debug(f"Executing {args}")
        args = list(args)
        exe = os.path.join(self._config_obj.bin_prefix, args.pop(0))
        args = [exe, "--config-dir", self._config_obj.salt_config_path] + args
        # return run(" ".join(args))
        return call(args)


class SaltBox:
    @staticmethod
    def refresh_factory(config_obj):
        bases = [TemplateRenderer]
        if hasattr(config_obj, "master") and config_obj.master:
            raise NotImplementedError()
        if hasattr(config_obj, "minion") and config_obj.minion:
            raise NotImplementedError()
        factory = type("SaltBox", tuple(bases), {})
        return factory(config_obj)

    @staticmethod
    def executor_factory(config_obj):
        bases = [Executor, TemplateRenderer]
        if hasattr(config_obj, "master") and config_obj.master:
            bases.append(MasterFactory)
        if hasattr(config_obj, "minion") and config_obj.minion:
            bases.append(MinionFactory)
        factory = type("SaltBox", tuple(bases), {})
        return factory(config_obj)

    @staticmethod
    def installer_factory(config_obj):
        bases = [RegistryWriter]
        factory = type("SaltBox", tuple(bases), {})
        return factory(config_obj)

        # config_path = os.path.join(sys.prefix, *cls.DEFAULT_BOX_CONFIG)
        # if not os.path.exists(config_path):
        #     cls.create_config(config_path)
        # dst_path = cls._resolve_prefix()
        # bases = [cls]
        # if minion:
        #     bases.append(MinionFactory)
        # if master:
        #     bases.append(MasterFactory)
        # print(bases)
        # factory = type("SaltBox", tuple(bases), {})
        # return factory(config_path, dst_path)


class SaltBoxConfig(types.SimpleNamespace):
    BOX_DEFAULT_REGISTRY_PATH = "etc/saltbox/registry.txt"
    SALT_DEFAULT_CONFIG_PATH = "etc/salt"
    SALT_DEFAULT_RUN_PATH = "var/run"
    # def __init__(self, prefix):
    #     LOG.debug(prefix)
    #     self._prefix = prefix
    # self._minion_config = None
    # self._master_config = None

    # @property
    # def _minion_config_path(self):
    #     return os.path.join(self.config_dir, "minion")

    # @property
    # def _master_config_path(self):
    #     os.path.join(self.config_dir, "master")

    # @property
    # def minion_opts(self):
    #     if self._minion_config is None:
    #         path = self._minion_config_path
    #         assert os.path.exists(path), path
    #         self._minion_config = salt.config.minion_config(path)
    #     return self._minion_config

    # @property
    # def master_opts(self):
    #     if self._master_config is None:
    #         path = self._master_config_path
    #         assert os.path.exists(path)
    #         self._master_config = salt.config.master_config(path)
    #     return self._minion_config

    # @property
    # def config_dir(self):
    #     return os.path.join(self.prefix, "etc", "salt")

    # @property
    # def master_pid(self):
    #     pid_file = os.path.join(self.prefix, "var", "run", "salt-master.pid")
    #     assert os.path.exists(pid_file)
    #     return int(open(pid_file).read())

    @property
    def salt_root_path(self):
        return self.prefix

    @property
    def salt_config_path(self):
        return os.path.join(self.salt_root_path, self.SALT_DEFAULT_CONFIG_PATH)

    @property
    def salt_run_path(self):
        return os.path.join(self.salt_root_path, self.SALT_DEFAULT_RUN_PATH)

    @property
    def bin_prefix(self):
        return os.path.join(self.prefix, "bin")

    @property
    def saltbox_registry_path(self):
        return os.path.join(self.prefix, self.BOX_DEFAULT_REGISTRY_PATH)

    @classmethod
    def from_env(cls, **dargs):
        return cls(prefix=sys.prefix, **dargs)

    def call_client(self):
        mopts = self.minion_opts
        # assert 'file_client' in mopts and mopts['file_client'] == 'local'
        return salt.client.Caller(mopts=mopts)

    def cloud_client(self):
        cfg_path = os.path.join(self.config_dir, "cloud")
        assert os.path.exists(cfg_path)
        opts = salt.config.cloud_config(path=cfg_path)
        return salt.cloud.CloudClient(opts=opts)

    # @classmethod
    # def from_root_dir(cls, root_dir):
    #     return cls(root_dir, cleanup=False)

    # @classmethod
    # def from_config_dir(cls, config_dir):
    #     config_dir, _ = os.path.split(config_dir)
    #     assert _ == "salt", _
    #     assert toekns.pop() == "etc"
    #     return cls(os.path.join(tokens))
