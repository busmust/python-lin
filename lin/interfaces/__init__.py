# coding: utf-8

"""
Interfaces contain low level implementations that interact with CAN hardware.
"""

import warnings
from pkg_resources import iter_entry_points


# interface_name => (module, classname)
BACKENDS = {
    'bmlin':            ('lin.interfaces.bmlin',            'BmLinBus'),
}

BACKENDS.update({
    interface.name: (interface.module_name, interface.attrs[0])
    for interface in iter_entry_points('lin.interface')
})

# Old entry point name. May be removed >3.0.
for interface in iter_entry_points('python_lin.interface'):
    BACKENDS[interface.name] = (interface.module_name, interface.attrs[0])
    warnings.warn('{} is using the deprecated python_lin.interface entry point. '.format(interface.name) +
                  'Please change to lin.interface instead.', DeprecationWarning)

VALID_INTERFACES = frozenset(list(BACKENDS.keys()) + ['socketlin_native', 'socketlin_ctypes'])
