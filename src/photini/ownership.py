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

from __future__ import unicode_literals

from datetime import datetime
import logging

from photini.filemetadata import ImageMetadata
from photini.pyqt import (
    catch_all, ComboBox, execute, MultiLineEdit, multiple_values, Qt, QtCore,
    QtGui, QtGui2, QtSignal, QtSlot, QtWidgets, SingleLineEdit, width_for_text)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class RightsDropDown(ComboBox):
    editingFinished = QtSignal()

    def __init__(self):
        super(RightsDropDown, self).__init__()
        self.config_store = QtWidgets.QApplication.instance().config_store
        # list of known licences
        licences = [
            (translate('OwnerTab', 'All rights reserved'), ''),
            (translate('OwnerTab', 'Attribution 4.0 (CC BY 4.0)'),
             'https://creativecommons.org/licenses/by/4.0/'),
            (translate(
                'OwnerTab', 'Attribution-ShareAlike 4.0 (CC BY-SA 4.0)'),
             'https://creativecommons.org/licenses/by-sa/4.0/'),
            (translate(
                'OwnerTab', 'Attribution-NonCommercial 4.0 (CC BY-NC 4.0)'),
             'https://creativecommons.org/licenses/by-nc/4.0/'),
            (translate(
                'OwnerTab',
                'Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)'),
             'https://creativecommons.org/licenses/by-nc-sa/4.0/'),
            (translate(
                'OwnerTab',
                'Attribution-NoDerivatives 4.0 (CC BY-ND 4.0)'),
             'https://creativecommons.org/licenses/by-nd/4.0/'),
            (translate(
                'OwnerTab',
                'Attribution-NonCommercial-NoDerivatives 4.0 (CC BY-NC-ND 4.0)'),
             'https://creativecommons.org/licenses/by-nc-nd/4.0/'),
            (translate(
                'OwnerTab',
                'CC0 1.0 Universal (CC0 1.0) Public Domain Dedication'),
             'https://creativecommons.org/publicdomain/zero/1.0/'),
            (translate(
                'OwnerTab', 'Public Domain Mark 1.0'),
             'https://creativecommons.org/publicdomain/mark/1.0/'),
            ]
        # add user defined licences
        licences += self.config_store.get('ownership', 'licences', [])
        # set up widget
        for name, value in licences:
            self.addItem(name, value)
        self.addItem(translate('OwnerTab', '<new>'))
        self.addItem(multiple_values())
        self.setItemData(self.count() - 1, '<multiple>', Qt.UserRole - 1)
        self.currentIndexChanged.connect(self.index_changed)
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.set_dropdown_width()
        self.old_idx = 0

    @QtSlot(int)
    @catch_all
    def index_changed(self, idx):
        if idx < self.count() - 2:
            # normal item selection
            self.editingFinished.emit()
            return
        # add new licence
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self.old_idx)
        self.blockSignals(blocked)
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('OwnerTab', 'Define new licence'))
        dialog.setLayout(QtWidgets.QFormLayout())
        name = SingleLineEdit(spell_check=True)
        dialog.layout().addRow(translate('OwnerTab', 'Name'), name)
        url = SingleLineEdit()
        dialog.layout().addRow(translate('OwnerTab', 'URL'), url)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if execute(dialog) != QtWidgets.QDialog.Accepted:
            return
        name = name.toPlainText()
        url = url.toPlainText()
        if not name and url:
            return
        licences = self.config_store.get('ownership', 'licences', [])
        licences.append((name, url))
        self.config_store.set('ownership', 'licences', licences)
        self.insertItem(idx, name, url)
        self.set_value(url)
        self.editingFinished.emit()

    @QtSlot(QtGui.QContextMenuEvent)
    @catch_all
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        for n in range(1, self.count() - 2):
            action = QtGui2.QAction(
                translate('OwnerTab',
                          'Open link to "{}"').format(self.itemText(n)),
                parent=self)
            action.setData(self.itemData(n))
            menu.addAction(action)
        action = execute(menu, event.globalPos())
        if not action:
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(action.data()))

    def set_value(self, value):
        blocked = self.blockSignals(True)
        if value:
            idx = self.findData(value)
            if idx < 0:
                idx = self.count() - 2
                self.insertItem(idx, value, value)
        else:
            idx = 0
        self.setCurrentIndex(idx)
        self.old_idx = idx
        self.blockSignals(blocked)

    def get_value(self):
        return self.itemData(self.currentIndex())

    def is_multiple(self):
        return self.currentIndex() == self.count() - 1

    def set_multiple(self, choices=[]):
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self.count() - 1)
        self.blockSignals(blocked)


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
            self.widgets[key].editingFinished.connect(
                getattr(self, 'new_' + key))
        self.layout().addWidget(form)
        ## buttons
        buttons = QtWidgets.QVBoxLayout()
        buttons.addStretch(1)
        edit_template = QtWidgets.QPushButton(
            translate('OwnerTab', 'Edit\ntemplate'))
        edit_template.clicked.connect(self.edit_template)
        buttons.addWidget(edit_template)
        apply_template = QtWidgets.QPushButton(
            translate('OwnerTab', 'Apply\ntemplate'))
        apply_template.clicked.connect(self.apply_template)
        self.enableable.append(apply_template)
        buttons.addWidget(apply_template)
        self.layout().addLayout(buttons)
        # disable data entry until an image is selected
        self.set_enabled(False)

    def data_form(self):
        widgets = {}
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scrollarea.setWidgetResizable(True)
        form = QtWidgets.QWidget()
        form.setLayout(QtWidgets.QFormLayout())
        # creator
        widgets['creator'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('creator'),
            spell_check=True, multi_string=True)
        widgets['creator'].setToolTip(translate(
            'OwnerTab',
            'Enter the name of the person that created this image.'))
        form.layout().addRow(translate(
            'OwnerTab', 'Creator'), widgets['creator'])
        # creator title
        widgets['creator_title'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('creator_title'),
            spell_check=True, multi_string=True)
        widgets['creator_title'].setToolTip(translate(
            'OwnerTab',
            'Enter the job title of the person listed in the Creator field.'))
        form.layout().addRow(translate(
            'OwnerTab', "Creator's Jobtitle"), widgets['creator_title'])
        # credit line
        widgets['credit_line'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('credit_line'),
            spell_check=True)
        widgets['credit_line'].setToolTip(translate(
            'OwnerTab',
            'Enter who should be credited when this image is published.'))
        form.layout().addRow(translate(
            'OwnerTab', 'Credit Line'), widgets['credit_line'])
        # copyright
        widgets['copyright'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('copyright'), spell_check=True)
        widgets['copyright'].setToolTip(translate(
            'OwnerTab', 'Enter a notice on the current owner of the'
            ' copyright for this image, such as "©2008 Jane Doe".'))
        form.layout().addRow(translate(
            'OwnerTab', 'Copyright Notice'), widgets['copyright'])
        ## contact information
        rights_group = QtWidgets.QGroupBox()
        rights_group.setLayout(QtWidgets.QFormLayout())
        # usage terms
        widgets['rights_UsageTerms'] = SingleLineEdit(spell_check=True)
        widgets['rights_UsageTerms'].setToolTip(translate(
            'OwnerTab',
            'Enter instructions on how this image can legally be used.'))
        rights_group.layout().addRow(translate(
            'OwnerTab', 'Usage Terms'), widgets['rights_UsageTerms'])
        # web statement of rights
        widgets['rights_WebStatement'] = RightsDropDown()
        rights_group.layout().addRow(translate(
            'OwnerTab', 'Web Statement'), widgets['rights_WebStatement'])
        # licensor URL
        widgets['rights_LicensorURL'] = SingleLineEdit()
        widgets['rights_LicensorURL'].setToolTip(translate(
            'OwnerTab', 'URL for a licensor web page. May facilitate licensing'
            ' of the image.'))
        rights_group.layout().addRow(translate(
            'OwnerTab', 'Licensor URL'), widgets['rights_LicensorURL'])
        form.layout().addRow(translate(
            'OwnerTab', 'Rights'), rights_group)
        # special instructions
        widgets['instructions'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('instructions'),
            spell_check=True)
        widgets['instructions'].setToolTip(translate(
            'OwnerTab', 'Enter information about embargoes, or other'
            ' restrictions not covered by the Rights Usage Terms field.'))
        form.layout().addRow(translate(
            'OwnerTab', 'Instructions'), widgets['instructions'])
        ## contact information
        contact_group = QtWidgets.QGroupBox()
        contact_group.setLayout(QtWidgets.QFormLayout())
        # email addresses
        widgets['CiEmailWork'] = SingleLineEdit()
        widgets['CiEmailWork'].setToolTip(translate(
            'OwnerTab', 'Enter the work email address(es) for the person'
            ' that created this image, such as name@domain.com.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Email(s)'), widgets['CiEmailWork'])
        # URLs
        widgets['CiUrlWork'] = SingleLineEdit()
        widgets['CiUrlWork'].setToolTip(translate(
            'OwnerTab', 'Enter the work Web URL(s) for the person'
            ' that created this image, such as http://www.domain.com/.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Web URL(s)'), widgets['CiUrlWork'])
        # phone numbers
        widgets['CiTelWork'] = SingleLineEdit()
        widgets['CiTelWork'].setToolTip(translate(
            'OwnerTab', 'Enter the work phone number(s) for the person'
            ' that created this image, using the international format,'
            ' such as +1 (123) 456789.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Phone(s)'), widgets['CiTelWork'])
        # address
        widgets['CiAdrExtadr'] = MultiLineEdit(
            length_check=ImageMetadata.max_bytes('contact_info'),
            spell_check=True)
        widgets['CiAdrExtadr'].setToolTip(translate(
            'OwnerTab',
            'Enter address for the person that created this image.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Address'), widgets['CiAdrExtadr'])
        # city
        widgets['CiAdrCity'] = SingleLineEdit(spell_check=True)
        widgets['CiAdrCity'].setToolTip(translate(
            'OwnerTab', 'Enter the city for the address of the person'
            ' that created this image.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'City'), widgets['CiAdrCity'])
        # postcode
        widgets['CiAdrPcode'] = SingleLineEdit()
        widgets['CiAdrPcode'].setToolTip(translate(
            'OwnerTab', 'Enter the postal code for the address of the person'
            ' that created this image.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Postal Code'), widgets['CiAdrPcode'])
        # region
        widgets['CiAdrRegion'] = SingleLineEdit(spell_check=True)
        widgets['CiAdrRegion'].setToolTip(translate(
            'OwnerTab', 'Enter the state for the address of the person'
            ' that created this image.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'State/Province'), widgets['CiAdrRegion'])
        # country
        widgets['CiAdrCtry'] = SingleLineEdit(spell_check=True)
        widgets['CiAdrCtry'].setToolTip(translate(
            'OwnerTab', 'Enter the country name for the address of the person'
            ' that created this image.'))
        contact_group.layout().addRow(translate(
            'OwnerTab', 'Country'), widgets['CiAdrCtry'])
        form.layout().addRow(translate(
            'OwnerTab', 'Contact<br>Information'), contact_group)
        scrollarea.setWidget(form)
        return scrollarea, widgets

    def set_enabled(self, enabled):
        for widget in self.enableable:
            widget.setEnabled(enabled)

    def refresh(self):
        self.new_selection(self.image_list.get_selected_images())

    def do_not_close(self):
        return False

    @QtSlot()
    @catch_all
    def new_creator(self):
        self._new_value('creator')

    @QtSlot()
    @catch_all
    def new_creator_title(self):
        self._new_value('creator_title')

    @QtSlot()
    @catch_all
    def new_credit_line(self):
        self._new_value('credit_line')

    @QtSlot()
    @catch_all
    def new_copyright(self):
        self._new_value('copyright')

    @QtSlot()
    @catch_all
    def new_rights_UsageTerms(self):
        self._new_value('rights_UsageTerms')

    @QtSlot()
    @catch_all
    def new_rights_LicensorURL(self):
        self._new_value('rights_LicensorURL')

    @QtSlot()
    @catch_all
    def new_rights_WebStatement(self):
        self._new_value('rights_WebStatement')

    @QtSlot()
    @catch_all
    def new_instructions(self):
        self._new_value('instructions')

    @QtSlot()
    @catch_all
    def new_CiEmailWork(self):
        self._new_value('CiEmailWork')

    @QtSlot()
    @catch_all
    def new_CiUrlWork(self):
        self._new_value('CiUrlWork')

    @QtSlot()
    @catch_all
    def new_CiTelWork(self):
        self._new_value('CiTelWork')

    @QtSlot()
    @catch_all
    def new_CiAdrExtadr(self):
        self._new_value('CiAdrExtadr')

    @QtSlot()
    @catch_all
    def new_CiAdrCity(self):
        self._new_value('CiAdrCity')

    @QtSlot()
    @catch_all
    def new_CiAdrPcode(self):
        self._new_value('CiAdrPcode')

    @QtSlot()
    @catch_all
    def new_CiAdrRegion(self):
        self._new_value('CiAdrRegion')

    @QtSlot()
    @catch_all
    def new_CiAdrCtry(self):
        self._new_value('CiAdrCtry')

    def _new_value(self, key):
        images = self.image_list.get_selected_images()
        if not self.widgets[key].is_multiple():
            value = self.widgets[key].get_value()
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
    def edit_template(self):
        dialog = QtWidgets.QDialog(parent=self)
        width = width_for_text(dialog, 'x' * 120)
        dialog.setFixedSize(min(width, self.window().width()),
                            min(width * 3 // 4, self.window().height()))
        dialog.setWindowTitle(self.tr('Photini: ownership template'))
        dialog.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        form, widgets = self.data_form()
        widgets['copyright'].setToolTip(
            widgets['copyright'].toolTip() + ' ' +
            translate('OwnerTab',
                      'Use %Y to insert the year the photograph was taken.'))
        # move config usageterms to rights_UsageTerms
        value = self.config_store.get('ownership', 'usageterms')
        if value:
            self.config_store.set('ownership', 'rights_UsageTerms', value)
            self.config_store.delete('ownership', 'usageterms')
        # read config
        for key in widgets:
            value = self.config_store.get('ownership', key)
            if key == 'copyright' and not value:
                name = self.config_store.get('user', 'copyright_name') or ''
                text = (self.config_store.get('user', 'copyright_text') or
                        translate('DescriptiveTab', 'Copyright ©{year} {name}.'
                                  ' All rights reserved.'))
                value = text.format(year='%Y', name=name)
            elif key == 'creator' and not value:
                value = self.config_store.get('user', 'creator_name')
            widgets[key].set_value(value)
        dialog.layout().addWidget(form)
        # apply & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if execute(dialog) != QtWidgets.QDialog.Accepted:
            return
        for key in widgets:
            value = widgets[key].get_value()
            if value:
                self.config_store.set('ownership', key, value)
            else:
                self.config_store.delete('ownership', key)

    @QtSlot()
    @catch_all
    def apply_template(self):
        value = {}
        for key in self.widgets:
            text = self.config_store.get('ownership', key)
            if text:
                value[key] = text
        images = self.image_list.get_selected_images()
        for image in images:
            date_taken = image.metadata.date_taken
            if date_taken is None:
                date_taken = datetime.now()
            else:
                date_taken = date_taken['datetime']
            for key in value:
                self._set_value(image, key, date_taken.strftime(value[key]))
        for key in value:
            self._update_widget(key, images)

    def _set_value(self, image, key, value):
        if key.startswith('Ci'):
            info = dict(image.metadata.contact_info or {})
            info[key] = value
            image.metadata.contact_info = info
        elif key.startswith('rights_'):
            key = key.split('_')[1]
            info = dict(image.metadata.rights or {})
            info[key] = value
            image.metadata.rights = info
        else:
            setattr(image.metadata, key, value)

    def _get_value(self, image, key):
        if key.startswith('Ci'):
            info = image.metadata.contact_info
            if info:
                return info[key]
            return None
        if key.startswith('rights_'):
            info = image.metadata.rights
            if info:
                key = key.split('_')[1]
                return info[key]
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
