from sys import modules
from os import stat, access, W_OK
from os.path import splitext
from py_compile import compile
from imp import reload
from types import ModuleType

from enums import LOG_NOTICE
import env

def chech_recency(module):
    if type(module) != ModuleType or not '__file__' in module.__dict__:
        # builtin module...
        return True
    if not access(module.__file__, W_OK):
        # system module...
        return True

    path, ext = splitext(module.__file__)
    if ext == '.pyc':
        pyc_stats = stat(module.__file__)
        py_stats  = stat(path + '.py')
        if pyc_stats.st_ctime < py_stats.st_ctime:
            if env.log_level >= LOG_NOTICE[0]:
                env.log.error("[N] Compiling module %s <%s.py>." % (module, path))
            compile(path + '.py')
            return False
        #endif
        return True
    elif ext == '.py':
        if env.log_level >= LOG_NOTICE[0]:
            env.log.error("[N] Compiling module %s <%s.py>." % (module, path))
        try:
            compile(module.__file__)
        except:
            pass
        return False
    elif ext == '.so':
        # it's ok, so is load onle onetime
        return True
    return True
#endif

def import_module(name, autoreload=None, log=None, path=None):
    # check, if file is newer, then compile version
    if env.autoreload and name in modules:
        if not chech_recency(modules[name]):
            if env.log_level >= LOG_NOTICE[0]:
                env.log.error("[N] Reloading module %s <%s>." % (name, pyc))
            reload(modules[name])
        return modules[name]
    #endif
    return __import__(name)
#enddef

# reload all modules which is in dict
def reload_modules():
    if not env.autoreload:
        return
    for name, module in modules.items():
        if not chech_recency(module):
            if env.log_level >= LOG_NOTICE[0]:
                env.log.error("[N] Reloading module %s <%s>." % (name, module.__file__))
            reload(module)            
        #endif
    #endfor
#enddef
