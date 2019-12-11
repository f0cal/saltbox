import os
import re

import yaml


def loader_factory():
    path_matcher = re.compile(r".*\$\{([^}^{]+)\}.*")

    def path_constructor(loader, node):
        return os.path.expandvars(node.value)

    class EnvVarLoader(yaml.SafeLoader):
        pass

    EnvVarLoader.add_implicit_resolver("!path", path_matcher, None)
    EnvVarLoader.add_constructor("!path", path_constructor)
    return EnvVarLoader


def load_yaml(path):
    return yaml.load(open(path), Loader=loader_factory())
