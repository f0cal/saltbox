import distutils.dir_util
import glob
import os

import jinja2
import warnings


class TemplateSync:
    @classmethod
    def copy_tree(cls, src_path, dst_path):
        assert os.path.exists(src_path), src_path
        assert os.path.isdir(src_path), src_path
        assert os.path.exists(dst_path), dst_path
        assert os.path.isdir(dst_path), dst_path
        distutils.dir_util.copy_tree(src_path, dst_path)


class RecipeTemplate(TemplateSync):
    DEFAULT_TEMPLATE_VARS = {}
    PATTERN = (
        "{ROOT_DIR}/**"
    )  # FIXME (br) this should be narrowed to only certain files

    def __init__(self, root_dir):
        self._root_dir = root_dir

    @property
    def jinja_env(self):
        j_env = jinja2.Environment(loader=jinja2.FileSystemLoader(self._root_dir))
        j_env.block_start_string = "((*"  # FIXME (br) this is unused
        j_env.block_end_string = "*))"  # FIXME (br)
        j_env.variable_start_string = "{{$"
        j_env.variable_end_string = "$}}"
        j_env.comment_start_string = "((="  # FIXME (br)
        j_env.comment_end_string = "=))"  # FIXME (br)
        return j_env

    def _render_one_inplace(self, possible_template, template_vars):
        env_path = os.path.relpath(possible_template, self._root_dir)
        try:
            new_contents = self.jinja_env.get_template(env_path).render(**template_vars)
        except Exception:
            warnings.warn(f"JINJA rendering failed for {env_path}")
            return
        with open(possible_template, "w") as rendered_template:
            rendered_template.write(new_contents)

    def _render_inplace(self, template_vars):
        pattern = self.PATTERN.format(ROOT_DIR=self._root_dir)
        matches = glob.iglob(pattern, recursive=True)
        for possible_template in matches:
            if not os.path.isfile(possible_template):
                continue
            try:
                self._render_one_inplace(possible_template, template_vars)
            except jinja2.exceptions.TemplateError:
                print(possible_template)
                raise

    def render(self, template_vars):
        self._render_inplace(template_vars)

    @classmethod
    def render_to_path(cls, src_path, dst_path, template_vars=None):
        template_vars = template_vars or {}
        assert isinstance(template_vars, dict)
        cls.copy_tree(src_path, dst_path)
        cls(dst_path).render(template_vars)
        return dst_path
