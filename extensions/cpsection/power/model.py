# Copyright (C) 2008 One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

import os
from gettext import gettext as _
import logging

import gconf
import dbus

OHM_SERVICE_NAME = 'org.freedesktop.ohm'
OHM_SERVICE_PATH = '/org/freedesktop/ohm/Keystore'
OHM_SERVICE_IFACE = 'org.freedesktop.ohm.Keystore'

POWERD_FLAG_DIR = '/etc/powerd/flags'
POWERD_INHIBIT_FLAG = '/etc/powerd/flags/inhibit-suspend'

_logger = logging.getLogger('ControlPanel - Power')


class ReadError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def using_powerd():
    # directory exists if powerd running, and it's recent
    # enough to be controllable.
    return os.access(POWERD_FLAG_DIR, os.W_OK)

def get_automatic_pm():
    if using_powerd():
        return not os.access(POWERD_INHIBIT_FLAG, os.R_OK)

    # ohmd
    client = gconf.client_get_default()
    return client.get_bool('/desktop/sugar/power/automatic')

def print_automatic_pm():
    print ('off', 'on')[get_automatic_pm()]

def set_automatic_pm(enabled):
    """Automatic suspends on/off."""

    if using_powerd():
        # powerd
        if enabled == 'off' or enabled == 0:
            try:
                fd = open(POWERD_INHIBIT_FLAG, 'w')
            except IOError:
                _logger.debug('File %s is not writeable' % POWERD_INHIBIT_FLAG)
            else:
                fd.close()
        else:
            os.unlink(POWERD_INHIBIT_FLAG)
        return

    # ohmd
    bus = dbus.SystemBus()
    proxy = bus.get_object(OHM_SERVICE_NAME, OHM_SERVICE_PATH)
    keystore = dbus.Interface(proxy, OHM_SERVICE_IFACE)

    if enabled == 'on' or enabled == 1:
        keystore.SetKey("suspend.automatic_pm", 1)
        enabled = True
    elif enabled == 'off' or enabled == 0:
        keystore.SetKey("suspend.automatic_pm", 0)
        enabled = False
    else:
        raise ValueError(_("Error in automatic pm argument, use on/off."))

    client = gconf.client_get_default()
    client.set_bool('/desktop/sugar/power/automatic', enabled)
    return

def get_extreme_pm():
    client = gconf.client_get_default()
    return client.get_bool('/desktop/sugar/power/extreme')

def print_extreme_pm():
    print ('off', 'on')[get_extreme_pm()]

def set_extreme_pm(enabled):
    """Extreme power management on/off."""

    bus = dbus.SystemBus()
    proxy = bus.get_object(OHM_SERVICE_NAME, OHM_SERVICE_PATH)
    keystore = dbus.Interface(proxy, OHM_SERVICE_IFACE)

    if enabled == 'on' or enabled == 1:
        keystore.SetKey("suspend.extreme_pm", 1)
        enabled = True
    elif enabled == 'off' or enabled == 0:
        keystore.SetKey("suspend.extreme_pm", 0)
        enabled = False
    else:
        raise ValueError(_("Error in extreme pm argument, use on/off."))

    client = gconf.client_get_default()
    client.set_bool('/desktop/sugar/power/extreme', enabled)
    return 0
