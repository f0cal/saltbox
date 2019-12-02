=======
saltbox
=======


Saltbox is a thin wrapper around [salt](https://github.com/saltstack/salt "Salt github") that allows for salt to run in 
non-privileged mode and contains all of salts files inside of a python virtual environment. 

Getting start
====
####Installation
Saltbox is meant to be used with python virtual environments therefore it should always be installed in one: 
```
python3 -m venv $VENV_DIR 
source env/bin/activate
git clone https://github.com/f0cal/saltbox.git
cd saltbox 
pip install .
```

#### Usage
First point saltbox to your local file root:
 
`saltbox install $MY_SALT_DIR `

$MY_SALT_DIR should contain any state or configuration file you may wish to use with the salt box installation.

To start a master process using the local configuration use the `exec` command as follows: 

`saltbox exec -- salt-master -d`

Saltbox also provides an option to run the master only when needed by provided the `-m` option: 

`saltbox -m exec -- salt '*' state.apply`

If you also need a salt minion running use the `-n` option

Note
====

This project has been set up using PyScaffold 3.2.1. For details and usage
information on PyScaffold see https://pyscaffold.org/.
