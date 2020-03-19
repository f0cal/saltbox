import contextlib
import hashlib
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import types
from filelock import FileLock
import salt

from .salt_helpers import SaltMaster, SaltMinion
from .template import RecipeTemplate

HERE = os.path.dirname(__file__)
RSYNC = shutil.which("rsync")
LOG = logging.getLogger(__name__)


def call(arg_list):
    LOG.debug(f"CALL {arg_list}")
    return subprocess.call(arg_list)


def run(arg_list, capture_output=False):
    LOG.debug(f"RUN {arg_list}")
    kwargs = {}
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE
    return subprocess.run(arg_list, **kwargs)


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


class Base(contextlib.AbstractContextManager):
    def __init__(self, config_obj):
        self._config_obj = config_obj

    def __enter__(self, *args, **dargs):
        return self

    def __exit__(self, *args, **dargs):
        pass


class MinionFactory(Base):
    MINION_FACTORY = SaltMinion

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
            self._master_svc.   wait()
        if self._master_svc.running:
            self._master_svc.stop()
        return result


class RegistryWriter(Base):
    def __init__(self, config_obj):
        self._registry = None
        super().__init__(config_obj)

    def add_package(self, package_dir):
        assert self._registry is not None
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


class Cache(Base):
    def __init__(self, config_obj):
        super().__init__(config_obj)
        if not os.path.exists(self._config_obj.saltbox_cache_root):
            os.makedirs(self._config_obj.saltbox_cache_root)

    def cache_dir(self, package_dir):
        package_dir = os.path.abspath(package_dir)
        hsh = hashlib.md5(package_dir.encode()).hexdigest()
        cache_dir = os.path.join(
            self._config_obj.saltbox_cache_root, hsh
        )  # tempfile.mkdtemp(dir=self._config_obj.saltbox_cache_root)
        return cache_dir

    def add_package(self, package_dir):
        cache_dir = self.cache_dir(package_dir)
        shutil.copytree(package_dir, cache_dir)
        super().add_package(cache_dir)


class BottomTemplate(Base):
    HERE = os.path.dirname(__file__)

    # def __init__(self, config_obj):
    #     super().__init__(config_obj)

    def add_package(self, package_dir):
        super().add_package(self.bottom_template_path)
        super().add_package(package_dir)

    @property
    def bottom_template_path(self):
        return os.path.join(self.HERE, "template")


class TemplateRenderer(Base):
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
        assert RSYNC is not None, "Salt box depends on rsync, please install via your system's package manager"
        lock = FileLock(os.path.join(dst_root, 'lock'))
        with lock:
            LOG.debug(f'Acquired lock {lock} running rsync')
            run(shlex.split(f"{RSYNC} -a --inplace {tmp_dir}/ {dst_root}"))

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
    def _format_args(self, args):
        assert len(args) > 0
        assert os.path.exists(
            self._config_obj.salt_config_path
        ), self._config_obj.salt_config_path
        LOG.debug(f"Executing {args}")
        arg_list = list(args)
        exe_list = [os.path.join(self._config_obj.bin_prefix, arg_list.pop(0))]
        config_list = ["--config-dir", self._config_obj.salt_config_path]
        log_list = ["--log-level", self._config_obj.salt_loglevel]
        return exe_list + config_list + log_list + arg_list

    def execute(self, *args, **dargs):
        args = self._format_args(args)
        return call(args)

    def run(self, *args, **dargs):
        capture_output = dargs.pop('capture_output', False)
        args = self._format_args(args)
        return run(args, capture_output)


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
        if config_obj.use_install_cache:
            bases.insert(0, Cache)
        if not os.path.exists(config_obj.salt_config_path):
            bases.insert(0, BottomTemplate)
        factory = type("SaltBox", tuple(bases), {})
        return factory(config_obj)


class SaltBoxConfig(types.SimpleNamespace):
    BOX_DEFAULT_REGISTRY_PATH = "etc/saltbox/registry.txt"
    BOX_DEFAULT_CACHE_PATH = "var/cache/saltbox"
    SALT_DEFAULT_CONFIG_PATH = "etc/salt"
    SALT_DEFAULT_RUN_PATH = "var/run"

    @property
    def use_install_cache(self):
        if hasattr(self, "_use_install_cache"):
            return self._use_install_cache
        return False

    @property
    def saltbox_cache_root(self):
        return os.path.join(self._prefix, self.BOX_DEFAULT_CACHE_PATH)

    @property
    def salt_root_path(self):
        return self._prefix

    @property
    def salt_config_path(self):
        return os.path.join(self.salt_root_path, self.SALT_DEFAULT_CONFIG_PATH)

    @property
    def salt_run_path(self):
        return os.path.join(self.salt_root_path, self.SALT_DEFAULT_RUN_PATH)

    @property
    def bin_prefix(self):
        if hasattr(self, "_bin_prefix"):
            return self._bin_prefix
        return os.path.join(self._prefix, "bin")

    @property
    def saltbox_registry_path(self):
        return os.path.join(self._prefix, self.BOX_DEFAULT_REGISTRY_PATH)

    @property
    def salt_loglevel(self):
        return "debug"

    @classmethod
    def from_env(cls, **dargs):
        prefix = dargs.pop('prefix', sys.prefix)
        dargs['prefix'] = prefix
        _dargs = {f"_{k}": v for k, v in dargs.items()}
        return cls(**_dargs)

    def call_client(self):
        mopts = self.minion_opts
        return salt.client.Caller(mopts=mopts)

    def cloud_client(self):
        cfg_path = os.path.join(self.config_dir, "cloud")
        assert os.path.exists(cfg_path)
        opts = salt.config.cloud_config(path=cfg_path)
        return salt.cloud.CloudClient(opts=opts)
