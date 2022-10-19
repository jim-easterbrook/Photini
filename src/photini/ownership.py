##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2021-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
##
##  This program is free software: you can redistribute it and/or
##  modify it under the terms of the GNU General Public License as
##  published by the Free Software Foundation, either version 3 of the
##  License, or (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##  General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see
##  <http://www.gnu.org/licenses/>.

from datetime import datetime
import logging

from photini.metadata import ImageMetadata
from photini.pyqt import *
from photini.widgets import (DropDownSelector, Label, LangAltWidget,
                             MultiLineEdit, PushButton, SingleLineEdit)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class RightsDropDown(DropDownSelector):
    def __init__(self, key):
        super(RightsDropDown, self).__init__(key, extendable=True)
        self.config_store = QtWidgets.QApplication.instance().config_store
        # list of known licences
        licences = [
            (self.tr('All rights reserved'), None),
            (self.tr('Attribution 4.0 (CC BY 4.0)'),
             'https://creativecommons.org/licenses/by/4.0/'),
            (self.tr('Attribution-ShareAlike 4.0 (CC BY-SA 4.0)'),
             'https://creativecommons.org/licenses/by-sa/4.0/'),
            (self.tr('Attribution-NonCommercial 4.0 (CC BY-NC 4.0)'),
             'https://creativecommons.org/licenses/by-nc/4.0/'),
            (self.tr(
                'Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)'),
             'https://creativecommons.org/licenses/by-nc-sa/4.0/'),
            (self.tr('Attribution-NoDerivatives 4.0 (CC BY-ND 4.0)'),
             'https://creativecommons.org/licenses/by-nd/4.0/'),
            (self.tr(
                'Attribution-NonCommercial-NoDerivatives 4.0 (CC BY-NC-ND 4.0)'),
             'https://creativecommons.org/licenses/by-nc-nd/4.0/'),
            (self.tr('CC0 1.0 Universal (CC0 1.0) Public Domain Dedication'),
             'https://creativecommons.org/publicdomain/zero/1.0/'),
            (self.tr('Public Domain Mark 1.0'),
             'https://creativecommons.org/publicdomain/mark/1.0/'),
            ]
        # add user defined licences
        licences += self.config_store.get('ownership', 'licences') or []
        # set up widget
        self.set_values(licences)

    def define_new_value(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(self.tr('Define new licence'))
        dialog.setLayout(FormLayout())
        name = SingleLineEdit('name', spell_check=True)
        dialog.layout().addRow(self.tr('Name'), name)
        url = SingleLineEdit('url')
        dialog.layout().addRow(self.tr('URL'), url)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if execute(dialog) != QtWidgets.QDialog.DialogCode.Accepted:
            return None, None
        name = name.toPlainText()
        url = url.toPlainText()
        if not name and url:
            return None, None
        licences = self.config_store.get('ownership', 'licences') or []
        licences.append((name, url))
        self.config_store.set('ownership', 'licences', licences)
        return name, url

    @QtSlot(QtGui.QContextMenuEvent)
    @catch_all
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        for n in range(1, self._last_idx()):
            action = QtGui2.QAction(
                self.tr('Open link to "{}"').format(self.itemText(n)),
                parent=self)
            action.setData(self.itemData(n))
            menu.addAction(action)
        action = execute(menu, event.globalPos())
        if not action:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(action.data()))


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('OwnerTab', '&Ownership metadata')

    def __init__(self, image_list, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # construct widgets
        self.enableable = []
        ## data fields
        form, self.widgets = self.data_form()
        self.enableable.append(form.widget())
        for key in self.widgets:
            self.widgets[key].new_value.connect(self.new_value)
        self.layout().addWidget(form)
        ## buttons
        buttons = QtWidgets.QVBoxLayout()
        buttons.addStretch(1)
        init_template = PushButton(
            translate('OwnerTab', 'Initialise template'), lines=2)
        init_template.clicked.connect(self.init_template)
        self.enableable.append(init_template)
        buttons.addWidget(init_template)
        edit_template = PushButton(
            translate('OwnerTab', 'Edit template'), lines=2)
        edit_template.clicked.connect(self.edit_template)
        buttons.addWidget(edit_template)
        apply_template = PushButton(
            translate('OwnerTab', 'Apply template'), lines=2)
        apply_template.clicked.connect(self.apply_template)
        self.enableable.append(apply_template)
        buttons.addWidget(apply_template)
        self.layout().addLayout(buttons)
        # disable data entry until an image is selected
        self.set_enabled(False)
        # update config
        value = self.config_store.get('ownership', 'usageterms')
        if value:
            self.config_store.set('ownership', 'rights/UsageTerms', value)
            self.config_store.delete('ownership', 'usageterms')
        for key in self.widgets:
            if '/' not in key:
                continue
            if key.startswith('rights'):
                old_key = key.replace('/', '_')
            else:
                old_key = key.split('/')[1]
            value = self.config_store.get('ownership', old_key)
            if value:
                self.config_store.set('ownership', key, value)
                self.config_store.delete('ownership', old_key)
        if not self.config_store.get('ownership', 'copyright'):
            name = self.config_store.get('user', 'copyright_name') or ''
            text = self.config_store.get('user', 'copyright_text') or ''
            if text:
                self.config_store.set('ownership', 'copyright',
                                      text.format(year='%Y', name=name))
        if not self.config_store.get('ownership', 'creator'):
            name = self.config_store.get('user', 'creator_name')
            if name:
                self.config_store.set('ownership', 'creator', name)
        self.config_store.remove_section('user')

    def data_form(self):
        widgets = {}
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        scrollarea.setWidgetResizable(True)
        form = QtWidgets.QWidget()
        form.setLayout(FormLayout())
        # creator
        widgets['creator'] = SingleLineEdit(
            'creator', spell_check=True, multi_string=True,
            length_check=ImageMetadata.max_bytes('creator'))
        widgets['creator'].setToolTip('<p>' + translate(
            'OwnerTab',
            'Enter the name of the person that created this image.') + '</p>')
        form.layout().addRow(translate(
            'OwnerTab', 'Creator'), widgets['creator'])
        # creator title
        widgets['creator_title'] = SingleLineEdit(
            'creator_title', spell_check=True, multi_string=True,
            length_check=ImageMetadata.max_bytes('creator_title'))
        widgets['creator_title'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the job title of the person listed in the'
            ' Creator field.') + '</p>')
        form.layout().addRow(translate(
            'OwnerTab', "Creator's Jobtitle"), widgets['creator_title'])
        # credit line
        widgets['credit_line'] = SingleLineEdit(
            'credit_line', spell_check=True,
            length_check=ImageMetadata.max_bytes('credit_line'))
        widgets['credit_line'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter who should be credited when this image is'
            ' published.') +'</p>')
        form.layout().addRow(translate(
            'OwnerTab', 'Credit Line'), widgets['credit_line'])
        # copyright
        widgets['copyright'] = LangAltWidget(
            'copyright', multi_line=False, spell_check=True,
            length_check=ImageMetadata.max_bytes('copyright'))
        widgets['copyright'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter a notice on the current owner of the'
            ' copyright for this image, such as "©2008 Jane Doe".') + '</p>')
        form.layout().addRow(translate(
            'OwnerTab', 'Copyright Notice'), widgets['copyright'])
        ## usage information
        rights_group = QtWidgets.QGroupBox()
        rights_group.setLayout(FormLayout())
        # usage terms
        widgets['rights/UsageTerms'] = LangAltWidget(
            'rights/UsageTerms', multi_line=False, spell_check=True)
        widgets['rights/UsageTerms'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter instructions on how this image can legally'
            ' be used.') + '</p>')
        rights_group.layout().addRow(translate(
            'OwnerTab', 'Usage Terms'), widgets['rights/UsageTerms'])
        # web statement of rights
        widgets['rights/WebStatement'] = RightsDropDown('rights/WebStatement')
        rights_group.layout().addRow(translate(
            'OwnerTab', 'Web Statement'), widgets['rights/WebStatement'])
        # licensor URL
        widgets['rights/LicensorURL'] = SingleLineEdit('rights/LicensorURL')
        widgets['rights/LicensorURL'].setToolTip('<p>' + translate(
            'OwnerTab', 'URL for a licensor web page. May facilitate licensing'
            ' of the image.') + '</p>')
        rights_group.layout().addRow(translate(
            'OwnerTab', 'Licensor URL'), widgets['rights/LicensorURL'])
        form.layout().addRow(translate(
            'OwnerTab', 'Rights'), rights_group)
        # special instructions
        widgets['instructions'] = SingleLineEdit(
            'instructions', spell_check=True,
            length_check=ImageMetadata.max_bytes('instructions'))
        widgets['instructions'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter information about embargoes, or other'
            ' restrictions not covered by the Rights Usage Terms field.'
            ) + '</p>')
        form.layout().addRow(translate(
            'OwnerTab', 'Instructions'), widgets['instructions'])
        ## creator contact information
        contact_group = QtWidgets.QGroupBox()
        contact_group.setLayout(FormLayout())
        # email addresses
        widgets['contact_info/CiEmailWork'] = SingleLineEdit(
            'contact_info/CiEmailWork')
        widgets['contact_info/CiEmailWork'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the work email address(es) for the person'
            ' that created this image, such as name@domain.com.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Email(s)'), widgets['contact_info/CiEmailWork'])
        # URLs
        widgets['contact_info/CiUrlWork'] = SingleLineEdit(
            'contact_info/CiUrlWork')
        widgets['contact_info/CiUrlWork'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the work Web URL(s) for the person that'
            ' created this image, such as http://www.domain.com/.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Web URL(s)'), widgets['contact_info/CiUrlWork'])
        # phone numbers
        widgets['contact_info/CiTelWork'] = SingleLineEdit(
            'contact_info/CiTelWork')
        widgets['contact_info/CiTelWork'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the work phone number(s) for the person'
            ' that created this image, using the international format,'
            ' such as +1 (123) 456789.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Phone(s)'), widgets['contact_info/CiTelWork'])
        # address
        widgets['contact_info/CiAdrExtadr'] = MultiLineEdit(
            'contact_info/CiAdrExtadr',
            length_check=ImageMetadata.max_bytes('contact_info'),
            spell_check=True)
        widgets['contact_info/CiAdrExtadr'].setToolTip('<p>' + translate(
            'OwnerTab',
            'Enter address for the person that created this image.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Address'), widgets['contact_info/CiAdrExtadr'])
        # city
        widgets['contact_info/CiAdrCity'] = SingleLineEdit(
            'contact_info/CiAdrCity', spell_check=True)
        widgets['contact_info/CiAdrCity'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the city for the address of the person'
            ' that created this image.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'City'), widgets['contact_info/CiAdrCity'])
        # postcode
        widgets['contact_info/CiAdrPcode'] = SingleLineEdit(
            'contact_info/CiAdrPcode')
        widgets['contact_info/CiAdrPcode'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the postal code for the address of the person'
            ' that created this image.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Postal Code'), widgets['contact_info/CiAdrPcode'])
        # region
        widgets['contact_info/CiAdrRegion'] = SingleLineEdit(
            'contact_info/CiAdrRegion', spell_check=True)
        widgets['contact_info/CiAdrRegion'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the state for the address of the person'
            ' that created this image.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'State/Province'), widgets['contact_info/CiAdrRegion'])
        # country
        widgets['contact_info/CiAdrCtry'] = SingleLineEdit(
            'contact_info/CiAdrCtry', spell_check=True)
        widgets['contact_info/CiAdrCtry'].setToolTip('<p>' + translate(
            'OwnerTab', 'Enter the country name for the address of the person'
            ' that created this image.') + '</p>')
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Country'), widgets['contact_info/CiAdrCtry'])
        form.layout().addRow(Label(translate(
            'OwnerTab', 'Creator Contact Information'), lines=3), contact_group)
        scrollarea.setWidget(form)
        return scrollarea, widgets

    def set_enabled(self, enabled):
        for widget in self.enableable:
            widget.setEnabled(enabled)

    def refresh(self):
        self.new_selection(self.image_list.get_selected_images())

    def do_not_close(self):
        return False

    @QtSlot(str, object)
    @catch_all
    def new_value(self, key, value):
        images = self.image_list.get_selected_images()
        for image in images:
            self._set_value(image, key, value)
        self._update_widget(key, images)

    def _update_widget(self, key, images):
        if not images:
            return
        values = []
        for image in images:
            value = self._get_value(image, key)
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets[key].set_multiple(choices=filter(None, values))
        else:
            self.widgets[key].set_value(values[0])

    @QtSlot()
    @catch_all
    def init_template(self):
        template = {}
        for image in self.image_list.get_selected_images():
            date_taken = image.metadata.date_taken
            if date_taken is None:
                date_taken = datetime.now()
            else:
                date_taken = date_taken['datetime']
            year = str(date_taken.year)
            for key in self.widgets:
                value = self._get_value(image, key)
                if not value:
                    continue
                if isinstance(value, dict):
                    # langalt copyright
                    value = dict(value)
                    for k in value:
                        if year in value[k]:
                            value[k] = value[k].replace(year, '%Y')
                else:
                    value = str(value)
                    if year in value:
                        value = value.replace(year, '%Y')
                template[key] = value
        # let user edit results
        self._edit_template(template)

    @QtSlot()
    @catch_all
    def edit_template(self):
        # read config
        template = {}
        for key in self.widgets:
            template[key] = self.config_store.get('ownership', key)
        # do dialog
        self._edit_template(template)

    def _edit_template(self, template):
        dialog = QtWidgets.QDialog(parent=self)
        width = width_for_text(dialog, 'x' * 120)
        dialog.setFixedSize(min(width, self.window().width()),
                            min(width * 3 // 4, self.window().height()))
        dialog.setWindowTitle(
            translate('OwnerTab', 'Photini: ownership template'))
        dialog.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        form, widgets = self.data_form()
        widgets['copyright'].setToolTip(
            widgets['copyright'].toolTip() + '<p>' + translate(
                'OwnerTab',
                'Use %Y to insert the year the photograph was taken.') + '</p>')
        # initialise values
        for key in widgets:
            if key in template:
                widgets[key].set_value(template[key])
            else:
                widgets[key].set_value(None)
        dialog.layout().addWidget(form)
        # apply & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if execute(dialog) != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.config_store.remove_section('ownership')
        for key in widgets:
            value = widgets[key].get_value()
            if value:
                self.config_store.set('ownership', key, value)

    @QtSlot()
    @catch_all
    def apply_template(self):
        template = {}
        for key in self.widgets:
            value = self.config_store.get('ownership', key)
            if value:
                template[key] = value
        images = self.image_list.get_selected_images()
        for image in images:
            date_taken = image.metadata.date_taken
            if date_taken is None:
                date_taken = datetime.now()
            else:
                date_taken = date_taken['datetime']
            for key in template:
                value = template[key]
                if isinstance(value, dict):
                    # langalt copyright
                    for k in value:
                        value[k] = date_taken.strftime(value[k])
                else:
                    value = date_taken.strftime(value)
                self._set_value(image, key, value)
        for key in template:
            self._update_widget(key, images)

    def _set_value(self, image, key, value):
        if '/' in key:
            key, sep, member = key.partition('/')
            info = dict(getattr(image.metadata, key) or {})
            info[member] = value
            setattr(image.metadata, key, info)
        else:
            setattr(image.metadata, key, value)

    def _get_value(self, image, key):
        if '/' in key:
            key, sep, member = key.partition('/')
            info = getattr(image.metadata, key)
            if info:
                return info[member]
            return None
        return getattr(image.metadata, key)

    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.set_enabled(False)
            return
        for key in self.widgets:
            self._update_widget(key, selection)
        self.set_enabled(True)
