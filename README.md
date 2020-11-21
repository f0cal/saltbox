# saltbox

*A sandboxing mechanism for [`salt`](https://github.com/saltstack/salt).*

`salt` is an infrastructure-as-code (`yaml`+`jinja`) interpreter written in Python. One of the key challenges of working with `salt` is its "sprawl." It typically requires a superuser run-level and drops files all over the filesystem.

"Sandboxing" is the practice of isolating software related to development so that the development environment doesn't affect system function, and vice-versa. `saltbox` uses Python's native `venv` ("virtual environment") mechanism to create a sandbox for `salt` where it can run unpriveleged and in isolation.

In addition to sandboxing, `saltbox` provides some developer-friendly features like:
* Makes `salt` "formulas" installable with `pip` so you can share them easily with other devs.
* Venv-wide formula index, with a nice CLI so you can list all available formulas quickly.

## Quick start

```bash
python3 -m venv ${VENV_DIR} 
source ${VENV_DIR}/bin/activate
git clone https://github.com/f0cal/saltbox && \
  cd saltbox && \
  pip install .
saltbox --help
```
