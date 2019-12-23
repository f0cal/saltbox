import logging
import os
import subprocess
import time

import salt

LOG = logging.getLogger(__name__)

# templating stuff


# class SilentUndefined(jinja2.DebugUndefined):
#     def _fail_with_undefined_error(self, *args, **kwargs):
#         print(dir(self._undefined_obj))
#         logging.exception("JINJA2: something was undefined!")
#         return str(self)


# def extract_jinja_vars(template_path):
#     search_dir, template_name = os.path.split(template_path)
#     env = jinja2.Environment(loader=jinja2.FileSystemLoader(search_dir))
#     template_source = env.loader.get_source(env, template_name)[0]
#     parsed_content = env.parse(template_source)
#     return jinja2.meta.find_undeclared_variables(parsed_content)


# def render_jinja_partial(template_path, **kwargs):
#     with open(template_path, "r") as template_file:
#         template = jinja2.Template(template_file.read(), undefined=SilentUndefined)
#         return template.render(kwargs)


# def extract_string_vars(template_path):
#     with open(template_path, "r") as template_file:
#         template_str = template_file.read()
#         return string.Formatter().parse(template_str)


# def render_string_partial(template_path, **kwargs):
#     with open(template_path, "r") as template_file:
#         template = string.Template(template_file.read())
#         return template.safe_substitute(**kwargs)


# daemons


class SaltDaemon:
    SIGHUP_SIGNAL = 2
    STATUS_SIGNAL = 0
    CFG_FILENAME = None
    EXE = None
    PIDFILE = None

    def __init__(self, config_obj):
        # assert self.CFG_FILENAME is not None
        assert self.EXE is not None
        self._config_obj = config_obj
        self._running = False

    def start(self, daemon=True):
        if self.running:
            return
        _cfg = self._config_obj.salt_config_path
        # assert os.path.exists(os.path.join(_cfg, cls.CFG_FILENAME))
        args = [self.EXE, "--config-dir", _cfg, "--log-level", "debug"]
        if daemon:
            args.append("--daemon")
        ret_code = subprocess.call(args)
        assert ret_code == 0, ret_code
        self._running = True

    def stop(self):
        if not self.running:
            return
        pid = self.pid
        if pid is not None:
            os.kill(pid, self.SIGHUP_SIGNAL)
        self._running = False

    def wait(self):
        if not self.running:
            return
        pid = self.pid
        assert pid is not None
        while not os.kill(pid, self.STATUS_SIGNAL):
            time.sleep(1)
        self._running = False

    @property
    def running(self):
        return self._running

    @property
    def pid(self):
        pid_file_path = os.path.join(self._config_obj.salt_run_path, self.PIDFILE)
        if not os.path.exists(pid_file_path):
            return None
        return int(open(pid_file_path).read())

    # def __enter__(self):
    #     return self

    # def __exit__(self, *exc):
    #     return self.stop()

    @classmethod
    def from_config(cls, config_obj, running=False):
        daemon = cls(config_obj)
        if running:
            daemon.start()
        return daemon


class SaltMaster(SaltDaemon):
    EXE = "salt-master"
    PIDFILE = "salt-master.pid"


class SaltMinion(SaltDaemon):
    EXE = "salt-minion"
    PIDFILE = "salt-minion.pid"


# config


class SaltConfig:
    # ROOT_DIR_VAR = "ROOT_DIR"
    # PATTERN = "{ROOT_DIR}/**"
    # PREFIX = "salt-config-"

    def __init__(self, root_dir, cleanup=None):
        LOG.debug(root_dir)
        self._root_dir = root_dir
        if cleanup is None:
            cleanup = False
        self._cleanup = cleanup
        self._minion_config = None
        self._master_config = None

    @property
    def _minion_config_path(self):
        return os.path.join(self.config_dir, "minion")

    @property
    def _master_config_path(self):
        os.path.join(self.config_dir, "master")

    @property
    def minion_opts(self):
        if self._minion_config is None:
            path = self._minion_config_path
            assert os.path.exists(path), path
            self._minion_config = salt.config.minion_config(path)
        return self._minion_config

    @property
    def master_opts(self):
        if self._master_config is None:
            path = self._master_config_path
            assert os.path.exists(path)
            self._master_config = salt.config.master_config(path)
        return self._minion_config

    @property
    def config_dir(self):
        return os.path.join(self._root_dir, "etc", "salt")

    @property
    def master_pid(self):
        pid_file = os.path.join(self._root_dir, "var", "run", "salt-master.pid")
        assert os.path.exists(pid_file)
        return int(open(pid_file).read())

    def call_client(self):
        mopts = self.minion_opts
        # assert 'file_client' in mopts and mopts['file_client'] == 'local'
        return salt.client.Caller(mopts=mopts)

    def cloud_client(self):
        cfg_path = os.path.join(self.config_dir, "cloud")
        assert os.path.exists(cfg_path)
        opts = salt.config.cloud_config(path=cfg_path)
        return salt.cloud.CloudClient(opts=opts)

    # def __enter__(self):
    #     return self

    # def __exit__(self, *exc):
    #     if self._cleanup == False:
    #         return self._cleanup
    #     return shutil.rmtree(self._root_dir, ignore_errors=True)

    # @classmethod
    # def from_root_dir(cls, config_dir, cleanup=None):
    #     root_dir = tempfile.mkdtemp(prefix=cls.PREFIX)
    #     LOG.debug(root_dir)
    #     distutils.dir_util.copy_tree(config_dir, root_dir)
    #     pattern = cls.PATTERN.format(ROOT_DIR=root_dir)
    #     matches = glob.iglob(pattern, recursive=True)
    #     for possible_template in matches:
    #         if not os.path.isfile(possible_template):
    #             continue
    #         new_contents = render_string_partial(possible_template, ROOT_DIR=root_dir)
    #         with open(possible_template, 'w') as rendered_template:
    #             rendered_template.write(new_contents)
    #     return cls(root_dir, cleanup=cleanup)

    @classmethod
    def from_root_dir(cls, root_dir):
        return cls(root_dir, cleanup=False)

    @classmethod
    def from_config_dir(cls, config_dir):
        tokens, _ = os.path.split(config_dir)
        assert _ == "salt", _
        assert tokens.pop() == "etc"
        return cls(os.path.join(tokens))

    @classmethod
    def from_env(cls):
        pass
