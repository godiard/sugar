# Copyright (C) 2006-2007, Red Hat, Inc.
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

import logging
from gettext import gettext as _
import gconf

import gobject
import gtk
import dbus

from sugar.graphics import style
from sugar.graphics.icon import get_icon_state
from sugar.graphics.tray import TrayIcon
from sugar.graphics.palette import Palette
from sugar.graphics.xocolor import XoColor

from jarabe.frame.frameinvoker import FrameWidgetInvoker

_ICON_NAME = 'battery'

_STATUS_CHARGING = 0
_STATUS_DISCHARGING = 1
_STATUS_FULLY_CHARGED = 2
_STATUS_NOT_PRESENT = 3

_LEVEL_PROP = 'battery.charge_level.percentage'
_CHARGING_PROP = 'battery.rechargeable.is_charging'
_DISCHARGING_PROP = 'battery.rechargeable.is_discharging'
_PRESENT_PROP = 'battery.present'

class DeviceView(TrayIcon):

    FRAME_POSITION_RELATIVE = 102

    def __init__(self, udi):
        client = gconf.client_get_default()
        self._color = XoColor(client.get_string('/desktop/sugar/user/color'))

        TrayIcon.__init__(self, icon_name=_ICON_NAME, xo_color=self._color)

        self.set_palette_invoker(FrameWidgetInvoker(self))

        self._model = DeviceModel(udi)
        self.palette = BatteryPalette(_('My Battery'))
        self.palette.set_group_id('frame')

        self._model.connect('notify::level',
                            self._battery_status_changed_cb)
        self._model.connect('notify::charging',
                            self._battery_status_changed_cb)
        self._model.connect('notify::discharging',
                            self._battery_status_changed_cb)
        self._model.connect('notify::present',
                            self._battery_status_changed_cb)
        self._update_info()

    def _update_info(self):
        name = _ICON_NAME
        current_level = self._model.props.level
        xo_color = self._color
        badge_name = None

        if not self._model.props.present:
            status = _STATUS_NOT_PRESENT
            badge_name = None
            xo_color = XoColor('%s,%s' % (style.COLOR_WHITE.get_svg(),
                                          style.COLOR_WHITE.get_svg()))
        elif self._model.props.charging:
            status = _STATUS_CHARGING
            name += '-charging'
            xo_color = XoColor('%s,%s' % (style.COLOR_WHITE.get_svg(),
                                          style.COLOR_WHITE.get_svg()))
        elif self._model.props.discharging:
            status = _STATUS_DISCHARGING
            if current_level <= 15:
                badge_name = 'emblem-warning'
        else:
            status = _STATUS_FULLY_CHARGED

        self.icon.props.icon_name = get_icon_state(name, current_level, step=-5)
        self.icon.props.xo_color = xo_color
        self.icon.props.badge_name = badge_name

        self.palette.set_level(current_level)
        self.palette.set_status(status)

    def _battery_status_changed_cb(self, pspec, param):
        self._update_info()

class BatteryPalette(Palette):

    def __init__(self, primary_text):
        Palette.__init__(self, primary_text)

        self._level = 0
        self._progress_bar = gtk.ProgressBar()
        self._progress_bar.set_size_request(
            style.zoom(style.GRID_CELL_SIZE * 4), -1)
        self._progress_bar.show()
        self._status_label = gtk.Label()
        self._status_label.show()

        vbox = gtk.VBox()
        vbox.pack_start(self._progress_bar)
        vbox.pack_start(self._status_label)
        vbox.show()

        self._progress_widget = vbox
        self.set_content(self._progress_widget)

    def set_level(self, percent):
        self._level = percent
        fraction = percent / 100.0
        self._progress_bar.set_fraction(fraction)

    def set_status(self, status):
        current_level = self._level
        secondary_text = ''
        status_text = '%s%%' % current_level

        progress_widget = self._progress_widget
        if status == _STATUS_NOT_PRESENT:
            secondary_text = _('Removed')
            progress_widget = None
        elif status == _STATUS_CHARGING:
            secondary_text = _('Charging')
        elif status == _STATUS_DISCHARGING:
            if current_level <= 15:
                secondary_text = _('Very little power remaining')
            else:
                #TODO: make this less of an wild/educated guess
                minutes_remaining = int(current_level / 0.59)
                remaining_hourpart = minutes_remaining / 60
                remaining_minpart = minutes_remaining % 60
                secondary_text = _('%(hour)d:%(min).2d remaining') % \
                        {'hour': remaining_hourpart, 'min': remaining_minpart}
        else:
            secondary_text = _('Charged')
        self.set_content(progress_widget)

        self.props.secondary_text = secondary_text
        self._status_label.set_text(status_text)

class DeviceModel(gobject.GObject):
    __gproperties__ = {
        'level'       : (int, None, None, 0, 100, 0,
                         gobject.PARAM_READABLE),
        'charging'    : (bool, None, None, False,
                         gobject.PARAM_READABLE),
        'discharging' : (bool, None, None, False,
                         gobject.PARAM_READABLE),
        'present'     : (bool, None, None, False,
                         gobject.PARAM_READABLE)
    }

    def __init__(self, udi):
        gobject.GObject.__init__(self)

        bus = dbus.Bus(dbus.Bus.TYPE_SYSTEM)
        proxy = bus.get_object('org.freedesktop.Hal', udi,
                               follow_name_owner_changes=True)
        self._battery = dbus.Interface(proxy, 'org.freedesktop.Hal.Device')
        bus.add_signal_receiver(self._battery_changed,
                                'PropertyModified',
                                'org.freedesktop.Hal.Device',
                                'org.freedesktop.Hal',
                                udi)

        self._level = self._get_level()
        self._charging = self._get_charging()
        self._discharging = self._get_discharging()
        self._present = self._get_present()

    def _get_level(self):
        try:
            return self._battery.GetProperty(_LEVEL_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s', _LEVEL_PROP)
            return 0

    def _get_charging(self):
        try:
            return self._battery.GetProperty(_CHARGING_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s', _CHARGING_PROP)
            return False

    def _get_discharging(self):
        try:
            return self._battery.GetProperty(_DISCHARGING_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s', _DISCHARGING_PROP)
            return False

    def _get_present(self):
        try:
            return self._battery.GetProperty(_PRESENT_PROP)
        except dbus.DBusException:
            logging.error('Cannot access %s', _PRESENT_PROP)
            return False

    def do_get_property(self, pspec):
        if pspec.name == 'level':
            return self._level
        if pspec.name == 'charging':
            return self._charging
        if pspec.name == 'discharging':
            return self._discharging
        if pspec.name == 'present':
            return self._present

    def get_type(self):
        return 'battery'

    def _battery_changed(self, num_changes, changes_list):
        for change in changes_list:
            if change[0] == _LEVEL_PROP:
                self._level = self._get_level()
                self.notify('level')
            elif change[0] == _CHARGING_PROP:
                self._charging = self._get_charging()
                self.notify('charging')
            elif change[0] == _DISCHARGING_PROP:
                self._discharging = self._get_discharging()
                self.notify('discharging')
            elif change[0] == _PRESENT_PROP:
                self._present = self._get_present()
                self.notify('present')

def setup(tray):
    bus = dbus.Bus(dbus.Bus.TYPE_SYSTEM)
    proxy = bus.get_object('org.freedesktop.Hal',
                            '/org/freedesktop/Hal/Manager')
    hal_manager = dbus.Interface(proxy, 'org.freedesktop.Hal.Manager')

    for udi in hal_manager.FindDeviceByCapability('battery'):
        tray.add_device(DeviceView(udi))
