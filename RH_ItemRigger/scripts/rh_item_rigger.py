"""
ItemRigger

Author: Randall Hess randall.hess@gmail.com
License: GNU General Public License v3.0
"""


import os
import re
import traceback

import maya
import maya.cmds as cmds
from functools import partial
from maya import OpenMayaUI as OpenMayaUI
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
import maya.OpenMaya as openMaya
from maya.OpenMayaUI import MQtUtil
import pymel.core as pymel

QT_VERSION = "none"

try:
	from cStringIO import StringIO
	from PySide.QtGui  import * 
	from PySide.QtCore import *
	from PySide import QtGui
	import shiboken
	from shiboken import wrapInstance
	QT_VERSION = "pyside"	
except:
	try:
		from cStringIO import StringIO
		from PySide2.QtGui     import * 
		from PySide2.QtCore    import *
		from PySide2.QtWidgets import *
		from PySide2 import QtGui		
		import shiboken2
		from shiboken2 import wrapInstance
		QT_VERSION = "pyside2"
	except:
		print "PySide(2) and PyQt4 not found"

import rh_maya

AUTHOR = 'Randall Hess'
WINDOW_TITLE = 'RH Item Rigger'
WINDOW_VERSION = 0.1
WINDOW_NAME = 'item_rigger_window'
WINDOW_DOCK = 'item_rigger_dock'
ICON_PATH = pymel.util.getEnv('RH_ICONS_PATH')
HEADER_LOGO = ICON_PATH + '/header_logo.png'

MAYA2014 = 201400
MAYA2015 = 201500
MAYA2016 = 201600
MAYA2016_5 = 201650
MAYA2017 = 201700
MAYA2017 = 201800
MAYA2017 = 201900

# SET YOUR PROJECT ART PATH HERE
PROJECT_ART_PATH = 'D:/Project/Art/'


'''
VERSION 0.5
ItemRigger > V 1.5
Updated to handle multiple materials per mesh
No longer validating mesh material group parents, we'll see how this goes
Some function cleanup to prevent big gets from happening many times

VERSION 0.4
Update to be more item general,
Rename all weapon attributes to Item
In preparation for Vehicle Rigging

VERSION 0.3
Added support for flagging meshes as static or deformable
Setting deformable by default as it will work in engine via SetMasterPose
When Adding a mesh back it will fill in the bone and control objects if they still exist

VERSION 0.2
Added support for flagging meshes as attachment
Exporting flagged attached meshes as separate mesh exports
Better Export output and progress bar
Renaming Prompting
'''


class ClickableLabel(QAbstractButton):

	clicked = Signal(str)

	def __init__(self, width, height, color, name, pixmap=None, ro=None, pressed=None, disabled=None, parent=None):
		super(ClickableLabel, self).__init__(parent)
		# set up the button states
		self.pixmap = pixmap
		self.pixmap_hover = None
		self.pixmap_pressed = None
		self.pixmap_disabled = None
		if ro:
			self.pixmap_hover = ro
		if pressed:
			self.pixmap_pressed = pressed
		if disabled:
			self.pixmap_disabled = disabled

		self.is_active = False
		self.is_disabled = False
		self.pressed.connect(self.update)
		self.released.connect(self.update)

	def paintEvent(self, event):
		if self.is_disabled:
			if self.pixmap_disabled:
				pix = self.pixmap_disabled

		elif self.is_active:
			if self.pixmap_pressed:
				pix = self.pixmap_pressed
			if self.isDown():
				if self.pixmap_pressed:
					if self.is_active:
						pix = self.pixmap			

		else:
			pix = self.pixmap_hover if self.underMouse() else self.pixmap
			if self.isDown():
				if self.pixmap_pressed:
					if self.is_active:
						pix = self.pixmap
					else:
						pix = self.pixmap_pressed
			if self.is_disabled:
				if self.pixmap_disabled:
					self.pixmap = self.pixmap_disabled

		painter = QPainter(self)
		painter.drawPixmap(event.rect(), pix)

	def sizeHint(self):
		return self.pixmap.size()

	def enterEvent(self, event):
		self.update()

	def leaveEvent(self, event):
		self.update()

	def mousePressEvent(self, event):
		self.update()
		self.clicked.emit(self.objectName())
	

class ItemRigger(MayaQWidgetDockableMixin, QDialog):
	toolName = WINDOW_TITLE

	def __init__(self, parent = None):
		## Delete any previous instances that is detected. Do this before parenting self to main window!
		self.deleteInstances()

		super(self.__class__, self).__init__(parent = parent)
		mayaMainWindowPtr = OpenMayaUI.MQtUtil.mainWindow() 		
		self.mayaMainWindow = wrapInstance(long(mayaMainWindowPtr), QMainWindow)

		# Setup window's properties	
		# Make this unique enough if using it to clear previous instance!
		self.setObjectName(self.__class__.toolName)		

		# initialize all variables
		self.initial_setup = True
		self._init_variables_()
		
		# Populate the Item Variables
		self._init_item_()			

		# create the UI base		
		self.setupUi(inital=True)		

		# Update the initial UI
		self.update_ui(initial=True)

		QMetaObject.connectSlotsByName(self)
		self.setWindowTitle( '{0} {1}'.format( WINDOW_TITLE, WINDOW_VERSION) )
		self.setWindowFlags( Qt.Tool )
		self.setAttribute( Qt.WA_DeleteOnClose )
		self.resize(200, 200)

		self.show(dockable = True, floating =False, area ='right', width=200)
		self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
		self.setMinimumWidth(380)
		self.setMaximumWidth(380)
		self.raise_()
	
		self.initial_setup = False		


	def deleteInstances(self):
		"""
		Handle proper clean up of removing the dock control widget

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/3/2014 2:40:06 PM
		"""

		mayaMainWindowPtr = OpenMayaUI.MQtUtil.mainWindow() 
		mayaMainWindow = wrapInstance(long(mayaMainWindowPtr), QMainWindow) # Important that it's QMainWindow, and not QWidget/QDialog

		# Go through main window's children to find any previous instances
		for obj in mayaMainWindow.children():		
			if type( obj ) == maya.app.general.mayaMixin.MayaQDockWidget:
				if obj.widget():
					if obj.widget().objectName() == self.__class__.toolName: # Compare object names
						# If they share the same name then remove it
						print 'Deleting instance {0}'.format(obj.widget().objectName())
						mayaMainWindow.removeDockWidget(obj) # This will remove from right-click menu, but won't actually delete it! ( still under mainWindow.children() )
						# Delete it for good
						obj.setParent(None)
						obj.deleteLater()
						break



	def closeEvent(self, event):
		"""
		CloseEvent

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/3/2014 4:18:15 PM
		"""		

		try:
			QtGui.closeEvent(self, event)
		except:
			pass			
		event.accept()


	def keyPressEvent(self, event):
		"""
		KeyPressEvent

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/3/2014 4:18:41 PM
		"""

		if event.type() == QEvent.KeyPress:
			pass
		else:
			pass


	def eventFilter(self, widget, event):
		"""
		Monitor the events

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/3/2014 4:18:59 PM
		"""		

		try:
			event_type = event.type()
		except:
			try:
				return QWidget.eventFilter( self, widget, event )
			except:
				return

		if event.type() == QEvent.Wheel:
			if isinstance( widget, QSpinBox ):
				event.ignore()
				return True

		if isinstance( widget, QLineEdit ):
			if isinstance( widget.parent(), QSpinBox ):				
				if event.type() == Qt.ClickFocus:					
					return True
				if event.type() == QEvent.MouseButtonPress:					
					return True

		if isinstance( widget, QTableView ):
			if event.type() == QEvent.KeyPress:				
				if event.key() == Qt.Key_P:
					pass					

		if isinstance( widget, QCheckBox ):
			if event.type() == QEvent.FocusIn:
				widget.selectAll()				
				return False

		if isinstance( widget, QSpinBox ):
			if event.type() == QEvent.FocusIn:				
				widget.selectAll()				
				return False

		if isinstance( widget, QLineEdit ):
			if event.type() == QEvent.FocusIn:										
				return False
			if event.type() == QEvent.KeyPress:
				key_val=None
				try:
					key_val=chr(event.key())
				except:
					pass				
				if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:					
					self.on_update_item_named(key=key_val, delete=True)
				else:					
					self.on_update_item_named(key=key_val)
				return False


		try:
			return QWidget.eventFilter( self, widget, event )
		except:
			pass
		
		
	def refresh_update_ui( self ):
		"""
		Refresh the UI from a callback
	
		*Arguments:*
			* ``None`` 
	
		*Keyword Arguments:*
			* ``None`` 
	
		*Returns:*
			* ``None`` 
	
		*Author:*
		* randall.hess, randall.hess@gmail.com, 2/11/2015 2:03:46 PM
		"""
	
		#self.__init__variables()
		if not self.ignore_callback:
			run()		


	def dockCloseEventTriggered(self):
		"""
		If it's floating or docked, this will run and delete it self when it closes.
		You can choose not to delete it here so that you can still re-open it through the right-click menu, but do disable any callbacks/timers that will eat memory		

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/3/2014 4:19:20 PM
		"""

		self.deleteInstances()


	def get_maya_colors(self):
		"""
		Get maya colors to rgb

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/29/2014 5:50:37 PM
		"""

		def get_rgb_color(color):				
			rgb = []
			for col in maya_color:
				if col == 1.0:
					c = 255
				else:
					c = col*255
				rgb.append(c)
			return rgb		

		self.color_indexes = {}
		rgb_colors = []
		color_indices = [1,2,3,11,24,21,12,10,25,4,13,20,8,30,9,5,6,18,15,29,28,7,27,19,23,26,14,17,22,16]
		for color in range(1, 30):
			maya_color = cmds.colorIndex(color, q=True, hsv=False)			
			rgb =get_rgb_color(maya_color)
			rgb_colors.append(rgb)
		return rgb_colors


	def _init_variables_(self):
		"""
		Initialize all of the item variables

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/20/2014 10:22:24 AM
		"""

		# Item UI variables
		self.selected_asset = None
		self.edit_mode = False
		self.settings_on = False
		self.named_on = False
		self.edit_on = False
		self.meshes_on = False
		self.first_toggle = True
		

		# Item Variables
		self.item_name = None		
		self.item_node = None
		self.item_base_mesh = None
		self.item_mesh_group = None
		self.item_material_groups = None
		self.item_materials = None
		self.item_type = 'Weapon'		
		self.item_type_attr = 'rh_item'
		self.unassigned_group = None
		self.item_material_group_meshes = []
		self.item_meshes = []
		self.item_bones = []
		self.item_controls = []
		self.all_item_nodes = []
		self.unassigned_objects = []
		self.item_attachments = []
		self.item_attachment_names = []
		self.duplicate_names = []
		self.selected_item_name = None
		self.is_resetting_text = False

		# active UI elements
		self.active_rename_layout = False
		self.active_item_name_layout = False
		self.active_edit_mode_layout = False
		self.active_edit_layout = False
		self.active_unassigned_layout = False
		self.active_utility_layout = False
		self.active_export_layout = False
		self.active_no_export_layout = False

		self.active_add_bone_text = False
		self.active_sel_bone_combo = False
		self.active_rename_pushbutton = False		

		# Item Temp Bones
		self.temp_bone = None
		self.temp_mesh = None
		self.temp_materials = None
		self.temp_control = None

		self.keep_skinning = False
		self.attachment_row_index = None

		# store ui name lists
		self.add_bone_combo_names = []
		self.parent_ctrl_add_control_names = []
		self.item_base_ctrls = ['weapon_root_anim', 'weapon_root_pivot_offset_anim', 'weapon_root_pivot_anim']
		self.vehicle_base_ctrls = ['main_anim', 'ground_anim', 'frame_anim','anim_root_pivot_offset_anim','anim_root_pivot_anim']

		# color picked combo boxes
		self.parent_ctrl_picked = False
		self.add_bone_picked = True

		self.last_bone_index_added = 0
		self.maya_rgb_colors = self.get_maya_colors()

		self.can_export = True
		self.export_error_message = ''


	def resizeEvent( self, event):
		"""
		Handle the layout when resizing

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/3/2014 4:19:40 PM
		"""

		self.setLayout( self.main_layout )


	def create_rename_item_ui(self):		
		'''
		##### SETTINGS BOX LAYOUT ########
		'''		
		# Text Edit
		self.textEditor= QLineEdit(self)
		self.textEditor.setStyleSheet('''QLineEdit {color: black; background-color: grey }''')
		self.textEditor.setFixedWidth(170)
		self.textEditor.setFixedHeight(30)
		self.textEditor.setPlaceholderText('ItemName')
		self.textEditor.installEventFilter( self )
		self.setFocus()			

		# Accept Rename
		accept_icon = QtGui.QPixmap(ICON_PATH + '/accept.png')
		accept_ro_icon = QtGui.QPixmap(ICON_PATH + '/accept_RO.png')		
		accept_disabled_icon = QtGui.QPixmap(ICON_PATH + '/accept_NOPE.png')
		self.accept_pushButton = ClickableLabel(24, 24, 'red', "pb_accept", pixmap=accept_icon, ro=accept_ro_icon, disabled=accept_disabled_icon)		
		self.accept_pushButton.setToolTip('The name must be at least 4 characters long.\nIt should also not contain invalid characters.')
		self.accept_pushButton.clicked.connect(lambda:self.on_pressed_accept_name())
		self.accept_pushButton.setDisabled(True)

		# Cancel Rename
		cancel_icon = QtGui.QPixmap(ICON_PATH + '/rename_CANCEL.png')		
		cancel_ro_icon = QtGui.QPixmap(ICON_PATH + '/rename_CANCEL_RO.png')		
		self.cancel_pushButton = ClickableLabel(24, 24, 'red', "pb_cancel", pixmap=cancel_icon, ro=cancel_ro_icon)		
		self.cancel_pushButton.setToolTip('Cancel renaming the item')
		self.cancel_pushButton.clicked.connect(lambda:self.on_pressed_cancel_rename())		

		# Label
		label_box = QHBoxLayout()	
		label_box.addWidget(self.textEditor)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.accept_pushButton, 0, 0)
		buttons_box.addWidget(self.cancel_pushButton, 0, 1)
		buttons_box.setSpacing(1)
		buttons_box.setHorizontalSpacing(5)

		# vbox		
		left_v_box = QVBoxLayout()
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(label_box)
		middle_v_box.setAlignment(Qt.AlignCenter)
		right_v_box = QVBoxLayout()		
		right_v_box.addLayout(buttons_box)
		right_v_box.setAlignment(Qt.AlignRight)

		main_box_layout = QHBoxLayout()	
		main_box_layout.setAlignment(Qt.AlignCenter)
		main_box_layout.addLayout(left_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(middle_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(right_v_box)		

		# Vertical Box
		self.settings_vbox = QVBoxLayout()
		self.settings_vbox.addLayout(main_box_layout)

		# GroupBox
		self.settings_groupbox = QGroupBox('Rename Item')
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.settings_groupbox.sizePolicy().hasHeightForWidth())
		self.settings_groupbox.setSizePolicy(sizePolicy)
		self.settings_groupbox.setMinimumSize(QSize(323, 100))		
		self.settings_groupbox.setLayout(self.settings_vbox)

		self.rename_layout = QHBoxLayout()
		self.rename_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.rename_layout.addWidget(self.settings_groupbox)
		self.rename_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))			

		return self.rename_layout

	def create_export_ui(self):
		'''
		##### Export BOX LAYOUT ########
		'''		
		# Name has been Set
		#self.export_label = QLabel()	

		# Label
		#label_box = QHBoxLayout()	
		#label_box.addWidget(self.export_label)

		self.export_pushButton = QPushButton('Export Item')
		self.export_pushButton.setFixedSize( 200, 40 )		
		self.export_pushButton.setObjectName("pb_export")
		self.export_pushButton.pressed.connect(lambda:self.on_pressed_export_item())		
		self.export_pushButton.setToolTip('Export the item')	

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.export_pushButton, 0, 0)		

		# vbox		
		left_v_box = QVBoxLayout()
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(buttons_box)
		middle_v_box.setAlignment(Qt.AlignCenter)
		right_v_box = QVBoxLayout()		
		right_v_box.setAlignment(Qt.AlignRight)

		main_box_layout = QHBoxLayout()	
		main_box_layout.setAlignment(Qt.AlignCenter)
		main_box_layout.addLayout(left_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(middle_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(right_v_box)
		
		# progress bar
		self.prog_box_layout = QHBoxLayout()	
		self.prog_box_layout.setAlignment(Qt.AlignCenter)
		self.export_progress = QProgressBar()
		self.export_progress.setGeometry(200,80,250,20)		
		self.prog_box_layout.addWidget(self.export_progress)
		
		# export output
		self.export_output = QTextEdit()
		self.export_output.sizeHint()
		self.export_output.setReadOnly(True)
		self.export_output.setLineWrapMode(QTextEdit.NoWrap)
		self.export_output.setGeometry(200,300,250,300)	
		output_box = QGridLayout()
		output_box.addWidget(self.export_output, 0, 0)	

		# setup the hbox layout
		self.export_vbox = QVBoxLayout()
		self.export_vbox.addLayout(main_box_layout)
		self.export_vbox.addLayout(self.prog_box_layout)
		self.export_vbox.addLayout(output_box)
		self.export_output.setVisible(False)

		self.export_groupbox = QGroupBox('Export')
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.export_groupbox.sizePolicy().hasHeightForWidth())
		self.export_groupbox.setSizePolicy(sizePolicy)
		self.export_groupbox.setMinimumSize(QSize(323, 100))
		self.export_groupbox.setLayout(self.export_vbox)

		self.export_layout = QHBoxLayout()
		self.export_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.export_layout.addWidget(self.export_groupbox)
		self.export_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))

		return self.export_layout

	def create_no_export_ui(self):
		'''
		##### Export BOX LAYOUT ########
		'''		
		# Name has been Set
		self.no_export_label = QLabel()	

		# Label
		label_box = QHBoxLayout()	
		label_box.addWidget(self.no_export_label)

		# Error List
		self.error_output = QTextEdit()
		self.error_output.sizeHint()
		self.error_output.setReadOnly(True)
		self.error_output.setLineWrapMode(QTextEdit.NoWrap)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.error_output, 0, 0)
		
		# Label
		label_box = QHBoxLayout()
		label_box.addStretch()
		label_box.addWidget(self.no_export_label)
		label_box.addStretch()

		# vbox		
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(buttons_box)
		middle_v_box.setAlignment(Qt.AlignCenter)
	
		main_box_layout = QHBoxLayout()	
		main_box_layout.setAlignment(Qt.AlignCenter)		
		main_box_layout.addSpacing(5)
		main_box_layout.addLayout(middle_v_box)
		main_box_layout.addSpacing(5)
		
		# setup the hbox layout
		no_export_vbox = QVBoxLayout()
		no_export_vbox.addLayout(label_box)
		no_export_vbox.addLayout(main_box_layout)

		no_export_groupbox = QGroupBox('Export Errors')
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(no_export_groupbox.sizePolicy().hasHeightForWidth())
		no_export_groupbox.setSizePolicy(sizePolicy)
		no_export_groupbox.setMinimumSize(QSize(323, 400))		
		no_export_groupbox.setLayout(no_export_vbox)

		self.no_export_layout = QHBoxLayout()
		self.no_export_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.no_export_layout.addWidget(no_export_groupbox)
		self.no_export_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))

		return self.no_export_layout


	def create_item_name_ui(self):
		'''
		##### ITEM NAMED BOX LAYOUT ########
		'''		
		# Name has been Set
		self.item_label = QLabel()

		# Rename the item
		rename_icon = QtGui.QPixmap(ICON_PATH + '/rename.png')		
		rename_ro_icon = QtGui.QPixmap(ICON_PATH + '/rename_RO.png')		
		rename_ro_icon = QtGui.QPixmap(ICON_PATH + '/rename_RO.png')
		rename_disabled_icon = QtGui.QPixmap(ICON_PATH + '/rename_NOPE.png')
		self.rename_pushButton = ClickableLabel(24, 24, 'red', "pb_rename", pixmap=rename_icon, ro=rename_ro_icon, disabled=rename_disabled_icon)		
		self.rename_pushButton.setObjectName("pb_rename")
		self.rename_pushButton.setToolTip('Rename the Item')
		self.rename_pushButton.clicked.connect(lambda:self.on_pressed_rename())

		# Edit the item
		edit_icon = QtGui.QPixmap(ICON_PATH + '/edit.png')		
		edit_ro_icon = QtGui.QPixmap(ICON_PATH + '/edit_RO.png')		
		edit_active_icon = QtGui.QPixmap(ICON_PATH + '/edit_Active.png')
		self.edit_pushButton = ClickableLabel(24, 24, 'red', "pb_edit", pixmap=edit_icon, ro=edit_ro_icon, pressed=edit_active_icon)		
		self.edit_pushButton.setToolTip('Edit the Item')
		self.edit_pushButton.clicked.connect(lambda:self.on_pressed_edit_item())
		self.edit_pushButton.is_active = False

		# Label
		label_box = QHBoxLayout()	
		label_box.addWidget(self.item_label)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.rename_pushButton, 0, 0)
		buttons_box.addWidget(self.edit_pushButton, 0, 1)
		buttons_box.setSpacing(1)
		buttons_box.setHorizontalSpacing(5)

		# vbox		
		left_v_box = QVBoxLayout()
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(label_box)
		middle_v_box.setAlignment(Qt.AlignCenter)
		right_v_box = QVBoxLayout()		
		right_v_box.addLayout(buttons_box)
		right_v_box.setAlignment(Qt.AlignRight)

		main_box_layout = QHBoxLayout()	
		main_box_layout.setAlignment(Qt.AlignCenter)
		main_box_layout.addLayout(left_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(middle_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(right_v_box)			

		# setup the hbox layout
		self.item_named_vbox = QVBoxLayout()
		self.item_named_vbox.addLayout(main_box_layout)

		self.item_named_groupbox = QGroupBox('Item')
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(self.item_named_groupbox.sizePolicy().hasHeightForWidth())
		self.item_named_groupbox.setSizePolicy(sizePolicy)
		self.item_named_groupbox.setMinimumSize(QSize(323, 100))		
		self.item_named_groupbox.setLayout(self.item_named_vbox)

		self.item_name_layout = QHBoxLayout()
		self.item_name_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.item_name_layout.addWidget(self.item_named_groupbox)
		self.item_name_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))

		return self.item_name_layout	


	def create_edit_mode_ui(self):
		'''
		##### ITEM NAMED BOX LAYOUT ########
		'''		
		# Name has been Set
		self.edit_mode_label = QLabel()

		# Edit the item
		edit_icon = QtGui.QPixmap(ICON_PATH + '/edit.png')		
		edit_ro_icon = QtGui.QPixmap(ICON_PATH + '/edit_RO.png')		
		edit_active_icon = QtGui.QPixmap(ICON_PATH + '/edit_Active.png')
		self.edit_mode_pushButton = ClickableLabel(24, 24, 'red', "pb_edit", pixmap=edit_icon, ro=edit_ro_icon, pressed=edit_active_icon)		
		self.edit_mode_pushButton.setToolTip('Edit the Item')
		self.edit_mode_pushButton.clicked.connect(lambda:self.on_pressed_edit_item())
		self.edit_mode_pushButton.is_active = False

		# Label
		label_box = QHBoxLayout()	
		label_box.addWidget(self.edit_mode_label)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.edit_mode_pushButton, 0, 0)
		buttons_box.setSpacing(1)
		buttons_box.setHorizontalSpacing(5)

		# vbox		
		left_v_box = QVBoxLayout()
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(label_box)
		middle_v_box.setAlignment(Qt.AlignCenter)
		right_v_box = QVBoxLayout()		
		right_v_box.addLayout(buttons_box)
		right_v_box.setAlignment(Qt.AlignRight)

		main_box_layout = QHBoxLayout()	
		main_box_layout.setAlignment(Qt.AlignCenter)
		main_box_layout.addLayout(left_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(middle_v_box)
		main_box_layout.addStretch(1)
		main_box_layout.addLayout(right_v_box)		

		self.edit_item_vbox = QVBoxLayout()
		self.edit_item_vbox.addLayout(main_box_layout)		

		edit_mode_groupbox = QGroupBox('Item')
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		sizePolicy.setHeightForWidth(edit_mode_groupbox.sizePolicy().hasHeightForWidth())
		edit_mode_groupbox.setSizePolicy(sizePolicy)
		edit_mode_groupbox.setMinimumSize(QSize(323, 100))		
		edit_mode_groupbox.setLayout(self.edit_item_vbox)

		self.edit_mode_layout = QHBoxLayout()
		self.edit_mode_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.edit_mode_layout.addWidget(edit_mode_groupbox)
		self.edit_mode_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))

		return self.edit_mode_layout


	def create_utilities_ui(self):
		'''
		Utilities
		'''	
		mesh_label = QLabel('Mesh:')
		
		self.replace_mesh_pushButton = QPushButton('Replace Mesh')
		self.replace_mesh_pushButton.setFixedSize( 80, 25 )		
		self.replace_mesh_pushButton.setObjectName("pb_replace_mesh")
		self.replace_mesh_pushButton.pressed.connect(lambda:self.on_pressed_replace_mesh())		
		self.replace_mesh_pushButton.setToolTip('To update the item mesh, select the original mesh then the new mesh')
		
		self.transfer_mat_pushButton = QPushButton('Copy Material')
		self.transfer_mat_pushButton.setFixedSize( 85, 25 )		
		self.transfer_mat_pushButton.setObjectName("pb_transfer_mat")
		self.transfer_mat_pushButton.pressed.connect(lambda:self.on_pressed_transfer_mat())		
		self.transfer_mat_pushButton.setToolTip('Copy material from the first selected mesh to the last selected meshes.')		
		
		# Label
		mesh_label_box = QHBoxLayout()	
		mesh_label_box.addWidget(mesh_label)
		
		# Buttons
		mesh_buttons_box = QGridLayout()
		mesh_buttons_box.addWidget(self.replace_mesh_pushButton, 0, 0)
		mesh_buttons_box.addWidget(self.transfer_mat_pushButton, 0, 1)
		mesh_buttons_box.setSpacing(10)
		mesh_buttons_box.setHorizontalSpacing(10)

		# vbox		
		left_v_box = QVBoxLayout()
		left_v_box.addLayout(mesh_label_box)
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(mesh_buttons_box)
		middle_v_box.setAlignment(Qt.AlignLeft)
		right_v_box = QVBoxLayout()		
		right_v_box.setAlignment(Qt.AlignRight)

		mesh_box_layout = QHBoxLayout()			
		mesh_box_layout.setAlignment(Qt.AlignCenter)
		mesh_box_layout.addLayout(left_v_box)
		mesh_box_layout.addStretch(1)
		mesh_box_layout.addLayout(middle_v_box)
		mesh_box_layout.addStretch(1)
		mesh_box_layout.addLayout(right_v_box)		
		
		# Name has been Set
		self.utility_bone_label = QLabel('Bone:')

		self.cvc_bone_pushButton = QPushButton('CVC Bone')
		self.cvc_bone_pushButton.setFixedSize( 60, 25 )		
		self.cvc_bone_pushButton.setObjectName("pb_cvc_bone")
		self.cvc_bone_pushButton.pressed.connect(lambda:self.on_pressed_create_cvc_bone())		
		self.cvc_bone_pushButton.setToolTip('Create Bone from Object or Component Selection')	

		self.pivot_bone_pushButton = QPushButton('Pivot Bone')
		self.pivot_bone_pushButton.setFixedSize( 60, 25 )		
		self.pivot_bone_pushButton.setObjectName("pb_pivot_bone")
		self.pivot_bone_pushButton.pressed.connect(lambda:self.on_pressed_create_pivot_bone())		
		self.pivot_bone_pushButton.setToolTip('Create Bone from Component selction Custom Pivot')			

		# Label
		label_box = QHBoxLayout()	
		label_box.addWidget(self.utility_bone_label)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.cvc_bone_pushButton, 0, 0)
		buttons_box.addWidget(self.pivot_bone_pushButton, 0, 1)
		buttons_box.setSpacing(10)
		buttons_box.setHorizontalSpacing(10)

		# vbox		
		left_v_box = QVBoxLayout()
		left_v_box.addLayout(label_box)
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(buttons_box)
		middle_v_box.setAlignment(Qt.AlignLeft)
		right_v_box = QVBoxLayout()		
		right_v_box.setAlignment(Qt.AlignRight)

		bone_box_layout = QHBoxLayout()			
		bone_box_layout.setAlignment(Qt.AlignCenter)
		bone_box_layout.addLayout(left_v_box)
		bone_box_layout.addStretch(1)
		bone_box_layout.addLayout(middle_v_box)
		bone_box_layout.addStretch(1)
		bone_box_layout.addLayout(right_v_box)	

		# Controls
		# Name has been Set
		self.utility_control_label = QLabel('Control:')

		self.add_ctrl_combo = QComboBox()
		self.add_ctrl_combo.setFixedWidth(80)
		self.add_ctrl_combo.setFixedHeight(20)
		self.add_ctrl_combo.installEventFilter( self )
		self.add_ctrl_combo.setStyleSheet('''QComboBox {color: black; background-color: grey }''')	
		
		# populate the item bones comboBox
		controls = ['circleX','square','cube','sphere','arrow','cross','orient']				
		string_list = QStringListModel()
		string_list.setStringList(controls)
		self.add_ctrl_combo.setModel(string_list)			

		self.create_control_pushButton = QPushButton('Create Ctrl')
		self.create_control_pushButton.setFixedSize( 60, 25 )		
		self.create_control_pushButton.setObjectName("pb_create_ctrl")
		self.create_control_pushButton.pressed.connect(lambda:self.on_pressed_create_listbox_control())		
		self.create_control_pushButton.setToolTip('Create a control from the listbox selection')

		self.copy_pivot_pushButton = QPushButton('Copy Pivot')
		self.copy_pivot_pushButton.setFixedSize( 60, 25 )		
		self.copy_pivot_pushButton.setObjectName("pb_copy_pivot")
		self.copy_pivot_pushButton.pressed.connect(lambda:self.on_pressed_copy_pivot())		
		self.copy_pivot_pushButton.setToolTip('Copy pivot from first selection to second selection')		

		self.scale_ctrl_up_pushButton = QPushButton('Scale+')
		self.scale_ctrl_up_pushButton.setFixedSize( 42, 25 )		
		self.scale_ctrl_up_pushButton.setObjectName("pb_scale_ctrl_up")
		self.scale_ctrl_up_pushButton.pressed.connect(lambda:self.on_pressed_ctrl_scale(1))
		self.scale_ctrl_up_pushButton.setToolTip('Scale selected control up')

		self.scale_ctrl_dwn_pushButton = QPushButton('Scale-')
		self.scale_ctrl_dwn_pushButton.setFixedSize( 42, 25 )		
		self.scale_ctrl_dwn_pushButton.setObjectName("pb_scale_ctrl_dwn")
		self.scale_ctrl_dwn_pushButton.pressed.connect(lambda:self.on_pressed_ctrl_scale(0))
		self.scale_ctrl_dwn_pushButton.setToolTip('Scale selected control down')

		self.set_color_combo = QComboBox()
		self.set_color_combo.setFixedWidth(40)
		self.set_color_combo.setFixedHeight(20)
		self.set_color_combo.installEventFilter(self)
		self.set_color_combo.activated.connect(lambda:self.on_pressed_color_index_changed())		
		for rgb in self.maya_rgb_colors:
			pixmap = QPixmap(16,16)
			q_color = QColor()
			q_color.setRgb(rgb[0], rgb[1], rgb[2])
			pixmap.fill(q_color)
			icon = QIcon(pixmap)
			icon.name()
			self.set_color_combo.addItem(icon, '')

		self.rot_ctrl_x_pushButton = QPushButton('Rot X')
		self.rot_ctrl_x_pushButton.setFixedSize( 40, 25 )		
		self.rot_ctrl_x_pushButton.setObjectName("pb_rot_x")
		self.rot_ctrl_x_pushButton.pressed.connect(lambda:self.on_pressed_rot_90_axis(0))
		self.rot_ctrl_x_pushButton.setToolTip('Rotate selected control on the X axis 90 degrees')

		self.rot_ctrl_y_pushButton = QPushButton('Rot Y')
		self.rot_ctrl_y_pushButton.setFixedSize( 40, 25 )		
		self.rot_ctrl_y_pushButton.setObjectName("pb_rot_y")
		self.rot_ctrl_y_pushButton.pressed.connect(lambda:self.on_pressed_rot_90_axis(1))
		self.rot_ctrl_y_pushButton.setToolTip('Rotate selected control on the Y axis 90 degrees')

		self.rot_ctrl_z_pushButton = QPushButton('Rot Z')
		self.rot_ctrl_z_pushButton.setFixedSize( 40, 25 )		
		self.rot_ctrl_z_pushButton.setObjectName("pb_rot_z")
		self.rot_ctrl_z_pushButton.pressed.connect(lambda:self.on_pressed_rot_90_axis(2))
		self.rot_ctrl_z_pushButton.setToolTip('Rotate selected control on the Z axis 90 degrees')

		ctrl_color_box = QHBoxLayout()	
		ctrl_color_box.addWidget(self.set_color_combo)
		ctrl_color_box.addWidget(self.scale_ctrl_dwn_pushButton)
		ctrl_color_box.addWidget(self.scale_ctrl_up_pushButton)
		ctrl_color_box.addWidget(self.rot_ctrl_x_pushButton)
		ctrl_color_box.addWidget(self.rot_ctrl_y_pushButton)
		ctrl_color_box.addWidget(self.rot_ctrl_z_pushButton)	


		# Label
		label_ctrl_box = QHBoxLayout()	
		label_ctrl_box.addWidget(self.utility_control_label)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.add_ctrl_combo, 0, 0)
		buttons_box.addWidget(self.create_control_pushButton, 0, 1)
		buttons_box.addWidget(self.copy_pivot_pushButton, 0, 2)
		buttons_box.setSpacing(10)
		buttons_box.setHorizontalSpacing(10)

		# vbox		
		left_v_box = QVBoxLayout()
		left_v_box.addLayout(label_ctrl_box)
		middle_v_box = QVBoxLayout()
		middle_v_box.addLayout(buttons_box)
		middle_v_box.setAlignment(Qt.AlignLeft)
		right_v_box = QVBoxLayout()		
		right_v_box.setAlignment(Qt.AlignRight)	

		ctrl_box_layout = QHBoxLayout()			
		ctrl_box_layout.setAlignment(Qt.AlignCenter)
		ctrl_box_layout.addLayout(left_v_box)
		ctrl_box_layout.addStretch(1)
		ctrl_box_layout.addLayout(middle_v_box)
		ctrl_box_layout.addStretch(1)
		ctrl_box_layout.addLayout(right_v_box)	

		v_box_gap = 0
		self.utility_vbox = QVBoxLayout()
		self.utility_vbox.addLayout(bone_box_layout)
		self.utility_vbox.addStretch()
		self.utility_vbox.addSpacing(v_box_gap)
		self.utility_vbox.addLayout(ctrl_box_layout)
		self.utility_vbox.addStretch()
		self.utility_vbox.addSpacing(v_box_gap)
		self.utility_vbox.addLayout(ctrl_color_box)
		self.utility_vbox.addStretch()
		self.utility_vbox.addSpacing(v_box_gap)
		self.utility_vbox.addLayout(mesh_box_layout)
		self.utility_vbox.addStretch()
		self.utility_vbox.addSpacing(v_box_gap)		

		utility_groupbox = QGroupBox('Utilities')	
		utility_groupbox.setMinimumSize(QSize(323, 150))		
		utility_groupbox.setMaximumSize(QSize(323, 200))
		utility_groupbox.setLayout(self.utility_vbox)

		self.utility_layout = QHBoxLayout()
		self.utility_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.utility_layout.addWidget(utility_groupbox)
		self.utility_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))

		return self.utility_layout

		# bone utilities

		# control utilities

		# mesh utilites


	def create_unassigned_ui(self):
		'''
		##### LISTVIEW BOX LAYOUT ########
		'''			

		# ListView
		self.listView = QListWidget()
		self.listView.SingleSelection
		self.listView.setEditTriggers(QAbstractItemView.NoEditTriggers)
		#sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
		#sizePolicy.setHorizontalStretch(0)
		#sizePolicy.setVerticalStretch(0)		
		#self.listView.setSizePolicy(sizePolicy)
		self.listView.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.listView.currentItemChanged.connect(lambda:self.on_selected_listview())
		self.listView.clicked.connect(lambda:self.on_selected_listview())
		
		self.listView.setMinimumWidth(self.listView.sizeHintForColumn(0))
		
		#sizePolicy = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
		#self.listView.setSizePolicy(sizePolicy)
		#self.listView.setMinimumSize(QSize(1, 1))
		
		#self.listView.setMinimumSize(QSize(10, 25))
		#self.listView.setMaximumSize(QSize(10, 25))

		# HBox Layout
		self.unassigned_hbox = QHBoxLayout()	
		#self.unassigned_hbox.addStretch(1)
		self.unassigned_hbox.addWidget(self.listView)
		#self.unassigned_hbox.addStretch(1)

		self.select_mesh_pushButton = QPushButton('Select')
		self.select_mesh_pushButton.setFixedSize( 100, 25 )		
		self.select_mesh_pushButton.setObjectName("pb_sel_unassigned")
		self.select_mesh_pushButton.pressed.connect(lambda:self.on_pressed_sel_unassigned())

		self.delete_mesh_pushButton = QPushButton('Delete')
		self.delete_mesh_pushButton.setFixedSize( 100, 25 )		
		self.delete_mesh_pushButton.setObjectName("pb_del_unassigned")
		self.delete_mesh_pushButton.pressed.connect(lambda:self.on_pressed_del_unassigned())		

		# Buttons
		self.unassigned_buttons_box = QGridLayout()
		#self.unassigned_buttons_box.setSpacing(1)
		self.unassigned_buttons_box.setHorizontalSpacing(20)		
		self.unassigned_buttons_box.addWidget(self.select_mesh_pushButton, 0, 0)
		self.unassigned_buttons_box.addWidget(self.delete_mesh_pushButton, 0, 1)				

		# Vertical Layout
		self.unassigned_vbox = QVBoxLayout()
		#self.unassigned_vbox.addStretch(1)
		self.unassigned_vbox.addLayout(self.unassigned_hbox)
		self.unassigned_vbox.addLayout(self.unassigned_buttons_box)
		#self.unassigned_vbox.addStretch(1)

		# GroupBox & Layout
		self.unassigned_meshes_groupbox = QGroupBox('Unassigned Meshes')
		sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
		#sizePolicy.setHorizontalStretch(0)
		#sizePolicy.setVerticalStretch(1)
		self.unassigned_meshes_groupbox.setSizePolicy(sizePolicy)
		self.unassigned_meshes_groupbox.setLayout(self.unassigned_vbox)		

		self.unassigned_layout = QHBoxLayout()
		self.unassigned_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.unassigned_layout.addWidget(self.unassigned_meshes_groupbox)		
		self.unassigned_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		

		return self.unassigned_layout		


	def create_edit_item_ui(self):
		'''
		##### MESHES BOX LAYOUT ########
		'''

		# Base Mesh
		base_mesh_label = QLabel('BaseMesh:')
		base_mesh_label.setGeometry(10,10,100,30)
		self.base_mesh_text = QLineEdit()
		self.base_mesh_text.setEnabled(False)
		self.base_mesh_text.setStyleSheet('''QLineEdit {color: Red; background-color: white }''')
		self.base_mesh_text.setFixedWidth(160)
		self.base_mesh_text.setFixedHeight(20)
		self.base_mesh_text.setPlaceholderText('Select the Base Mesh')
		self.base_mesh_text.installEventFilter( self )		

		self.pick_base_mesh_pushButton = QPushButton('<<')
		self.pick_base_mesh_pushButton.setFixedSize( 25, 20 )		
		self.pick_base_mesh_pushButton.setObjectName("pb_pick_base")
		self.pick_base_mesh_pushButton.setToolTip('Select the Base Mesh')
		self.pick_base_mesh_pushButton.pressed.connect(lambda:self.on_pressed_mesh_picked(base_mesh=True))

		self.remove_base_mesh_pushButton = QPushButton('X')
		self.remove_base_mesh_pushButton.setFixedSize( 22, 20 )		
		self.remove_base_mesh_pushButton.setObjectName("pb_remove_base")
		self.remove_base_mesh_pushButton.setToolTip('Remove the selected base mesh')
		self.remove_base_mesh_pushButton.pressed.connect(lambda:self.on_pressed_mesh_remove(base_mesh=True))

		self.info_base_mesh_pushButton = QPushButton('?')
		self.info_base_mesh_pushButton.setFixedSize( 15, 20 )		
		self.info_base_mesh_pushButton.setObjectName("pb_base_mesh_info")
		self.info_base_mesh_pushButton.setToolTip('Info on removing the base mesh')
		self.info_base_mesh_pushButton.pressed.connect(lambda:self.on_pressed_info(info_type='base'))		

		# Label
		label_box = QHBoxLayout()
		label_box.addStretch(1)
		label_box.addWidget(base_mesh_label, 0, Qt.AlignRight)		

		# Text
		text_box = QHBoxLayout()
		text_box.addStretch(1)
		text_box.addWidget(self.base_mesh_text)
		text_box.addStretch(1)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.pick_base_mesh_pushButton, 0, 0)
		buttons_box.addWidget(self.remove_base_mesh_pushButton, 0, 1)
		buttons_box.addWidget(self.info_base_mesh_pushButton, 0, 2)
		buttons_box.setSpacing(1)
		buttons_box.setHorizontalSpacing(1)

		# Base Mesh GridLayout
		self.base_mesh_hbox = QGridLayout()
		self.base_mesh_hbox.addLayout(label_box, 0, 0)
		self.base_mesh_hbox.addLayout(text_box, 0, 1)
		self.base_mesh_hbox.addLayout(buttons_box, 0, 2)

		'''
		##### Add Mesh ########
		'''				
		# Add Mesh
		self.add_mesh_label = QLabel('     Mesh: ')
		self.add_mesh_label.setGeometry(10,10,100,30)

		self.add_mesh_text = QLineEdit()
		self.add_mesh_text.setEnabled(False)
		self.add_mesh_text.setStyleSheet('''QLineEdit {color: black; background-color: grey }''')
		self.add_mesh_text.setFixedWidth(160)
		self.add_mesh_text.setFixedHeight(20)
		self.add_mesh_text.setPlaceholderText('Select a new mesh')
		self.add_mesh_text.installEventFilter( self )		

		self.add_mesh_pushButton = QPushButton('<<')
		self.add_mesh_pushButton.setFixedSize( 25, 20 )		
		self.add_mesh_pushButton.setObjectName("pb_pick_mesh")
		self.add_mesh_pushButton.setToolTip('Select a mesh')
		self.add_mesh_pushButton.pressed.connect(lambda:self.on_pressed_mesh_picked(base_mesh=False))

		self.remove_mesh_pushButton = QPushButton('X')
		self.remove_mesh_pushButton.setFixedSize( 22, 20 )		
		self.remove_mesh_pushButton.setObjectName("pb_remove_mesh")
		self.remove_mesh_pushButton.setToolTip('Remove the picked mesh')
		self.remove_mesh_pushButton.pressed.connect(lambda:self.on_pressed_mesh_remove(base_mesh=False))

		self.info_mesh_pushButton = QPushButton('?')
		self.info_mesh_pushButton.setFixedSize( 15, 20 )		
		self.info_mesh_pushButton.setObjectName("pb_mesh_info")
		self.info_mesh_pushButton.setToolTip('Info on adding a Mesh')
		self.info_mesh_pushButton.pressed.connect(lambda:self.on_pressed_info(info_type='mesh'))			

		# Label
		label_box = QHBoxLayout()
		label_box.addStretch(1)
		label_box.addWidget(self.add_mesh_label, 0, Qt.AlignRight)

		# Text
		text_box = QHBoxLayout()
		text_box.addStretch(1)
		text_box.addWidget(self.add_mesh_text)
		text_box.addStretch(1)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.add_mesh_pushButton, 0, 0)
		buttons_box.addWidget(self.remove_mesh_pushButton, 0, 1)
		buttons_box.addWidget(self.info_mesh_pushButton, 0, 2)
		buttons_box.setSpacing(1)
		buttons_box.setHorizontalSpacing(1)		

		# Base Mesh GridLayout
		self.add_mesh_hbox = QGridLayout()
		self.add_mesh_hbox.addLayout(label_box, 0, 0)
		self.add_mesh_hbox.addLayout(text_box, 0, 1)
		self.add_mesh_hbox.addLayout(buttons_box, 0, 2)	

		'''
		##### Pick Bone ########
		'''				
		# Add Bone
		self.add_bone_label = QLabel('      Bone: ')
		self.add_bone_label.setGeometry(10,10,100,30)

		# ComboBox
		self.active_sel_bone_combo = True
		self.add_bone_combo = QComboBox()
		self.add_bone_combo.setFixedWidth(160)
		self.add_bone_combo.setFixedHeight(20)
		self.add_bone_combo.installEventFilter( self )
		self.add_bone_combo.setStyleSheet('''QComboBox {color: black; background-color: orange }''')		

		# Pick Bone
		self.add_bone_pushButton = QPushButton('<<')
		self.add_bone_pushButton.setFixedSize( 25, 20 )		
		self.add_bone_pushButton.setObjectName("pb_pick_bone")
		self.add_bone_pushButton.setToolTip('Select a bone')
		self.add_bone_pushButton.pressed.connect(lambda:self.on_pressed_bone_picked())

		# Remove Bone
		self.remove_bone_pushButton = QPushButton('X')
		self.remove_bone_pushButton.setFixedSize( 22, 20 )		
		self.remove_bone_pushButton.setObjectName("pb_remove_bone")
		self.remove_bone_pushButton.setToolTip('Remove the selected bone')
		self.remove_bone_pushButton.pressed.connect(lambda:self.on_pressed_bone_remove())

		# Add Bone Info
		self.info_bone_pushButton = QPushButton('?')
		self.info_bone_pushButton.setFixedSize( 15, 20 )		
		self.info_bone_pushButton.setObjectName("pb_bone_info")
		self.info_bone_pushButton.setToolTip('Info on adding an item Bone')
		self.info_bone_pushButton.pressed.connect(lambda:self.on_pressed_info(info_type='bone'))			

		# Label
		label_box = QHBoxLayout()
		label_box.addStretch(1)
		label_box.addWidget(self.add_bone_label, 0, Qt.AlignRight)

		# Text
		b_text_box = QHBoxLayout()
		b_text_box.addStretch(1)
		b_text_box.addWidget(self.add_bone_combo)
		b_text_box.addStretch(1)

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.add_bone_pushButton, 0, 0)
		buttons_box.addWidget(self.remove_bone_pushButton, 0, 1)
		buttons_box.addWidget(self.info_bone_pushButton, 0, 2)
		buttons_box.setSpacing(1)
		buttons_box.setHorizontalSpacing(1)			

		# Base Mesh GridLayout
		self.add_bone_hbox = QGridLayout()
		self.add_bone_hbox.addLayout(label_box, 0, 0)
		self.add_bone_hbox.addLayout(b_text_box, 0, 1)
		self.add_bone_hbox.addLayout(buttons_box, 0, 2)		

		'''
		##### Sel Bone ########
		'''				
		# Sel Bone
		self.sel_bone_label = QLabel('      Bone: ')
		self.sel_bone_label.setGeometry(10,10,100,30)	

		# Sel Bone Text
		self.sel_bone_text = QLineEdit()
		self.sel_bone_text.setEnabled(False)
		self.sel_bone_text.setStyleSheet('''QLineEdit {color: black; background-color: orange }''')
		self.sel_bone_text.setFixedWidth(160)
		self.sel_bone_text.setFixedHeight(20)
		self.sel_bone_text.setPlaceholderText('Select a new bone')
		self.sel_bone_text.installEventFilter( self )		

		# Sel Bone
		self.sel_bone_pushButton = QPushButton('<<')
		self.sel_bone_pushButton.setFixedSize( 25, 20 )		
		self.sel_bone_pushButton.setObjectName("pb_pick_bone")
		self.sel_bone_pushButton.setToolTip('Select a bone')
		self.sel_bone_pushButton.pressed.connect(lambda:self.on_pressed_bone_picked())

		# Remove Sel Bone
		self.remove_sel_bone_pushButton = QPushButton('X')
		self.remove_sel_bone_pushButton.setFixedSize( 22, 20 )		
		self.remove_sel_bone_pushButton.setObjectName("pb_remove_bone")
		self.remove_sel_bone_pushButton.setToolTip('Remove the selected bone')
		self.remove_sel_bone_pushButton.pressed.connect(lambda:self.on_pressed_bone_remove())

		self.info_sel_bone_pushButton = QPushButton('?')
		self.info_sel_bone_pushButton.setFixedSize( 15, 20 )		
		self.info_sel_bone_pushButton.setObjectName("pb_bone_info")
		self.info_sel_bone_pushButton.setToolTip('Info on adding an item Bone')
		self.info_sel_bone_pushButton.pressed.connect(lambda:self.on_pressed_info(info_type='bone'))			

		# Sel Bone Layout

		# Label
		label_box = QHBoxLayout()
		label_box.addStretch(1)
		label_box.addWidget(self.sel_bone_label, 0, Qt.AlignRight)

		# Text
		b_text_box = QHBoxLayout()
		b_text_box.addStretch(1)
		b_text_box.addWidget(self.sel_bone_text)
		b_text_box.addStretch(1)		

		# Buttons
		buttons_box = QGridLayout()
		buttons_box.addWidget(self.sel_bone_pushButton, 0, 0)
		buttons_box.addWidget(self.remove_sel_bone_pushButton, 0, 1)
		buttons_box.addWidget(self.info_sel_bone_pushButton, 0, 2)
		buttons_box.setSpacing(1)
		buttons_box.setHorizontalSpacing(1)			

		# Base Mesh GridLayout
		self.sel_bone_hbox = QGridLayout()
		self.sel_bone_hbox.addLayout(label_box, 0, 0)
		self.sel_bone_hbox.addLayout(b_text_box, 0, 1)
		self.sel_bone_hbox.addLayout(buttons_box, 0, 2)

		'''
		##### Add Control ########
		'''				
		# Add Bone
		self.ctrl_label = QLabel('      Control: ')
		self.ctrl_label.setGeometry(10,10,100,30)

		# lineEdit
		self.add_ctrl_text = QLineEdit()
		self.add_ctrl_text.setEnabled(False)
		self.add_ctrl_text.setStyleSheet('''QLineEdit {color: black; background-color: grey }''')
		self.add_ctrl_text.setFixedWidth(160)
		self.add_ctrl_text.setFixedHeight(20)
		self.add_ctrl_text.setPlaceholderText('Select a new control shape')
		self.add_ctrl_text.installEventFilter( self )		

		# Pick Bone
		self.add_ctrl_pushButton = QPushButton('<<')
		self.add_ctrl_pushButton.setFixedSize( 25, 20 )		
		self.add_ctrl_pushButton.setObjectName("pb_pick_control")
		self.add_ctrl_pushButton.setToolTip('Select a custom control shape')
		self.add_ctrl_pushButton.pressed.connect(lambda:self.on_pressed_ctrl_picked())

		# Remove Bone
		self.remove_ctrl_pushButton = QPushButton('X')
		self.remove_ctrl_pushButton.setFixedSize( 22, 20 )		
		self.remove_ctrl_pushButton.setObjectName("pb_remove_control")
		self.remove_ctrl_pushButton.setToolTip('Remove the selected control')
		self.remove_ctrl_pushButton.pressed.connect(lambda:self.on_pressed_ctrl_remove())

		self.info_control_pushButton = QPushButton('?')
		self.info_control_pushButton.setFixedSize( 15, 20 )		
		self.info_control_pushButton.setObjectName("pb_control_info")
		self.info_control_pushButton.setToolTip('Info on picking an item control.')
		self.info_control_pushButton.pressed.connect(lambda:self.on_pressed_info(info_type='rh_control'))		

		# Label
		self.ctrl_label_box = QHBoxLayout()
		self.ctrl_label_box.addStretch(1)
		self.ctrl_label_box.addWidget(self.ctrl_label, 0, Qt.AlignRight)

		# Text
		self.ctrl_text_box = QHBoxLayout()		
		self.ctrl_text_box.addStretch(1)
		self.ctrl_text_box.addWidget(self.add_ctrl_text)
		self.ctrl_text_box.addStretch(1)		

		# Buttons
		self.ctrl_buttons_box = QGridLayout()
		self.ctrl_buttons_box.addWidget(self.add_ctrl_pushButton, 0, 0)
		self.ctrl_buttons_box.addWidget(self.remove_ctrl_pushButton, 0, 1)
		self.ctrl_buttons_box.addWidget(self.info_control_pushButton, 0, 2)
		self.ctrl_buttons_box.setSpacing(1)
		self.ctrl_buttons_box.setHorizontalSpacing(1)			

		# Base Mesh GridLayout
		self.add_ctrl_hbox = QGridLayout()
		self.add_ctrl_hbox.addLayout(self.ctrl_label_box, 0, 0)
		self.add_ctrl_hbox.addLayout(self.ctrl_text_box, 0, 1)
		self.add_ctrl_hbox.addLayout(self.ctrl_buttons_box, 0, 2)			

		'''
		##### Add Parent Control ########
		'''				
		# Add Bone
		self.parent_ctrl_label = QLabel('Parent Ctrl:')
		self.parent_ctrl_label.setGeometry(10,10,100,30)

		# ComboBox
		self.parent_ctrl_combo = QComboBox()
		self.parent_ctrl_combo.setFixedWidth(160)
		self.parent_ctrl_combo.setFixedHeight(20)
		self.parent_ctrl_combo.installEventFilter( self )
		self.parent_ctrl_combo.setStyleSheet('''QComboBox {color: black; background-color: grey }''')	

		# Pick Bone
		self.parent_ctrl_add_pushButton = QPushButton('<<')
		self.parent_ctrl_add_pushButton.setFixedSize( 25, 20 )		
		self.parent_ctrl_add_pushButton.setObjectName("pb_pick_parent_control")
		self.parent_ctrl_add_pushButton.setToolTip('Select an existing control shape')
		self.parent_ctrl_add_pushButton.setDisabled(True)
		#self.parent_ctrl_add_pushButton.setVisible(False)
		self.parent_ctrl_add_pushButton.pressed.connect(lambda:self.on_pressed_parent_ctrl_picked())

		# Remove Bone
		self.parent_ctrl_remove_pushButton = QPushButton('X')
		self.parent_ctrl_remove_pushButton.setFixedSize( 22, 20 )		
		self.parent_ctrl_remove_pushButton.setObjectName("pb_parent_remove_control")
		self.parent_ctrl_remove_pushButton.setDisabled(True)

		self.info_parent_control_pushButton = QPushButton('?')
		self.info_parent_control_pushButton.setFixedSize( 15, 20 )		
		self.info_parent_control_pushButton.setObjectName("pb_parent_control_info")
		self.info_parent_control_pushButton.pressed.connect(lambda:self.on_pressed_info(info_type='parent_control'))		

		# Label
		ctrl_label_box = QHBoxLayout()
		ctrl_label_box.addStretch(1)
		ctrl_label_box.addWidget(self.parent_ctrl_label, 0, Qt.AlignRight)

		# Text
		ctrl_text_box = QHBoxLayout()		
		ctrl_text_box.addStretch(1)
		ctrl_text_box.addWidget(self.parent_ctrl_combo)
		ctrl_text_box.addStretch(1)		

		# Buttons
		ctrl_buttons_box = QGridLayout()
		ctrl_buttons_box.addWidget(self.parent_ctrl_add_pushButton, 0, 0)
		ctrl_buttons_box.addWidget(self.parent_ctrl_remove_pushButton, 0, 1)
		ctrl_buttons_box.addWidget(self.info_parent_control_pushButton, 0, 2)
		ctrl_buttons_box.setSpacing(1)
		ctrl_buttons_box.setHorizontalSpacing(1)		

		# Base Mesh GridLayout
		parent_add_ctrl_hbox = QGridLayout()
		parent_add_ctrl_hbox.addLayout(ctrl_label_box, 0, 0)
		parent_add_ctrl_hbox.addLayout(ctrl_text_box, 0, 1)
		parent_add_ctrl_hbox.addLayout(ctrl_buttons_box, 0, 2)

		'''
		##### Add Mesh Button ########
		'''	
		# Set Mesh
		self.set_mesh_pushButton = QPushButton('Add the Mesh')
		self.set_mesh_pushButton.setFixedSize( 200, 30 )		
		self.set_mesh_pushButton.setObjectName("pb_set_mesh")
		self.set_mesh_pushButton.pressed.connect(lambda:self.on_pressed_set_mesh())		
		self.set_mesh_pushButton.setDisabled(True)

		# Add Bone Layout
		self.set_mesh_hbox = QHBoxLayout()
		self.set_mesh_hbox.addStretch(1)
		self.set_mesh_hbox.addWidget(self.set_mesh_pushButton)
		self.set_mesh_hbox.addStretch(1)
		#self.set_mesh_hbox.addSpacing(10)

		'''
		Edit Table
		'''
		self.create_edit_table_ui()

		''''''

		''''''		

		# Vertical Layout
		self.meshes_vbox = QVBoxLayout()
		self.meshes_vbox.addStretch(1)
		self.meshes_vbox.addLayout(self.base_mesh_hbox)
		self.meshes_vbox.addLayout(self.tw_meshes_layout)
		#self.meshes_vbox.addStretch(1)
		self.meshes_vbox.addStretch(0)
		self.meshes_vbox.addSpacing(20)		
		self.meshes_vbox.addLayout(self.add_mesh_hbox)		
		self.meshes_vbox.addStretch(1)
		self.meshes_vbox.addLayout(self.add_bone_hbox)
		self.meshes_vbox.addLayout(self.sel_bone_hbox)
		#self.meshes_vbox.addStretch(1)
		self.meshes_vbox.addSpacing(20)
		self.meshes_vbox.addLayout(self.add_ctrl_hbox)		
		self.meshes_vbox.addLayout(parent_add_ctrl_hbox)
		self.meshes_vbox.addStretch(0)
		self.meshes_vbox.addSpacing(10)
		self.meshes_vbox.addLayout(self.set_mesh_hbox)
		self.meshes_vbox.addStretch(1)

		# GroupBox & Layout
		self.meshes_groupbox = QGroupBox('Edit Item')
		sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		sizePolicy.setHorizontalStretch(0)
		sizePolicy.setVerticalStretch(0)
		#sizePolicy.setHeightForWidth(self.meshes_groupbox.sizePolicy().hasHeightForWidth())		
		self.meshes_groupbox.setSizePolicy(sizePolicy)
		#self.meshes_groupbox.setMinimumSize(QSize(325, 500))		
		self.meshes_groupbox.setLayout(self.meshes_vbox)		

		self.edit_layout = QHBoxLayout()
		self.edit_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
		self.edit_layout.addWidget(self.meshes_groupbox)		
		self.edit_layout.addItem((QSpacerItem(20, 40, QSizePolicy.Maximum, QSizePolicy.Maximum)))


		# Add the individual Layouts to the main HBox


		return self.edit_layout


	def create_header_ui(self):
		"""
		Create the Header banner UI

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:43:55 PM
		"""

		# Create image widget
		label = None				
		header_file = HEADER_LOGO
		if os.path.isfile(header_file):
			label = QLabel()
			pixmap = QPixmap(header_file)
			label.setPixmap(pixmap)			

		self.image_layout = QHBoxLayout()
		if label:
			self.image_layout.addItem((QSpacerItem(200, 20, QSizePolicy.Maximum, QSizePolicy.Maximum)))		
			self.image_layout.addWidget(label)
			self.image_layout.addItem((QSpacerItem(200, 20, QSizePolicy.Maximum, QSizePolicy.Maximum)))


	def create_edit_table_ui(self):
		"""
		Create the Edit Mesh ListBox section of the UI

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/14/2015 4:32:26 PM
		"""	

		# QTtable Settings
		self.tw_meshes = QTableWidget()	
		self.tw_meshes.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		self.tw_meshes.setEditTriggers(QAbstractItemView.EditKeyPressed )
		self.tw_meshes.setAlternatingRowColors(True)
		self.tw_meshes.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.tw_meshes.setTextElideMode(Qt.ElideRight)
		self.tw_meshes.setWordWrap(True)
		self.tw_meshes.setCornerButtonEnabled(True)
		self.tw_meshes.setObjectName("tw_meshes")
		self.tw_meshes.setColumnCount(3)
		self.tw_meshes.setRowCount(1)	
		self.tw_meshes.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
		self.vertical_bar = self.tw_meshes.verticalScrollBar()
		self.tw_meshes.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.tw_meshes.setMaximumWidth(295)
		self.tw_meshes.setContextMenuPolicy(Qt.CustomContextMenu)
		self.tw_meshes.customContextMenuRequested.connect(self.on_open_tw_meshes_menu)
		self.tw_meshes.cellChanged.connect( self.on_mesh_name_changed )


		''' Update this index when the Name column changes '''
		self.row_name_column = 0

		# Fill out the table temporarily
		item = QTableWidgetItem()
		self.tw_meshes.setVerticalHeaderItem(0, item)
		item = QTableWidgetItem()
		self.tw_meshes.setHorizontalHeaderItem(0, item)
		item = QTableWidgetItem()
		self.tw_meshes.setHorizontalHeaderItem(1, item)
		item = QTableWidgetItem()
		self.tw_meshes.setHorizontalHeaderItem(2, item)

		if QT_VERSION == 'pyside':
			self.tw_meshes.horizontalHeaderItem(0).setText(QApplication.translate(WINDOW_TITLE, "Mesh", None, QApplication.UnicodeUTF8))
			self.tw_meshes.horizontalHeaderItem(1).setText(QApplication.translate(WINDOW_TITLE, "Material", None, QApplication.UnicodeUTF8))
			self.tw_meshes.horizontalHeaderItem(2).setText(QApplication.translate(WINDOW_TITLE, "UVs", None, QApplication.UnicodeUTF8))

		elif QT_VERSION == 'pyside2':
			self.tw_meshes.horizontalHeaderItem(0).setText("Mesh")
			self.tw_meshes.horizontalHeaderItem(1).setText("Material")
			self.tw_meshes.horizontalHeaderItem(2).setText("UVs")

		# Table Header Settings
		self.tw_meshes.horizontalHeader().setVisible(True)
		self.tw_meshes.horizontalHeader().setDefaultSectionSize(100)
		self.tw_meshes.horizontalHeader().setHighlightSections(True)
		self.tw_meshes.horizontalHeader().setSortIndicatorShown(False)
		self.tw_meshes.horizontalHeader().setStretchLastSection(True)
		self.tw_meshes.verticalHeader().setVisible(False)
		self.tw_meshes.verticalHeader().setCascadingSectionResizes(True)
		self.tw_meshes.verticalHeader().setDefaultSectionSize(19)
		self.tw_meshes.verticalHeader().setStretchLastSection(False)

		# set the column width defaults	
		self.update_column_widths()

		# Connections
		self.tw_meshes.clicked.connect( partial( self.on_cell_clicked ) )

		self.selection_model = self.tw_meshes.selectionModel()
		self.connect( self.selection_model, SIGNAL( 'selectionChanged(QItemSelection, QItemSelection)'), self.on_row_selection_changed )

		# GroupBox & Layout
		self.tw_meshes_layout = QHBoxLayout()	
		self.tw_meshes_layout.addWidget(self.tw_meshes)	

		self.vertical_bar_last = self.vertical_bar.value()
		self.tw_meshes.installEventFilter( self )

		return self.tw_meshes_layout


	def setupUi(self, inital=False):
		"""
		Initial UI Setup

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:44:51 PM
		"""		

		# Main Layout
		self.main_layout = QVBoxLayout()
		self.main_layout.setAlignment( Qt.AlignTop )		

		'''
		##### IMAGE BOX LAYOUT ########
		'''			
		self.create_header_ui()
		self.main_layout.addLayout(self.image_layout)

		# only add this if there are no item_nodes present
		if inital:
			create_initial_ui = True
			if pymel.objExists('Weapon'):
				item_node = pymel.PyNode('Weapon')
				if item_node:
					if self.get_attribute_value(item_node, 'rh_item_data'):
						create_initial_ui = False
			elif pymel.objExists('Vehicle'):
				item_node = pymel.PyNode('Vehicle')
				if item_node:
					if self.get_attribute_value(item_node, 'rh_item_data'):
						create_initial_ui = False			

			# Name/Create Item
			if create_initial_ui:
				self.create_rename_item_ui()
				self.cancel_pushButton.setDisabled(True)
				self.cancel_pushButton.setVisible(False)
				self.main_layout.addLayout(self.rename_layout)
				self.settings_groupbox.setTitle('Item Name')
				self.active_rename_layout = True
			else:
			# Item Named
				self.create_item_name_ui()
				self.main_layout.addLayout(self.item_name_layout)
				self.active_item_name_layout = True

		self.retranslateUi()


	def remove_layout(self, layout):
		"""
		Remove layout and widgets
		Supposedly the safest removal method
		https://stackoverflow.com/questions/4528347/clear-all-widgets-in-a-layout-in-pyqt

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/20/2014 4:49:33 PM
		"""
		
		try:
			shiboken.isValid(layout)
		except:
			return		

		try:
			for i in reversed(range(layout.count())):
				widget = layout.itemAt(i).widget()
				if widget:
					layout.removeWidget(widget)
					widget.setParent(None)
		except RuntimeError:
			pass

		# clear the main layout
		try:
			layout.setParent(None)
			QWidget().setLayout(layout)
		except:
			pass


	def update_column_widths( self ):
		"""
		Update the Mesh Grid column widths after resizing

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/14/2015 5:38:20 PM
		"""

		# resize the columns
		self.column_name_width = 140
		self.tw_meshes.setColumnWidth( 0, self.column_name_width )
		self.tw_meshes.setColumnWidth( 1, 95 )
		self.tw_meshes.setColumnWidth( 2, 10 )

		header = self.tw_meshes.horizontalHeader()		
		self.tw_meshes.setColumnWidth( 2, 10 )		
		self.tw_meshes.horizontalHeader().setResizeMode(2, QHeaderView.Stretch)		
	
		return

	def check_duplicate_names(self):
		"""
		Make sure there are not duplicate named objects in the scene
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/29/2014 2:40:39 PM
		"""
		
		error_msg = ''
		self.duplicate_names = []
		duplicate_names = rh_maya.get_duplicated_node_names()
		if duplicate_names:
			self.duplicate_names = duplicate_names
			error_msg += 'DUPLICATED NAMED OBJECTS:\nMultiple objects in the scene have the same name.\nPlease make sure these objects have unique names.' + '\n'
			for name in duplicate_names:
				error_msg += ' Duplicate Object Name: {0}\n'.format(name)
			error_msg += '\n'
			return True, error_msg
		else:
			return False, ''		

	def do_check_can_export(self):
		"""
		Run checks to make sure we can export the item

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/30/2014 9:33:46 AM
		"""

		error_msg = ''
		
		# make sure there are no namespaces in the scene
		namespaces = rh_maya.get_scene_namespaces()
		if namespaces:
			error_string = ' \n'.join(namespaces)
			error_string += '\n'
			error_msg += 'NAMESPACES:\nThere are namespaces found in your scene.\nYou must get rid of all namespaces before continuing.\n {0}\n'.format(error_string)			
			maya.mel.eval('NamespaceEditor;')
			
		# make sure there are no duplicate node names in the scene
		dupe_names, error = self.check_duplicate_names()
		if dupe_names:
			error_msg += error		

		# make sure there are no unassigned objects
		#if self.unassigned_objects:
			#error_msg += 'UNASSIGNED OBJECTS:\nThere are unassigned objects in the scene.\nPlease clear these out before exporting.' + '\n'
			
		if self.item_type == 'Weapon':
			item_path = os.path.join(PROJECT_ART_PATH, 'Weapons').lower().replace('\\','/')
		else:
			item_path = os.path.join(PROJECT_ART_PATH, 'Vehicles').lower().replace('\\','/')

		# make sure the file is saved in the depot
		filename = cmds.file(q=True, sceneName=True)
		filename_error = False
		if not filename:
			error_msg += '\nFILENAME:\nThis file has not been saved in the depot project art path.\nPlease save file under {0}\n'.format(item_path)
			filename_error = True
		else:
			if not '/rig/' in filename.lower():
				print filename
				error_msg += 'The item rig file must be saved in a rig subfolder.\nPlease save file under {0}\n'.format(item_path + '/itemName/rig/itemName_rig.ma')				

		if not filename_error:			
			if not filename.lower().startswith(item_path):
				error_msg += 'This file is not saved in the depot project art path.\nPlease save file under {0}\n'.format(item_path)

		# make sure there is a item node and a base mesh
		if not self.item_node:
			error_msg += '\nNO ITEM:\nThere is not yet a rigged item to export.\n'
		else:
			if not self.item_base_mesh:
				error_msg += '\nNO ITEM:\nThere is not yet a rigged item base mesh to export.\n'

		# make sure all textures are valid
		textures_are_valid = True
		#textures_are_valid, error_string = validate_scene_textures()
		if not textures_are_valid:
			error_msg += '\nBAD TEXTURES:\nThere are textures not mapped relative to the K:\ drive.\nPlease fix or delete the texture references:\n{0}\n'.format(error_string)
			maya.mel.eval('FilePathEditor;')

		# make sure meshes are valid
		valid, mesh_errors = self.validate_item_meshes()
		if not valid:
			error_msg += mesh_errors + '\n'

		if error_msg:
			self.export_error_message = error_msg
			self.can_export = False
		else:
			self.export_error_message = ''
			self.can_export = True
			
			
	def do_add_mesh_attributes(self, mesh, bone=None, control=None, material_group=None, is_attachment=False, is_static=False):
		"""
		Add attributes that the item mesh should have

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/6/2014 1:42:57 PM
		"""
		
		# flag as attachement then return
		# everything else should already exist
		if is_attachment:
			if not pymel.hasAttr(mesh, 'rh_attachment'):
				pymel.addAttr(mesh, ln='rh_attachment', niceName='ItemAttachment', at='bool', keyable=False, dv=1)
			if not pymel.hasAttr(mesh, 'rh_static_mesh'):
				pymel.addAttr(mesh, ln='rh_static_mesh', niceName='MeshIsStatic', at='bool', keyable=False, dv=is_static)
			mesh.setAttr('rh_static_mesh', is_static)
			return		
	
		# flag as Item
		if not mesh.hasAttr(self.item_type_attr):
			pymel.addAttr(mesh, ln=self.item_type_attr, at='bool', keyable=False, dv=1)
			mesh.setAttr(self.item_type_attr, lock=True)		

		# message for the bone being added
		if not mesh.hasAttr('rh_bone'):
			pymel.addAttr(mesh, at='message', ln= 'rh_bone', niceName='Bone')
		else:
			mesh.setAttr('rh_bone', lock=False)
			connection = pymel.PyNode(mesh.longName()+'.rh_bone')
			if connection:
				connection.disconnect()		
		if bone:
			cmds.connectAttr( bone.longName() + '.message', mesh.longName() + '.rh_bone', f=True )
			mesh.setAttr('rh_bone', lock=True)

		# Mesh message for the control being added 
		if not mesh.hasAttr('rh_control'):					
			pymel.addAttr(mesh, at='message', ln= 'rh_control', niceName='Control')
		else:
			mesh.setAttr('rh_control', lock=False)
			connection = pymel.PyNode(mesh.longName()+'.rh_control')
			if connection:
				connection.disconnect()
		if control:
			cmds.connectAttr( control.longName() + '.message', mesh.longName() + '.rh_control', f=True )				
			mesh.setAttr('rh_control', lock=True)

		# add mesh attributes
		# Material Group Attribute
		if not pymel.hasAttr(mesh, 'rh_mat_group'):							
			pymel.addAttr(mesh, at='message', ln= 'rh_mat_group', niceName='MaterialGroup')				

		if mesh.hasAttr('rh_mat_group'):
			if not material_group:
				material_group = self.get_mesh_material_group(mesh)
			if material_group:
				cmds.connectAttr( material_group.nodeName() + '.message', '{0}.rh_mat_group'.format(mesh.longName()), f=True )	


	def do_add_mesh_row( self, row, row_data, select_row = True, ignore_name = True ):
		"""
		Add an animation row to the UI and self.row_data dict

		*Arguments:*
		* ``row``       row index
		* ``row_data``  if given the row_data will have the information for the row

		*Keyword Arguments:*
		* ``None`` Enter a description for the keyword argument here.
		* ``ignore_path`` Don't check the export path

		*Returns:*
		* ``None``

		*Examples:* ::

		Enter code examples here. (optional field)

		*Todo:*
		* Enter thing to do. (optional field)

		*Author:*
		* Randall Hess, randall.hess@gmail.com, 11/4/2014 12:23:01 PM
		"""	

		if row > self.tw_meshes.rowCount( ):
			row = -1

		if row == -1:
			row = self.tw_meshes.rowCount( )		

		self.tw_meshes.insertRow( row )	
		self.tw_meshes.blockSignals(True)
		
		# setup the row data
		mesh_name = 'Unknown'
		mesh_mats = 'Unknown'
		mesh_bone = 'None'		

		if row_data:
			mesh_name = row_data['name']			
			mesh_mats = row_data['rh_material']
			mesh_uvs  = row_data['uvs']	

		try:
			table_widget = QTableWidgetItem( mesh_name )			
			QTableWidget( )
		except TypeError:
			return False
		self.tw_meshes.setItem( row, 0, table_widget )

		try:
			table_widget = QTableWidgetItem( mesh_mats )
			table_widget.setFlags(Qt.ItemIsEnabled)
			QTableWidget()
		except TypeError:
			return False
		self.tw_meshes.setItem( row, 1, table_widget )

		try:
			table_widget = QTableWidgetItem( mesh_uvs )
			table_widget.setFlags(Qt.ItemIsEnabled)
			QTableWidget()
		except TypeError:
			return False
		self.tw_meshes.setItem( row, 2, table_widget )

		if select_row:
			self.tw_meshes.selectRow( row )
			
		self.tw_meshes.blockSignals(False)
			

	def do_export_attachments(self, step_value, progress_value, export_log, export_text, exported_files):
		"""
		Handle exporting attachments
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/9/2014 10:18:08 AM
		"""
		
		# update material names for export
		temp_group = pymel.PyNode('TEMP_Attachments')
	
		# export each attachment separately
		export_log += '\nExporting Attachments: \n'
		for mesh in self.item_attachments:
			
			do_export = True
			
			# create a custom group for the mesh
			pymel.select(cl=True)
			mesh_group = pymel.group(n='TEMP')	
			pymel.parent(mesh_group, self.item_node)
			pymel.parent(mesh, mesh_group)
			item_export_file = os.path.join(self.get_item_export_path(), self.item_name + "_" + mesh.nodeName()) + '.fbx'
	
			# update progress bar
			progress_value += step_value
			self.export_progress.setValue(progress_value)
			export_text += 'Exporting Attachment:  {0}\n'.format(mesh.nodeName())
			self.export_output.setText(export_text)					
			export_text += ' ...'
			self.export_output.setText(export_text)
			
			# handle static mesh			
			is_static_mesh = self.get_attribute_value(mesh, 'rh_static_mesh')
			if is_static_mesh == None:
				is_static_mesh = False
			export_mesh = None
			export_group = None
			if is_static_mesh:
				export_mesh = pymel.duplicate(mesh)[0]
				pymel.lockNode(export_mesh, lock=False)
				rh_maya.lock_channels(export_mesh, lock=False)
				bone = self.get_attribute_value(mesh, 'rh_bone')
				if not bone:					
					influences = rh_maya.get_skincluster_influences(mesh)
					if influences:
						if len(influences) > 1:
							print 'WARNING: There is more than one bone with influence for this attachment.\n{0}'.format(mesh.nodeName())
						bone = influences[0]

				# Fail if we didnt find an attachment bone				
				if not bone:
					export_text += 'FAILED to find a primary bone influence for this attachment!\n'
					self.export_output.setText(export_text)
					export_log += ' FAILED Exporting: {0}'.format(export_text)
					do_export = False
				else:
					pymel.select(cl=True)
					
					# create and snap a new group to the bone
					export_group = pymel.group(empty=True, n='MESH_' + mesh.nodeName())
					const = pymel.parentConstraint(bone, export_group, mo=False)
					pymel.delete(const)										
					pymel.parent(export_mesh, export_group)
					
					# move the group to the origin
					export_group.setAttr('translateX', 0.0)
					export_group.setAttr('translateY', 0.0)
					export_group.setAttr('translateZ', 0.0)
					
					# reset transform on the export mesh
					pymel.select(export_group, r=True)
					cmds.makeIdentity( apply=True, translate=True, rotate=True, scale=True, n=False )
					pymel.select(export_mesh)
					pymel.mel.eval("ResetTransformations;")
			
			if do_export:				
				if item_export_file:	
					did_export = False
					try:
						if export_mesh:
							did_export, did_export_string = rh_maya.export_weapon_part(export_mesh, export_group, weapon_export_file=item_export_file, is_static_mesh=is_static_mesh)
						else:
							did_export, did_export_string = rh_maya.export_weapon_part(mesh, mesh_group, weapon_export_file=item_export_file, is_static_mesh=is_static_mesh)
						export_text += ' Export Successful\n'
						self.export_output.setText(export_text)							
					except:
						export_text += ' Export Failed\n'
						self.export_output.setText(export_text)								
						tb = traceback.format_exc()
						export_log = 'Attachment Export Failed:\nCallstack from Main Export Crash:\nCopy this and send to your technical animator for debugging!\n\n{0}\n\nSee output for more details.'.format(tb)
		
		
					if did_export:
						exported_files.append(item_export_file)
						export_log += '{0}\n'.format(item_export_file)
					else:
						export_log += 'FAILED Exporting: {0}\n'.format(item_export_file)							
				else:
					error = 'Couldnt generate an export file for this attachment: {0}\n'.format(mesh.nodeName())
					export_log += ' FAILED Exporting: {0}'.format(error)
			
			# clean up new export mesh and group
			if export_group:
				pymel.delete(export_group)	
	
			pymel.parent(mesh, temp_group)
			pymel.delete(mesh_group)
	
		return export_log, export_text, exported_files	
	

	def on_pressed_export_item(self):
		"""
		Export the item

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/29/2014 7:23:39 PM
		"""	
		
		pymel.select(cl=True)
		exported_files = []
		export_string = ''

		# Show the progress bar
		self.export_progress.setValue(0)
		self.export_progress.setVisible(True)
		self.export_output.setVisible(True)
		self.export_groupbox.setMinimumSize(QSize(323, 300))
		
		export_text = 'Preparing Item Export...\n\n'
		self.export_output.setText(export_text)		
		
		temp_group = None
		export_attachments = False
		if self.item_attachments:	
			
			# ask the user to export attachments
			pymel.select(cl=True)
			temp_group = pymel.group(n='TEMP_Attachments')
			pymel.lockNode(self.item_node, lock=False)
			pymel.parent(temp_group, self.item_node)
			
			# move the attachments to separate groups
			attachment_string = ''
			for mesh in self.item_attachments:
				pymel.lockNode(mesh, lock=False)
				pymel.parent(mesh, temp_group)
				attachment_string += '  {0}\n'.format(mesh.nodeName())
				
			cmds.refresh()		
			
			query_txt = 'Would you like to also export each of the attachments?\n\nAttachments:\n{0}\n'.format(attachment_string)
			result = cmds.confirmDialog( title='Item Rigger: Export Attachments', message=query_txt, button=[ 'Yes', 'No' ], defaultButton='No', cancelButton='No',dismissString='No' )
			if result == 'Yes':
				export_attachments = True				
		
		# export the base item
		pymel.select(cl=True)
		export_log = ''
		progress_value = 0
		step_value = (100/ (len(self.item_attachments) + 2) )

		export_text += 'Exporting Item: {0}\n'.format(self.item_name)
		self.export_output.setText(export_text)
		export_text += ' ...'
		self.export_output.setText(export_text)
		did_export = False
		try:
			did_export, export_log = rh_maya.export_weapon_prep(quiet=True, item_type=self.item_type)
			if did_export:
				export_text += ' Export Successful\n'
				self.export_output.setText(export_text)
		except:
			export_text += ' Export Failed\n'
			self.export_output.setText(export_text)
			tb = traceback.format_exc()			
			export_log = 'Item Export Failed:\nCallstack from Main Export Crash:\nCopy this and send to your technical animator for debugging!\n\n{0}\n\nSee output for more details.'.format(tb)
		
		progress_value += step_value
		self.export_progress.setValue(progress_value)	
		
		# export the item parts
		if did_export:
			if export_attachments:				
				export_log, export_text, exported_files = self.do_export_attachments(step_value, progress_value, export_log, export_text, exported_files)
			
		pymel.refresh(force=True)
		
		# move the attachment back to their original groups
		export_text += '\nCleaning Up...\n'
		self.export_output.setText(export_text)
		if self.item_attachments:
			for mesh in self.item_attachments:				
				parent = self.get_attribute_value(mesh, 'rh_mat_group')
				if not parent:
					parent = self.get_material_group(index=0)
				pymel.parent(mesh, parent)
				pymel.lockNode(mesh, lock=True)
				
			# delete the temp group
			pymel.delete(temp_group)

			# lock everything
			pymel.lockNode(self.item_node, lock=True)		
		
		progress_value = 100
		self.export_progress.setValue(progress_value)
		pymel.select(cl=True)
		if not did_export:	
			cmds.confirmDialog( t='Item Export: Failed' , m=export_log, b='OK' )
		else:
			cmds.confirmDialog( t='Item Export: Completed' , m=export_log, b='OK' )			

		# restore buttons properly
		self.export_output.setText('')
		self.export_progress.setVisible(False)
		self.export_output.setVisible(False)
		self.export_groupbox.setMinimumSize(QSize(323, 100))
		self.export_pushButton.showNormal()
		self.export_pushButton.setDown(False)
		

	def on_pressed_cancel_rename(self):
		"""
		Cancle renaming item

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:39:13 PM
		"""

		# Remove the Rename Layout
		self.remove_layout(self.rename_layout)
		self.active_rename_layout = False

		# Add the item name Layout
		self.create_item_name_ui()
		self.main_layout.addLayout(self.item_name_layout)
		self.active_item_name_layout = True

		self.update_ui()		


	def on_pressed_edit_item(self):
		"""
		Handle going into edit mode

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:39:01 PM
		"""
		
		# check namespaces first
		namespaces = rh_maya.get_scene_namespaces()
		if namespaces:
			names = ' \n'.join(namespaces)
			message = 'There are namespaces in your scene!!\nPlease clear the namespaces out before continuing.\n\n{0}'.format(names)
			cmds.confirmDialog(t='Item Rigger: Error', m=message)
			maya.mel.eval('NamespaceEditor;')
			return False
		
		dupe_names, error = self.check_duplicate_names()
		if dupe_names:						
			message = error
			message += '\nPlease name these objects uniquely to continue.'
			cmds.confirmDialog(t='Item Rigger: Error', m=message)			
			return False			

		self.edit_mode = not(self.edit_mode)		
		self.on_toggle_edit_mode(edit=self.edit_mode, changed=True)


	def on_update_item_named(self, key=None, delete=False):
		"""
		Update the item named UI
		This is dynamically checking keys pressed to validate the text string and length

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/12/2014 5:03:34 PM
		"""

		text_val = self.textEditor.text()
		if not text_val:
			return

		self.textEditor.setStyleSheet('''QLineEdit {color: black; background-color: gray }''')

		num_characters = len(text_val)		
		# add the last pressed key to the text
		if key:
			text_val = text_val + key

		if delete:
			text_val = text_val[:-1]
			num_characters -= 1
		else:
			num_characters += 1

		if not rh_maya.validate_text(text_val, numbers=True):
			self.textEditor.setStyleSheet('''QLineEdit {color: black; background-color: pink }''')			
			valid_text = False
		else:			
			valid_text = True

		if not valid_text:
			self.accept_pushButton.setDisabled(True)
			self.accept_pushButton.setToolTip('The name must be at least 4 characters long.\nIt should also not contain invalid characters.')			
			return			

		if text_val:
			if num_characters >= 4: # some arbitrary number to validate a name
				self.accept_pushButton.setDisabled(False)
				self.accept_pushButton.setToolTip('Accept the new item name')
				return
			elif num_characters < 4:
				self.accept_pushButton.setDisabled(True)
				self.accept_pushButton.setToolTip('The name must be at least 4 characters long.\nIt should also not contain invalid characters.')
				return

		self.accept_pushButton.setToolTip('The name must be at least 4 characters long.\nIt should also not contain invalid characters.')
		self.accept_pushButton.setDisabled(True)
		self.textEditor.setFocus()


	def update_ui_unassigned_meshes(self):		
		"""
		Update the list of meshes in the mesh table

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/20/2014 2:30:46 PM
		"""		

		self.get_unassigned_objects()
		if self.unassigned_objects:
			if not self.edit_mode:
				return

			# create the unassigned ui
			if not self.active_unassigned_layout:
				self.create_unassigned_ui()
				self.main_layout.addLayout(self.unassigned_layout)
				self.active_unassigned_layout = True

			if self.active_unassigned_layout:				
				current_selection = pymel.ls(sl=True)

				# get the names of the unassigned items
				if self.item_base_mesh:
					self.unassigned_names = [x.longName() for x in self.unassigned_objects if not x.longName() == self.item_base_mesh.longName()]	
				else:
					self.unassigned_names = [x.longName() for x in self.unassigned_objects]						
				items = [x.nodeName() for x in self.unassigned_objects]
				self.listView.clear()				
				self.listView.addItems(items)
				#self.listView.setFixedSize(250, 200)
				self.listView.setFixedSize(250, self.listView.sizeHintForRow(0) * self.listView.count() + 12 * self.listView.frameWidth())
				self.listView.setCurrentRow(0)

				# reselect
				if current_selection:
					pymel.select(current_selection)

		else:
			if self.active_unassigned_layout:
				self.remove_layout(self.unassigned_layout)
				self.active_unassigned_layout = False

			# Remove the group
			if self.unassigned_group:
				pymel.lockNode(self.unassigned_group, lock=False)
				pymel.delete(self.unassigned_group)
				self.unassigned_group = None


	def update_ui_meshes(self, clear=True):
		"""
		Update the list of meshes in the mesh table

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/20/2014 2:30:46 PM
		"""		

		# update mesh table
		if clear:
			while self.tw_meshes.rowCount():
				self.tw_meshes.removeRow( 0 )

		# get the mesh names
		if self.item_base_mesh:

			# add the first row, base_mesh
			mesh = self.item_base_mesh.nodeName()
			mat_name = None
			mats = rh_maya.get_mesh_materials(self.item_base_mesh)
			if mats:
				if len(mats) == 1:
					mat_name = mats[0].nodeName()		
				elif len(mats) > 1:
					mat_name = 'Multiple'
			if not mat_name:
				print 'Error: Mesh does not have a proper material or it has Too many materials. Exit Edit Mode to Proceed: {0}'.format(mesh)
				
			uvs = pymel.polyUVSet(mesh, q = True, auv = True )
			if uvs:
				num_uvs = str(len(uvs))
			else:
				num_uvs = 'Missing'			
			row_data = {'name':mesh
			            ,'rh_material':mat_name
			            ,'uvs':num_uvs}
			self.do_add_mesh_row(0, row_data)			

			# update some lists
			self.get_material_groups()
			self.get_item_attachments()
			
			row_index = 1
			self.item_mesh_nodes = [self.item_base_mesh]
			for group in self.item_material_groups:
				index = self.get_attribute_value(group, 'rh_item_material_index')
				mat_grp_meshes = self.get_item_material_group_meshes(group)
				for mesh in mat_grp_meshes:
					if not mesh == self.item_base_mesh:

						# don't add an attachment item here
						if self.get_attribute_value(mesh, 'rh_attachment'):
							continue

						mat_name = None
						mats = rh_maya.get_mesh_materials(mesh)
						if mats:
							if len(mats) == 1:
								mat_name = mats[0].nodeName()
							elif len(mats) > 1:
								mat_name = 'Multiple'						
						if not mat_name:
							cmds.warning( 'Error: Mesh does not have a proper material or it has Too many materials. Exit Edit Mode to Proceed: {0}'.format(mesh))
							continue
						uvs = pymel.polyUVSet(mesh, q = True, auv = True )
						if uvs:
							num_uvs = str(len(uvs))
						else:
							num_uvs = 'Missing'					

						self.item_mesh_nodes.append(mesh)
						row_data = {'name':mesh.nodeName()
						            ,'rh_material':mat_name
						            ,'uvs':num_uvs}
						self.do_add_mesh_row(row_index, row_data)
						row_index += 1

			# Add attachments Row
			self.item_attachment_nodes = []
			self.attachment_row_index = None
			if self.item_attachments:
				column_len = 30	
				column_width = 30
				row_data = {'name':'----- Attachments -----' ,'rh_material':'-----------------------' ,'uvs':'------'}
				self.do_add_mesh_row(row_index, row_data)
				self.attachment_row_index = row_index
				row_index += 1
	
				for mesh in self.item_attachments:
					mat_name = None
					mats = rh_maya.get_mesh_materials(mesh)
					if mats:
						if len(mats) == 1:
							mat_name = mats[0].nodeName()
						else:
							mat_name = 'Multiple'
					if not mat_name:
						print 'Error: Mesh does not have a proper material: {0}'.format(mesh)
						continue
					uvs = pymel.polyUVSet(mesh, q = True, auv = True )
					if uvs:
						num_uvs = str(len(uvs))
					else:
						num_uvs = 'Missing'					
	
					self.item_attachment_nodes.append(mesh)
					is_static = self.get_attribute_value(mesh, 'rh_static_mesh')
					if is_static:
						line_name = '(S) {0}'.format(mesh.nodeName())						
					else:
						line_name = '(D) {0}'.format(mesh.nodeName())										
					row_data = {'name':line_name
						        ,'rh_material':mat_name
						        ,'uvs':num_uvs}
					self.do_add_mesh_row(row_index, row_data)
					row_index += 1
			
		self.update_column_widths()		


	def reset_ui(self):
		"""
		Reset the UI

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/26/2014 3:16:05 PM
		"""

		if self.active_edit_mode_layout:
			self.remove_layout(self.edit_mode_layout)
			self.active_edit_mode_layout = False

		# edit ui
		if self.active_edit_layout:
			self.remove_layout(self.edit_layout)
			self.active_edit_layout = False

		# unassigned ui
		if self.active_unassigned_layout:
			self.remove_layout(self.unassigned_layout)
			self.active_unassigned_layout = False

		# utility
		if self.active_utility_layout:
			self.remove_layout(self.utility_layout)
			self.active_utility_layout = False

		# Turn off Item Name Layout
		if self.active_item_name_layout:
			self.remove_layout(self.item_name_layout)
			self.active_item_name_layout = False

		self.setupUi(inital=True)
		self.update_ui()		


	def update_ui(self, initial=False):
		"""
		Main Update UI

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:40:56 PM
		"""	

		if not self.item_node: return	

		# update the list unassigned objects
		if not initial:
			self.update_unassigned_objects()

		# update the item name in the UI
		item_name = self.item_node.getAttr('rh_item_name')
		if not item_name: return
		self.item_name = item_name

		if not self.edit_mode:
			
			if not hasattr(self, 'item_label'):
				return 
			# Update the Item Name UI
			name_font = QtGui.QFont("SansSerif", 20, QtGui.QFont.Bold)
			self.item_label.setText(self.item_name)
			self.item_label.setFont(name_font)
			self.edit_pushButton.is_active = False
			self.edit_pushButton.setStyleSheet('QPushButton {background-color: #black; color: red;}')

			# Turn on Export UI
			if self.can_export:
				if not self.active_export_layout:				
					self.create_export_ui()
					self.main_layout.addLayout(self.export_layout)
					self.active_export_layout = True
					self.export_progress.setVisible(False)
					self.export_output.setVisible(False)
			else:
				if not self.active_no_export_layout:												
					self.create_no_export_ui()
					self.main_layout.addLayout(self.no_export_layout)
					self.active_no_export_layout = True

				if self.active_no_export_layout:
					name_font = QtGui.QFont("SansSerif", 20, QtGui.QFont.Bold)
					self.no_export_label.setText('Export Errors')
					self.no_export_label.setFont(name_font)
					self.error_output.setText(self.export_error_message)
		else:

			'''
			Edit Mode Active
			'''
			name_font = QtGui.QFont("SansSerif", 20, QtGui.QFont.Bold)
			self.edit_mode_label.setText('EDIT MODE')
			self.edit_mode_label.setFont(name_font)
			self.edit_mode_pushButton.is_active = True

			# Make sure the UI exists
			if self.active_edit_layout:

				# Update base mesh name in the UI
				self.base_mesh_text.setText('')
				self.set_mesh_pushButton.setVisible(False)
				if self.item_base_mesh:					
					self.base_mesh_text.setText(self.item_base_mesh.nodeName())
					self.base_mesh_text.setStyleSheet('''QLineEdit {color: Black; background-color: grey }''')					
					self.remove_base_mesh_pushButton.setDisabled(False)
					self.pick_base_mesh_pushButton.setDisabled(True)
					self.add_mesh_text.setStyleSheet('''QLineEdit {color: red; background-color: white }''')
					self.add_bone_combo.setStyleSheet('''QComboBox {color: black; background-color: grey }''')
					self.info_base_mesh_pushButton.setStyleSheet("")
				else:
					self.base_mesh_text.setStyleSheet('''QLineEdit {color: Red; background-color: white }''')
					self.remove_base_mesh_pushButton.setDisabled(True)
					self.pick_base_mesh_pushButton.setDisabled(False)
					self.update_ui_meshes(clear=True)					
					self.add_mesh_text.setStyleSheet('''QLineEdit {color: black; background-color: grey }''')
					self.add_bone_combo.setStyleSheet('''QComboBox {color: black; background-color: grey }''')
					self.info_base_mesh_pushButton.setStyleSheet('''QPushButton {color:black;background-color: green }''')

				# Update the Meshes Table
				if self.item_base_mesh:
					self.update_ui_meshes()
					
					self.add_mesh_label.setVisible(True)
					self.add_mesh_text.setVisible(True)
					self.add_mesh_pushButton.setVisible(True)
					self.remove_mesh_pushButton.setVisible(True)
					self.info_mesh_pushButton.setVisible(True)

					# disable mesh boxes
					self.add_mesh_pushButton.setDisabled(False)
					self.remove_mesh_pushButton.setDisabled(False)
					self.info_mesh_pushButton.setDisabled(False)

					# disable bone boxes
					self.add_bone_pushButton.setDisabled(False)
					self.remove_bone_pushButton.setDisabled(False)
					self.info_bone_pushButton.setDisabled(False)
					if self.active_sel_bone_combo:					
						self.add_bone_combo.setDisabled(False)
					elif self.active_add_bone_text:					
						self.add_bone_text.setDisabled(False)					

				else:
					self.add_mesh_label.setVisible(False)
					self.add_mesh_text.setVisible(False)
					self.add_mesh_pushButton.setVisible(False)
					self.remove_mesh_pushButton.setVisible(False)
					self.info_mesh_pushButton.setVisible(False)
					self.set_mesh_pushButton.setVisible(False)
					
					# disable mesh boxes
					self.add_mesh_pushButton.setDisabled(True)
					self.remove_mesh_pushButton.setDisabled(True)
					self.info_mesh_pushButton.setDisabled(True)

					# disable bone boxes
					self.add_bone_pushButton.setDisabled(True)
					self.remove_bone_pushButton.setDisabled(True)
					self.info_bone_pushButton.setDisabled(True)
					self.add_bone_combo.setDisabled(True)

				# hide all bone ui
				self.add_bone_label.setVisible(False)
				self.add_bone_combo.setVisible(False)
				self.add_bone_pushButton.setVisible(False)
				self.remove_bone_pushButton.setVisible(False)
				self.info_bone_pushButton.setVisible(False)

				# disable sel bone ui
				self.sel_bone_label.setVisible(False)
				self.sel_bone_text.setVisible(False)
				self.sel_bone_pushButton.setVisible(False)
				self.remove_sel_bone_pushButton.setVisible(False)
				self.info_sel_bone_pushButton.setVisible(False)

				# turn off the parent ctrl objects
				self.parent_ctrl_label.setVisible(False)
				self.parent_ctrl_combo.setVisible(False)
				self.parent_ctrl_add_pushButton.setVisible(False)
				self.parent_ctrl_add_pushButton.setDisabled(False)
				self.parent_ctrl_remove_pushButton.setVisible(False)
				self.info_parent_control_pushButton.setVisible(False)

				# turn off the ctrl objects
				self.ctrl_label.setVisible(False)
				self.add_ctrl_text.setVisible(False)
				self.add_ctrl_pushButton.setVisible(False)
				self.remove_ctrl_pushButton.setVisible(False)
				self.info_control_pushButton.setVisible(False)

				self.info_bone_pushButton.setStyleSheet("")
				if not self.temp_bone:

					if self.temp_mesh:
						
						self.set_mesh_pushButton.setVisible(True)
						
						self.info_mesh_pushButton.setStyleSheet("")

						# enable add bone ui
						self.add_bone_label.setVisible(True)
						self.add_bone_combo.setVisible(True)
						self.add_bone_pushButton.setVisible(True)
						self.remove_bone_pushButton.setVisible(True)
						self.info_bone_pushButton.setVisible(True)

						# disable sel bone ui
						self.sel_bone_label.setVisible(False)
						self.sel_bone_text.setVisible(False)
						self.sel_bone_pushButton.setVisible(False)
						self.remove_sel_bone_pushButton.setVisible(False)
						self.info_sel_bone_pushButton.setVisible(False)	
						self.info_bone_pushButton.setStyleSheet('''QPushButton {color:black;background-color: green }''')

						# populate the item bones comboBox
						bones = [x.nodeName() for x in self.item_bones if not x.nodeName() == 'weapon_root']
						self.add_bone_combo_names = bones
						string_list = QStringListModel()
						string_list.setStringList(bones)
						self.add_bone_combo.setModel(string_list)					
						self.remove_bone_pushButton.setDisabled(True)
					else:
						self.info_mesh_pushButton.setStyleSheet('''QPushButton {color:black;background-color: green }''')
				else:

					if self.temp_mesh:
						self.set_mesh_pushButton.setVisible(True)
						self.info_mesh_pushButton.setStyleSheet("")
						self.info_bone_pushButton.setStyleSheet('''QPushButton {color:black;background-color: green }''')
						
						# disable add bone ui
						self.add_bone_label.setVisible(False)
						self.add_bone_combo.setVisible(False)
						self.add_bone_pushButton.setVisible(False)
						self.remove_bone_pushButton.setVisible(False)
						self.info_bone_pushButton.setVisible(False)						

						# enable sel bone ui
						self.sel_bone_label.setVisible(True)
						self.sel_bone_text.setVisible(True)
						self.sel_bone_pushButton.setVisible(True)
						self.remove_sel_bone_pushButton.setVisible(True)
						self.info_sel_bone_pushButton.setVisible(True)	

						# temp bone text
						self.sel_bone_text.setText(self.temp_bone.nodeName())

						if self.add_bone_picked:
							self.add_bone_combo.setStyleSheet('''QLineEdit {color: black; background-color: orange}''')
						else:
							self.add_bone_combo.setStyleSheet('''QLineEdit {color: black; background-color: green}''')

						# turn on the ctrl objects
						self.ctrl_label.setVisible(True)
						self.add_ctrl_text.setVisible(True)
						self.add_ctrl_pushButton.setVisible(True)
						self.remove_ctrl_pushButton.setVisible(True)
						self.info_control_pushButton.setVisible(True)								

						# update the temp ctrl text
						self.remove_ctrl_pushButton.setDisabled(True)
						if self.temp_control:

							# update add ctrl ui
							self.add_ctrl_text.setText(self.temp_control.nodeName())
							self.add_ctrl_text.setStyleSheet('''QLineEdit {color: black; background-color: orange}''')
							self.remove_ctrl_pushButton.setDisabled(False)						

							# turn on the parent ctrl objects
							self.parent_ctrl_label.setVisible(True)
							self.parent_ctrl_combo.setVisible(True)
							self.parent_ctrl_add_pushButton.setVisible(True)
							self.parent_ctrl_add_pushButton.setDisabled(False)
							self.parent_ctrl_remove_pushButton.setVisible(True)
							self.info_parent_control_pushButton.setVisible(True)

							# update the parent ctrl combo box
							self.parent_ctrl_combo.setDisabled(False)							
							self.parent_ctrl_add_control_names = [x.nodeName() for x in self.item_controls if not any([x.nodeName() in self.item_base_ctrls])]
							string_list = QStringListModel()
							string_list.setStringList(self.parent_ctrl_add_control_names)			
							self.parent_ctrl_combo.setModel(string_list)
							if self.parent_ctrl_picked == True:
								self.parent_ctrl_combo.setStyleSheet('''QComboBox {color: black; background-color: orange }''')
								self.info_parent_control_pushButton.setStyleSheet("")
							else:
								self.parent_ctrl_combo.setStyleSheet('''QComboBox {color: black; background-color: green }''')
								self.info_parent_control_pushButton.setStyleSheet('''QPushButton {color:black;background-color: green }''')								
							self.info_control_pushButton.setStyleSheet("")
						else:
							self.info_control_pushButton.setStyleSheet('''QPushButton {color:black;background-color: green }''')
							self.info_parent_control_pushButton.setStyleSheet("")

							# disable add ctrl ui
							self.add_ctrl_text.setText('')
							self.add_ctrl_text.setStyleSheet('''QLineEdit {color: black; background-color: grey}''')

				# Enable Add Mesh Button
				self.set_mesh_pushButton.setDisabled(True)
				self.set_mesh_pushButton.setStyleSheet('''QPushButton {color: black; background-color: grey }''')
				if self.temp_mesh:
					self.add_mesh_text.setText(self.temp_mesh.nodeName())
					self.remove_mesh_pushButton.setDisabled(False)					
					self.add_mesh_text.setStyleSheet('''QLineEdit {color: black; background-color: orange}''')
					self.add_bone_combo.setStyleSheet('''QComboBox {color: black; background-color: green }''')

					# If we have a temp bone we should also have a temp_control
					if not self.temp_bone:
						if self.add_bone_combo.currentText():
							self.set_mesh_pushButton.setDisabled(False)
							self.set_mesh_pushButton.setStyleSheet('''QPushButton {color: black; background-color: green }''')
					else:
						if self.temp_control:
							if self.parent_ctrl_combo.currentText():
								self.set_mesh_pushButton.setDisabled(False)
								self.set_mesh_pushButton.setStyleSheet('''QPushButton {color: black; background-color: green }''')								
						else:
							if self.add_bone_picked:
								self.set_mesh_pushButton.setDisabled(True)
								self.set_mesh_pushButton.setStyleSheet('''QPushButton {color: black; background-color: grey }''')
							else:
								self.set_mesh_pushButton.setDisabled(False)
								self.set_mesh_pushButton.setStyleSheet('''QPushButton {color: black; background-color: green }''')								
								
				else:
					self.add_mesh_text.setText('')
					self.remove_mesh_pushButton.setDisabled(True)					
					self.set_mesh_pushButton.setDisabled(True)

			'''
			UNASSIGNED OBJECTS
			'''
			# populate the unassigned window			
			self.update_ui_unassigned_meshes()			


	def get_attribute_value(self, obj, attribute):
		"""
		Query the given attribute on a given object

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/12/2014 5:42:55 PM
		"""
		if pymel.hasAttr(obj, attribute):
			attr_val = obj.getAttr(attribute)
			return attr_val			
		return None


	def set_attribute_value(self, obj, attr, val):
		"""
		Handle updating attributes on the Item Node

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:40:36 PM
		"""

		pymel.lockNode(obj, lock = False)
		obj.setAttr(attr, lock=False)
		obj.setAttr(attr, val)
		obj.setAttr(attr, lock=True)
		pymel.lockNode(obj, lock = True)


	def update_material_group_indices(self):
		"""
		When material groups have been removed we need to update the indices of the 
		remaining material groups.
		Also, update the item_node material_index

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 3:48:50 PM
		"""

		indexs = []
		grp_indexs = {}
		mat_grps = self.get_material_groups()
		for grp in mat_grps:
			index = self.get_attribute_value(grp, 'rh_item_material_index')
			if not index == None:
				index = int(index)
				if not index == 0:
					if index in indexs:
						cmds.warning('More than one mat group has the same material index.\n\nIndex: {0}\ngrp_indexs'.format(index, grp_indexs))				
					if not index in indexs:
						indexs.append(index)
					grp_indexs[index] = grp

		self.last_material_index = 0	
		def check_groups():
			# now that we have index/grp mapping need to see if there is a gap			
			index = 0
			for idx, grp in sorted(grp_indexs.iteritems()):
				next_index = index + 1
				if not idx == next_index:
					return [next_index, grp]
				index += 1
			self.last_material_index = index
			return None, None

		# loop through the materials for each material and update indice if needbe
		check_num = len(grp_indexs.keys())
		checked_grps = []
		for num in range(0, check_num):
			missing_index, grp = check_groups()
			if missing_index:
				if not grp in checked_grps:
					pymel.lockNode(grp, lock=False)
					grp.setAttr('rh_item_material_index', lock=False)
					grp.setAttr('rh_item_material_index', missing_index)				
					index_string = str( missing_index ).zfill( 2 )		
					pymel.rename(grp, 'Mat_' + index_string)
					grp.setAttr('rh_item_material_index', lock=True)
					pymel.lockNode(grp, lock=True)
					checked_grps.append(grp)					

					# remove item from dictionary
					remove_index = None
					for index, val in grp_indexs.iteritems():
						if val == grp:
							remove_index = index
							break
					if remove_index:
						grp_indexs.pop(remove_index)

					# update the dictionary
					grp_indexs[missing_index] = grp

		if self.last_material_index:
			pymel.lockNode(self.item_node, lock=False)
			self.item_node.setAttr('rh_material_index', lock=False)
			self.item_node.setAttr('rh_material_index', self.last_material_index)
			self.item_node.setAttr('rh_material_index', lock=True)
			pymel.lockNode(self.item_node, lock=True)


	def get_material_groups(self):
		"""
		Get the item material groups

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/13/2014 3:30:37 PM
		"""

		material_groups = []
		material_indexs = []
		mat_grp_dict = {}
		if self.item_mesh_group:
			transform_groups = pymel.ls(self.item_mesh_group, dag=True, type='transform', sn=True)
			mat_groups = [x for x in transform_groups if x.startswith('Mat_')]
			for mat_grp in mat_groups:
				material_index = self.get_attribute_value(mat_grp, 'rh_item_material_index')
				if not material_index is None:
					mat_grp_dict[material_index] = mat_grp					
					if not material_index in material_indexs:
						material_indexs.append(material_index)
					else:
						cmds.confirmDialog(t='Item Material Groups: Issue', m='There are multiple groups with the same material index. This is badd!!!')

			# get the sorted material groups
			for idx, grp in sorted(mat_grp_dict.iteritems()):
				material_groups.append(grp)

		self.item_material_groups = material_groups
		return material_groups


	def get_material_group(self, index=0):
		"""
		Get the material group by index or mesh

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/12/2014 5:01:25 PM
		"""	
		
		if not self.item_material_groups:
			self.get_material_groups()

		if self.item_material_groups:		
			for mat_grp in self.item_material_groups:
				index_val = self.get_attribute_value(mat_grp, 'rh_item_material_index')
				if not index_val is None:
					if int(index_val) == index:
						return mat_grp

		return None
	
	
	def is_item_mesh(self, obj):
		"""
		Determine if an item is improperly unassigned
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 2/9/2018 9:47:29 AM
		"""
		
		if rh_maya.get_mesh_shape(obj):
			if self.get_attribute_value(obj, 'rh_item') or self.get_attribute_value(obj, 'rh_weapon'):
				# find the appropriate Mat Group
				if self.item_material_groups:
					# want to determine the primary material, usually the first one or most assigned faces
					mat_dict = rh_maya.get_mesh_materials(obj, info=True)										
					if mat_dict:
						print 'Obj: {0}'.format(obj)
						for mat, faces in mat_dict.iteritems():							
							print ' {0}'.format(mat)													
		

	def get_unassigned_objects(self):
		"""
		Enter a description of the function here.

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/18/2014 9:09:42 PM
		"""

		objs = []
		if self.unassigned_group:
			c_objs = pymel.listRelatives(self.unassigned_group, type='transform', c=True, ad=True)
			for obj in c_objs:
				if rh_maya.get_mesh_shape(obj):
					if not obj in objs:
						objs.append(obj)					

		self.unassigned_objects = objs
		return objs


	def get_material_group_meshes(self, index, quiet=True):
		"""
		Get all the meshes under a material group

		*Arguments:*
			* ``index`` material grp index

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/13/2014 11:03:32 AM
		"""

		if not self.item_meshes:
			self.get_item_meshes()
			
		if not self.item_meshes:
			if not quiet:
				cmds.warning('There are no item meshes')
			return []
		
		# if given a mat_group convert to the mat_grp index
		if not isinstance(index, int):
			if isinstance(index, float):
				index = int(index)
			else:
				index = self.get_attribute_value(index, 'rh_item_material_index')			

		mat_group = self.get_material_group(index=index)
		if not mat_group:
			if not quiet:
				cmds.warning('You should not be able to query a group that doesnt exist.\n Material Group Index: {0}'.format(index))
			return []

		mat_group_meshes = []
		for mesh, parent_group in self.item_meshes.iteritems():
			if parent_group == mat_group:
				mat_group_meshes.append(mesh)			

		return mat_group_meshes


	def get_item_bone(self, bone_name, index = None):
		"""
		Get a item bone from the Item

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:40:09 PM
		"""

		item_bone = None
		item_prefix = '{0}_'.format(self.item_type.lower())
		try:
			joint_name = item_prefix + bone_name
			item_bone = pymel.PyNode(joint_name)
		except:
			pass
		return item_bone


	def get_material_group_by_material(self, mats):
		"""
		Get a item material group by material

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/4/2014 5:36:33 PM
		"""

		self.item_material_groups = self.get_material_groups()		
		for mat_group in self.item_material_groups:
			if mat_group.hasAttr('rh_material'):
				materials = self.get_attribute_value(mat_group, 'rh_material')
				if len(mats) > 1:				
					failed_mats = False
					for mat in mats:						
						if not mat in materials:
							failed_mats = True
							break
					if not failed_mats:
						if sorted(mats) == sorted(materials):
							return mat_group
				else:
					if mats[0] in materials:				
						return mat_group

		return None


	def get_item_materials(self):
		"""
		Get all the Item Mat_Group materials

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/13/2014 10:48:44 AM
		"""

		item_materials = {}

		# get the item material groups
		self.item_material_groups = self.get_material_groups()		
		for mat_group in self.item_material_groups:
			if mat_group.hasAttr('rh_material'):
				materials = self.get_attribute_value(mat_group, 'rh_material')
				material_index = self.get_attribute_value(mat_group, 'rh_item_material_index')
				if materials:
					item_materials[material_index] = [materials, mat_group]
			else:
				pymel.lockNode(mat_group, lock=False)
				pymel.lockNode(self.unassigned_group, lock=False)
				pymel.parent(mat_group, self.unassigned_group)
				pymel.lockNode(mat_group, lock=True)
				pymel.lockNode(self.unassigned_group, lock=False)

		# material_index, [material,material_group]
		self.item_materials = item_materials
		return item_materials


	def get_item_mesh_group(self):
		"""
		Get the Item Node mesh_grp

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:39:55 PM
		"""

		mesh_grp = None
		if self.item_node:
			try:
				mesh_grp = self.item_node.getAttr('rh_mesh_grp')
			except:
				cmds.warning('The item has no MESH_grp.')		

		self.item_mesh_group = mesh_grp
		return mesh_grp


	def get_item_controls(self):
		"""
		Get the animation controls under the item rig_grp

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/16/2014 2:23:16 PM
		"""		
		item_controls = []
		if self.item_node:
			rig_grp = None
			try:
				rig_grp = self.item_node.getAttr('rh_rig_grp')
			except:			
				cmds.warning('The item has no rig_grp.')

			if rig_grp:
				controls = pymel.ls(rig_grp, dag=True, type='transform')
				for ctrl in controls:
					if rh_maya.get_mesh_shape(ctrl):						
						if ctrl.hasAttr(self.item_type_attr):
							item_controls.append(ctrl)							

		self.item_controls = item_controls
		return item_controls	


	def get_item_bones(self):
		"""
		Get the bones under the item root

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/16/2014 2:23:16 PM
		"""

		item_bones = []
		item_bone_names = []
		item_bone_indices = []
		index_error_msg =''
		name_error_msg = ''
		if self.item_node:
			root_bone = None
			try:
				root_bone = self.item_node.getAttr('rh_item_root')
			except:			
				cmds.warning('The item has no root_bone.')

			ignore_bones = ['weapon_root','item_root','offset','root','ground']
			if root_bone:
				bones = pymel.ls(root_bone, dag=True, type='joint')
				for bone in bones:
					if not bone.nodeName() in ignore_bones:						
						if bone.hasAttr(self.item_type_attr):
							item_bones.append(bone)

							# check for dupe indices
							bone_index = self.get_attribute_value(bone, 'rh_item_bone_index')
							if bone_index:
								if bone_index in item_bone_indices:
									index_error_msg += '  Bone: {0}  Index: {1}'.format(bone.longName(), bone_index)
								else:
									item_bone_indices.append(bone_index)

							# check for dupe names
							if bone.nodeName() in item_bone_names:
								name_error_msg += '  Bone: {0}'.format(bone.longName())
							else:
								item_bone_names.append(bone.nodeName())

		show_error = False
		error_msg = 'There were issues with the item bones!'
		if index_error_msg:
			error_msg += '\n\nThese bones have assigned index values that are already used:\n' + index_error_msg
			show_error = True
		if name_error_msg:
			error_msg += '\n\nThese bones have names that exist in other parts of the hierarchy:\n' + name_error_msg
			show_error = True

		if show_error:
			cmds.confirmDialog(t='Item Rigger: Error', m=error_msg)

		self.item_bones = item_bones
		return item_bones


	def get_mesh_material_group(self, mesh):
		"""
		Given a mesh return the material group

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/16/2014 3:12:09 PM
		"""	

		for group in self.item_material_groups:
			index = self.get_attribute_value(group, 'rh_item_material_index')
			mat_grp_meshes = self.get_item_material_group_meshes(group)
			if mesh in mat_grp_meshes:
				return group

		return None	

	def get_item_material_group_meshes(self, mat_grp):
		"""
		Get meshes straight from the material group

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/20/2014 6:44:20 PM
		"""		

		# get the actual item meshes	
		mat_grp_meshes = []
		if mat_grp:
			transforms = pymel.ls(mat_grp, dag=True, type='transform', sn=True)
			for transform in transforms:
				if rh_maya.get_mesh_shape(transform):					
					if self.get_attribute_value(transform, self.item_type_attr):
						mat_grp_meshes.append(transform)

		self.item_material_group_meshes = mat_grp_meshes			
		return mat_grp_meshes


	def get_item_attachments(self):
		"""
		Get the meshes that are set as attachments

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/3/2014 10:11:44 AM
		"""

		attachments = []
		attachment_names = []
		if self.item_meshes is None:
			return None
		
		for mesh in self.item_meshes:
			attachment = self.get_attribute_value(mesh, 'rh_attachment')
			if attachment:
				attachments.append(mesh)
				attachment_names.append(mesh.nodeName())

		self.item_attachments = attachments
		self.item_attachment_names = attachment_names
		return self.item_attachments


	def get_item_meshes(self):
		"""
		Get the meshes in Item Node mesh_grp

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:39:55 PM
		"""

		item_meshes = {}
		self.unassigned_group = None

		# get the object group to throw meshes in that don't belong
		unassigned_string = '_UNASSIGNED_'
		if not pymel.objExists(unassigned_string):
			self.unassigned_group = pymel.group(empty=True, n=unassigned_string)
			rh_maya.lock_channels(self.unassigned_group)
			rh_maya.hide_channels(self.unassigned_group)
			self.unassigned_group.setAttr('v', keyable=False)			

		else:
			self.unassigned_group = pymel.PyNode(unassigned_string)
			pymel.lockNode(self.unassigned_group, lock=False)

		if not self.unassigned_group:			
			cmds.warning('Failed to get or create the Item _UNASSIGNED_ grp')
			return None
		else:
			pass
		
		# check the unassigned group for actual weapon meshes
		if self.unassigned_group:
			self.unassigned_objects = self.get_unassigned_objects()
			if self.get_unassigned_objects():
				for obj in self.unassigned_objects:
					if self.item_base_mesh:
						if obj == self.item_base_mesh:
							cmds.warning('There are issues with the rig!!')
							return							

		# get the actual item meshes
		if self.item_mesh_group:
			transforms = pymel.ls(self.item_mesh_group, dag=True, type='transform', sn=True)
			for transform in transforms:
				if rh_maya.get_mesh_shape(transform):
					if self.get_attribute_value(transform, self.item_type_attr):

						# need to see if it has Bone/Control attrs assigned
						# if it has attrs but nothing assigned it was probably duplicated so move it
						if self.item_base_mesh:
							if not transform == self.item_base_mesh:
								if pymel.hasAttr(transform, 'rh_mat_group'):
									val = transform.getAttr('rh_mat_group')
									connection = pymel.PyNode(transform.longName()+'.rh_mat_group')
									if not val:									
										pymel.lockNode(transform, lock=False)
										transform.setAttr(self.item_type_attr, lock=False)		
										transform.deleteAttr(self.item_type_attr)
										pymel.parent(transform, self.unassigned_group)
										continue

						# item meshes should have a skincluster
						if not pymel.listHistory(transform, type='skinCluster'):
							pymel.lockNode(transform, lock=False)
							pymel.parent(transform, self.unassigned_group)
							cmds.warning('Item mesh no longer has a skincluster!\n\nMoving mesh to the "_UNASSIGNED_" group to be fixed.\n\n: {0}'.format(transform.nodeName()))

						# get the parent and store it with the mesh
						parent = pymel.listRelatives(transform, p=True)
						if parent:
							parent=parent[0]
						else:
							parent = None					
						item_meshes[transform] = parent
					else:
						pymel.lockNode(transform, lock=False)
						pymel.parent(transform, self.unassigned_group)

		# lock the nodes	
		if not self.get_unassigned_objects():
			pymel.lockNode(self.unassigned_group, lock=False)
			pymel.delete(self.unassigned_group)
			self.unassigned_group = None
		else:
			if not self.edit_mode:
				pymel.lockNode(self.unassigned_group, lock=True)		

		self.item_meshes = item_meshes
		return item_meshes	


	def validate_modified_meshes(self):
		"""
		Make sure meshese that may have been modified are handled properly

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/11/2014 1:01:50 PM
		"""

		# bake skinned meshes
		self.item_meshes = self.get_item_meshes()
		if not self.item_meshes:			
			return 
		
		for mesh in self.item_meshes.keys():
			pymel.lockNode(mesh, lock=False)

			# check for non-deformer history and delete
			shape = rh_maya.get_mesh_shape(mesh)
			has_polyblind_data = False
			if shape:
				nonDeformerHistoryNodes  = [n for n in shape.history(il=1, pdo = True) if not isinstance(n, pymel.nodetypes.GeometryFilter)]
				if nonDeformerHistoryNodes :
					nonDeformerHistoryNodes  = list(set(nonDeformerHistoryNodes))
					bake_non_history = False
					for node in nonDeformerHistoryNodes:					
						if not type(node) == pymel.nodetypes.PolyBlindData:
							print 'Shape has NonDeformerHistory: {0}'.format(node.nodeName())
							bake_non_history = True
							break

					if bake_non_history:
						print 'Baking NonDeformerHistory on Shape: {0}'.format(shape.nodeName())
						cmds.bakePartialHistory(shape.longName(),prePostDeformers=True )

			pymel.lockNode(mesh, lock=True)		


	def on_toggle_edit_mode(self, edit=True, changed=False):
		"""
		Handle toggling Edit Mode
		Hiding and Enabling UI layouts

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:39:35 PM
		"""

		# need to check things again
		if not self.first_toggle:
			self._init_item_()
		else:
			self.first_toggle = False

		pymel.waitCursor( state = True )		

		if edit:
			
			if not self.item_node:
				cmds.warning('No item node found in scene! Restart!')
				return

			# toggle edit mode attribute
			pymel.lockNode(self.item_node, lock=False)
			self.item_node.setAttr('rh_item_edit', lock=False)
			self.item_node.setAttr('rh_item_edit', True)
			self.item_node.setAttr('rh_item_edit', lock=True)
			pymel.lockNode(self.item_node, lock=True)

			# Turn off Item Name Layout
			if self.active_item_name_layout:
				self.remove_layout(self.item_name_layout)
				self.active_item_name_layout = False

			# Turn off Export layout
			if self.active_export_layout:
				self.remove_layout(self.export_layout)
				self.active_export_layout = False

			# Turn off No Export Layout
			if self.active_no_export_layout:
				self.remove_layout(self.no_export_layout)
				self.active_no_export_layout = False

			# Turn on Edit Mode Layout
			self.create_edit_mode_ui()
			self.main_layout.addLayout(self.edit_mode_layout)		
			self.active_edit_mode_layout = True

			# Turn on Edit Layout
			self.create_edit_item_ui()
			self.main_layout.addLayout(self.edit_layout)
			self.active_edit_layout = True			

			# Turn on Unassigned Layout
			if self.get_unassigned_objects():
				self.create_unassigned_ui()
				self.main_layout.addLayout(self.unassigned_layout)
				self.active_unassigned_layout = True

			# Turn on Utility Layout
			self.create_utilities_ui()
			self.main_layout.addLayout(self.utility_layout)
			self.active_utility_layout = True			


		else:

			# toggle item edit attribute
			pymel.lockNode(self.item_node, lock=False)
			self.item_node.setAttr('rh_item_edit', lock=False)
			self.item_node.setAttr('rh_item_edit', False)
			self.item_node.setAttr('rh_item_edit', lock=True)
			pymel.lockNode(self.item_node, lock=True)

			# bake skinweighting of all meshes			
			self.validate_modified_meshes()			

			# edit mode ui
			if self.active_edit_mode_layout:
				self.remove_layout(self.edit_mode_layout)
				self.active_edit_mode_layout = False

			# edit ui
			if self.active_edit_layout:
				self.remove_layout(self.edit_layout)
				self.active_edit_layout = False

			# unassigned ui
			if self.active_unassigned_layout:
				self.remove_layout(self.unassigned_layout)
				self.active_unassigned_layout = False

			# utility
			if self.active_utility_layout:
				self.remove_layout(self.utility_layout)
				self.active_utility_layout = False

			# Turn on Item Name UI
			self.create_item_name_ui()
			self.main_layout.addLayout(self.item_name_layout)
			self.active_item_name_layout = True

			if self.can_export:
				self.create_export_ui()
				self.main_layout.addLayout(self.export_layout)
				self.active_export_layout = True
				self.export_progress.setVisible(False)
				self.export_output.setVisible(False)
			else:
				self.create_no_export_ui()
				self.main_layout.addLayout(self.no_export_layout)
				self.active_no_export_layout = True

		# lock/unlock nodes
		self.do_lock_item_nodes(lock=True, query=False)
		if self.item_bones:
			rh_maya.disable_segment_compensate_scale(joints=self.item_bones)

		self.update_ui()
		pymel.waitCursor( state = False )


	def do_item_skin_mesh(self, bones, mesh):
		"""
		Skin the item mesh with a given list of bones

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/12/2014 5:31:55 PM
		"""

		do_skin = rh_maya.skin_mesh(bones, mesh)
		if do_skin:
			return True		
		return False


	def clean_item_mat_groups(self):
		"""
		Remove material groups that no longer have meshes
		Warn the user

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 3:45:29 PM
		"""

		removed_groups=[]
		did_remove = False
		
		if not self.item_material_groups:
			mat_groups = self.get_material_groups()
		
		# find mat groups without meshes
		if self.item_material_groups:
			num_mat_groups = len(self.item_material_groups)
		for mat_grp in self.item_material_groups:
			index = self.get_attribute_value(mat_grp, 'rh_item_material_index')
			if index:
				meshes = self.get_material_group_meshes(index)
				if not meshes:
					removed_groups.append(mat_grp)

		new_num_mat_groups = len(self.get_material_groups())

		# delete empyt mat groups
		if len(removed_groups) > 0:
			did_remove = True
			for mat_grp in removed_groups:
				pymel.lockNode(mat_grp, lock=False)
				pymel.delete(mat_grp)

		if did_remove:
			msg = 'WARNING::\n\nYou have removed meshes from the item, which resulted in Material Groups that have been removed!  This could likely result in scrambled materials in game.\n\nMake sure your materials in game are not mixed up after exporting!'
			cmds.confirmDialog(t='Item Mat Groups Removed',m=msg)


	def _init_item_(self):
		"""
		Get all attribute objects on the item for later inspection

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/13/2014 11:11:32 AM
		"""

		# get the item node
		if pymel.objExists('Weapon'):
			item_node = pymel.PyNode('Weapon')
			if pymel.hasAttr(item_node, 'rh_item_data'):
				self.item_node = item_node
				self.item_type = 'Weapon'
			elif pymel.hasAttr(item_node, 'rh_weapon_data'):
				self.item_node = item_node
				self.item_type = 'Weapon'
				
		elif pymel.objExists('Vehicle'):
			item_node = pymel.PyNode('Vehicle')
			if pymel.hasAttr(item_node, 'rh_item_data'):
				self.item_node = item_node			
				self.item_type = 'Vehicle'

		# get the item name
		if not self.item_node:			
			return
			
		# item node name
		item_name = self.get_attribute_value(self.item_node, 'rh_item_name')
		if item_name:
			self.item_name = item_name
			
		# check legacy name/version
		if not item_name:
			item_name = self.get_attribute_value(self.item_node, 'rh_weapon_name')
			if item_name:
				self.item_name = item_name
				
		# get the base mesh
		self.item_base_mesh = self.get_attribute_value(self.item_node, 'rh_mesh_base')			
		
		# get the item mesh_grp
		self.get_item_mesh_group()		
		
		# get the item meshes
		self.get_item_meshes()			
		
		# get the item material groups
		self.get_material_groups()

		# get the item materials
		self.get_item_materials()		

		# get the meshes that are attachments
		self.get_item_attachments()

		# get the item bones
		self.get_item_bones()

		# get the item controls
		self.get_item_controls()

		# check bone parents
		self.check_bone_parents()	

		# check outlying meshes/groups/transforms
		self.update_unassigned_objects()

		# clean out empty Mat Groups
		self.clean_item_mat_groups()

		# clean mesh shapes
		self.clean_multiple_shape_nodes()

		# Re-Index MatGroups when ones have been removed
		self.update_material_group_indices()

		# remove the empty group if there is nothing in there
		if not self.unassigned_objects:
			if self.unassigned_group:
				pymel.lockNode(self.unassigned_group, lock=False)
				pymel.delete(self.unassigned_group)
				self.unassigned_group = None

		# can export
		if not self.edit_mode:
			self.do_check_can_export()


	def check_bone_parents(self):
		"""
		Make sure the parents of item bones have not changed

		*Arguments:*
			* ``(None)`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/18/2014 5:27:49 PM
		"""

		bones = self.get_item_bones()
		for bone in bones:
			parent_attr = self.get_attribute_value(bone, 'rh_parent')
			if parent_attr:
				current_parent = pymel.listRelatives(bone, p=True)
				if current_parent:
					current_parent = current_parent[0]
					if not parent_attr == current_parent:
						error_msg = 'This bone parent has been changed from when it was originally defined.\n\
						This could have unexpected results!\n\n Bone: {0}\n Parent: {1}\n Original Parent: {2}'.format(bone.nodeName(), current_parent.nodeName(), parent_attr.nodeName())
						print error_msg
						cmds.warning(error_msg)


	def update_unassigned_objects(self):
		"""
		Look for rogue objects in the scene and move to unassigned

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 10:50:22 AM
		"""		

		unassigned_objs = []
		non_item_objs = []
		if not pymel.objExists('_UNASSIGNED_'):
			self.unassigned_group = pymel.group(empty=True, n='_UNASSIGNED_')

		# get all objects not under/assigned to the item
		ignore_nodes = ['front','persp','side','top']
		if self.item_node:
			item_nodes = pymel.ls(self.item_node, dag=True, type='transform')		
			scene_objects = pymel.ls(type='transform')

			# get all the objs not in item nodes
			for obj in scene_objects:
				if not obj == self.unassigned_group:
					if not obj in item_nodes:					
						non_item_objs.append(obj)

			# see if a top-level parent of the current object is in the objs list, then remove it
			for obj in non_item_objs:
				if not obj.nodeName() in ignore_nodes:
					obj_parent = rh_maya.get_obj_parent(obj)
					if obj_parent:
						if not obj_parent == obj:
							if not obj_parent == self.unassigned_group:
								if not obj_parent in non_item_objs:
									unassigned_objs.append(obj)
							else:
								pymel.lockNode(obj, lock=False)
						else:
							unassigned_objs.append(obj)
					else:
						unassigned_objs.append(obj)


		# move the nodes under the unassigned group
		if unassigned_objs:				
			pymel.lockNode(self.unassigned_group, lock=False)
			for obj in unassigned_objs:
				pymel.lockNode(obj, lock=False)
				if obj.hasAttr(self.item_type_attr):
					obj.setAttr(self.item_type_attr, lock=False)
					obj.deleteAttr(self.item_type_attr)				
				pymel.parent(obj, self.unassigned_group)

		# clean out empty groups
		empty_groups = []
		objs = pymel.ls(self.unassigned_group, dag=True, type='transform')
		for obj in objs:
			if not obj == self.unassigned_group:
				obj_children = pymel.listRelatives(obj, c=True, ad=True)
				if not obj_children:
					if not pymel.nodeType(obj) == 'joint':
						has_shape = rh_maya.get_mesh_shape(obj)
						if not has_shape:
							empty_groups.append(obj)			
		if empty_groups:
			pymel.delete(empty_groups)

		# update the unassigned objects list
		self.get_unassigned_objects()
		if not self.unassigned_objects:
			if self.unassigned_group:
				pymel.lockNode(self.unassigned_group, lock=False)
				pymel.delete(self.unassigned_group)
				self.unassigned_group = None
			else:
				pymel.lockNode(self.unassigned_group, lock=True)		


	def do_lock_item_nodes(self, nodes=[], lock=True, query=False):
		"""
		Lock all item nodes

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/18/2014 5:15:34 PM
		"""

		lock_nodes = []
		if nodes:
			lock_nodes = nodes

		if not lock_nodes:
			if self.item_node:
				lock_nodes.append(self.item_node)
			else:
				return

			if self.item_mesh_group:
				lock_nodes.append(self.item_mesh_group)

			if self.item_base_mesh:
				lock_nodes.append(self.item_base_mesh)

			if self.item_materials:
				mats = []
				for mat,mat_grp in self.item_materials.itervalues():
					mats.append(mat)
				lock_nodes.extend(mats)

			if self.item_material_groups:
				lock_nodes.extend(self.item_material_groups)			

			if self.item_meshes:			
				lock_nodes.extend(self.item_meshes.keys())		

			if self.item_bones:
				lock_nodes.extend(self.item_bones)

			if self.item_controls:
				lock_nodes.extend(self.item_controls)

			self.all_item_nodes = lock_nodes
			if query:
				return self.all_item_nodes()

		# lock the nodes
		root_nodes = ['weapon_root','item_root','root','weapon_root_anim']
		for node in lock_nodes:			
			try:				
				# dont lock the root bone nodes, they are connected to and updated in weapon connection anim scenes
				if node.nodeName() in root_nodes and lock:
					continue
				pymel.lockNode(node, lock=lock)					
			except:
				pass

		return lock_nodes


	def clean_multiple_shape_nodes(self):
		"""
		Some processes may introduce multiple intermediate shape nodes

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/16/2014 2:18:26 PM
		"""

		all_bad_shapes = {}
		if not self.item_meshes:
			self.get_item_meshes()
			
		if self.item_meshes:
			for mesh in self.item_meshes:
				shapes = mesh.getShapes()
				intermediate_shape = None			
				bad_shapes = []
				for shape in shapes:
					if pymel.hasAttr(shape, 'intermediateObject'):
						if shape.getAttr('intermediateObject'):
							connections = pymel.listConnections(shape)
							if connections:							
								pass
							else:
								bad_shapes.append(shape)					
	
				if bad_shapes:
					all_bad_shapes[mesh] = bad_shapes

		if all_bad_shapes:
			for mesh, shapes in all_bad_shapes.iteritems():
				print 'MESH Has Duplicate Shapes: {0}\n {1}'.format(mesh.nodeName(), shapes)				
				pymel.delete(shapes)			


	def validate_item_meshes(self):
		"""
		On many actions including inti we need to validate the meshes to ensure they have not been messed with

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/12/2014 5:10:30 PM
		"""

		all_valid = True
		mesh_errors = 'MESH ERRORS:\n'
		if not self.item_meshes:
			self.get_item_meshes()
			
		if self.item_meshes:
			for mesh in self.item_meshes:
				if pymel.objExists(mesh):
					is_valid, mesh, material, error_msg = self.validate_mesh(mesh=mesh)
					if not is_valid:
						all_valid = False
						mesh_errors += '{0}'.format(error_msg)
		else:
			return False, 'MESH ERRORS:\n No item meshes found!'

		if not all_valid:
			return False, mesh_errors
		else:
			return True, ''				

		#vert_num = cmds.polyEvaluate(mesh, vertex=True)
		#face_num = cmds.polyEvaluate(mesh, faces=True)

		# make sure the meshes have only singular materials
		# make sure the meshes are sorted into the correct material groups


	def check_transforms(self, mesh):
		"""
		Check the transforms of the mesh up to the parent
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/6/2014 3:52:32 PM
		"""
		
		selection = pymel.ls(sl=True)
		mesh_parent = rh_maya.get_obj_parent(mesh)
		if mesh_parent.nodeName() == '_UNASSIGNED_':
			mesh_parent = rh_maya.get_obj_parent(mesh, parent_before='_UNASSIGNED_')
			
		if mesh_parent in self.item_meshes.keys():
			return
			
		if mesh_parent:			
			
			# unlock mesh parent channels
			pymel.lockNode(mesh_parent, lock=False)
			if not mesh_parent.isLocked():
				rh_maya.lock_channels(mesh_parent, lock=False)
			
			# unlock mesh parent and all children and channels
			children = mesh_parent.listRelatives(c=True, ad=True, type='transform')
			for child in children:
				if child.getShapes():
					pymel.lockNode(child, lock=False)
					if not child.isLocked():
						rh_maya.lock_channels(child, lock=False)
						
			# freeze parent
			try:
				pymel.select(cl=True)
				pymel.select(mesh_parent)
				cmds.makeIdentity( apply=True, translate=True, rotate=True, scale=True, n=False )
			except:
				cmds.warning('Failed to freeze transforms on the mesh: {0}'.format(mesh.nodeName()))
				
		else:
			# unlock the mesh
			pymel.lockNode(mesh, lock=False)
			if not mesh.isLocked():
				rh_maya.lock_channels(mesh, lock=False)			
			
			# freeze mesh
			try:
				pymel.select(cl=True)
				pymel.select(mesh)
				cmds.makeIdentity( apply=True, translate=True, rotate=True, scale=True, n=False )
			except:
				cmds.warning('Failed to freeze transforms on the mesh: {0}'.format(mesh.nodeName()))		
			

	def validate_mesh(self, mesh=None, is_base=False):
		"""
		Validate a mesh selection

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/13/2014 10:40:11 AM
		"""

		error_msg = ''
		if not mesh:
			# validate the selection
			selection = pymel.ls(sl=True, type='transform')
			if not len(selection) == 1:
				error_msg = 'Validating Mesh Error:\n'
				error_msg += 'You must select a single mesh object!'				
				cmds.warning(error_msg)
				return False, None, None, error_msg
			mesh = selection[0]
		else:
			error_msg = 'Validating Mesh: {0}\n'.format(mesh.nodeName())			
		
		# make sure the selection has an actual mesh shape		
		mesh_shape = rh_maya.get_mesh_shape(mesh)
		if not mesh_shape:
			error_msg += 'You must select a single mesh object.\nThis object has no shape!'
			cmds.warning(error_msg)
			return False, None, None, error_msg

		# make sure the name isnt bad
		valid_name = rh_maya.validate_text(mesh.nodeName(), numbers=True)
		if not valid_name:
			error_msg += 'The selected mesh has invalid characters in the name.\nEx: "-,spaces,numbers".\n\nPlease fix then add again!\n\nMesh: {0}'.format(mesh.nodeName())
			cmds.warning(error_msg)
			return False, None, None, error_msg

		# validate the actual mesh
		valid_mesh, error = rh_maya.validate_mesh(mesh, mesh_type='Weapon', uv_num=2)
		if not valid_mesh:
			error_msg += error
			cmds.warning(error_msg)
			return False, None, None, error_msg		

		# make sure the mesh only has a single material applied
		mesh_materials = rh_maya.get_mesh_materials(mesh)
		if mesh_materials:
			pass			
		else:
			error_msg += '\nYour mesh has no materials assigned.\nThis object is likely not a mesh.'
			return False, None, None, error_msg

		# make sure the mesh isnt already under the mesh grp
		return True, mesh, mesh_materials, error_msg


	def on_open_tw_meshes_menu(self, position):
		"""
		Open the menu

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 2:26:45 PM
		"""

		row_index = self.tw_meshes.currentRow()
		col_index = self.tw_meshes.currentColumn()
		mesh_types = ['(S)','(D)']

		node = None			
		try:
			# trying to get the name
			if col_index == 2:				
				item = self.tw_meshes.item(row_index, 0)
			else:
				item = self.tw_meshes.item(row_index, col_index)			
				
			# if its multiple materials graph material on the mesh object
			item_name = item.data(0)
			if col_index == 1:
				if item_name == 'Multiple':
					item = self.tw_meshes.item(row_index, 0)
					item_name = item.data(0)
					
			split_paren = item_name.split(') ')
			if len(split_paren) > 1:
				item_name = split_paren[1]			
		except:
			item_name = None		
		
		try:	
			current_item = self.tw_meshes.currentItem()
			name = current_item.data(0)
		except:
			name = None
		if name:											
			if cmds.objExists(name):
				node = pymel.PyNode(name)	

		if not col_index == 2:
			current_item = self.tw_meshes.currentItem()
			if current_item:
				name = current_item.data(0)				
				if name:
					split_name = name.split(') ')				
					if len(split_name) > 1:
						name = split_name[1]
					if cmds.objExists(name):
						node = pymel.PyNode(name)
		else:
			current_item = self.tw_meshes.item(row_index, 0)
			if current_item:
				name = current_item.data(0)
				if name:											
					if cmds.objExists(name):
						node = pymel.PyNode(name)

		if not node:
			if item_name:
				if cmds.objExists(item_name):
					node = pymel.PyNode(item_name)					

		# remove selected item mesh
		if col_index == 0:
			if row_index == 0:
				return False
			if node:
				if self.item_base_mesh:
					if node == self.item_base_mesh:
						return False

				def paint_cmd():
					try:
						maya.mel.eval('artAttrSkinPaintCtx artAttrSkinPaintCtx1;setToolTo artAttrSkinPaintCtx1;')
					except:
						pass

				self.tw_menu = QMenu(self)
				select_action = QAction('Remove Item Mesh', self)
				select_action.triggered.connect(lambda: self.on_pressed_remove_mesh())
				self.tw_menu.addAction(select_action)
				self.tw_menu.popup(QCursor.pos())
				
				# only show menu for items not already attachments
				show_attach_flag = False
				if self.attachment_row_index:					
					if row_index < self.attachment_row_index:
						show_attach_flag = True
				else:
					show_attach_flag = True
						
				if show_attach_flag:					
					attach_action = QAction('Flag Mesh As Attachment', self)
					attach_action.triggered.connect(lambda: self.on_pressed_set_mesh_attachment())
					self.tw_menu.addAction(attach_action)
					self.tw_menu.popup(QCursor.pos())
					
					
				# remove flag as attachment
				# only show menu for items not already attachments
				show_unattach_flag = False
				if self.attachment_row_index:					
					if row_index > self.attachment_row_index:
						show_unattach_flag = True
			
				if show_unattach_flag:					
					unattach_action = QAction('UnFlag Mesh As Attachment', self)
					unattach_action.triggered.connect(lambda: self.on_pressed_remove_mesh_attachment())
					self.tw_menu.addAction(unattach_action)
					self.tw_menu.popup(QCursor.pos())
					
					# separator
					self.tw_menu.addSeparator()

					is_static = self.get_attribute_value(node, 'rh_static_mesh')					
					if not is_static:
						# flag mesh as static
						static_mesh_action = QAction('Set Attachment as Static Mesh', self)
						static_mesh_action.triggered.connect(lambda: self.on_pressed_set_mesh_static(1))
						self.tw_menu.addAction(static_mesh_action)
						self.tw_menu.popup(QCursor.pos())					
					else:
						# flag mesh as skeletal
						skeletal_mesh_action = QAction('Set Attachment as Deformable Mesh', self)
						skeletal_mesh_action.triggered.connect(lambda: self.on_pressed_set_mesh_static(0))
						self.tw_menu.addAction(skeletal_mesh_action)
						self.tw_menu.popup(QCursor.pos())									

				#paint_action = QAction('Paint Skin Mesh', self)
				#paint_action.triggered.connect(lambda: paint_cmd())
				#self.tw_menu.addAction(paint_action)
				#self.tw_menu.popup(QCursor.pos())							

		# select and graph material in hypershade
		if col_index == 1:
			if not node:
				if item_name:					
					if cmds.objExists(item_name):
						self.tw_menu = QMenu(self)
						select_action = QAction('Graph Material', self)
						select_action.triggered.connect(lambda: self.on_pressed_material_hypershade())
						self.tw_menu.addAction(select_action)
						self.tw_menu.popup(QCursor.pos())
			else:
				self.tw_menu = QMenu(self)
				select_action = QAction('Graph Material', self)
				select_action.triggered.connect(lambda: self.on_pressed_material_hypershade())
				self.tw_menu.addAction(select_action)
				self.tw_menu.popup(QCursor.pos())					

		# select node and open UV editor
		if col_index == 2:
			if node:
				pymel.select(node)
				pymel.lockNode(node, lock=False)

				def uv_cmd():
					try:
						maya.mel.eval('TextureViewWindow')
					except:
						pass

				self.tw_menu = QMenu(self)

				# uvEditor
				uv_action = QAction('UV Editor', self)
				uv_action.triggered.connect(lambda: uv_cmd())
				self.tw_menu.addAction(uv_action)
				self.tw_menu.popup(QCursor.pos())
				

	def check_bone_connected(self, bone):
		"""
		See if the bone is skinned we cannot perform certain operations if it is

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/21/2014 10:14:36 PM
		"""

		bindpose = False
		skincluster = False
		connections = bone.listConnections()
		if connections:
			for conn in connections:
				if pymel.nodeType(conn) == 'dagPose':
					bindpose = True
				elif pymel.nodeType(conn) == 'skincluster':
					skincluster = True

		if bindpose and skincluster:
			return True

		return False


	def do_remove_mesh(self, mesh, mesh_bone=None, mesh_control=None, remove_rigging=True):
		"""
		Remove the mesh from the item

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/3/2014 4:22:48 PM
		"""		

		original_selection = pymel.ls(sl=True)
		pymel.select(mesh)
		with pymel.UndoChunk():

			# unlock the node and move it
			pymel.lockNode(mesh, lock=False)

			# disable envelope on skinning
			skincluster = mesh.listHistory(type="skinCluster")
			if skincluster:
				pass

			if self.unassigned_group:
				pymel.lockNode(self.unassigned_group, lock=False)
				pymel.parent(mesh, self.unassigned_group)
				pymel.lockNode(self.unassigned_group, lock=True)

			# remove the item attribute
			# leave the existing attributes for adding back later
			attrs = ['rh_weapon','rh_vehicle','rh_item'] # 'rh_bone', 'rh_control']
			for attr in attrs:
				if mesh.hasAttr(attr):
					mesh.setAttr(attr, lock=False)		
					mesh.deleteAttr(attr)

			pymel.lockNode(mesh, lock=False)

			# remove the bones and control
			if remove_rigging:

				if mesh_bone:				
					# unlock node and attributes
					pymel.lockNode(mesh_bone, lock=False)
					attrs = ['rh_weapon','rh_vehicle','rh_item','rh_item_bone_index','rh_parent','rh_weapon_bone','rh_item_bone','rh_mat_group']
					bone_index = self.get_attribute_value(mesh_bone, 'rh_item_bone_index')				
					for attr in attrs:
						if mesh_bone.hasAttr(attr):
							mesh_bone.setAttr(attr, lock=False)		
							mesh_bone.deleteAttr(attr)

					weap_index = self.get_attribute_value(self.item_node, 'rh_bone_index')
					if weap_index:					
						if bone_index == weap_index-1:
							prev_index = bone_index
							# if this was the last rigged bone decrement the item_bone_index						
							pymel.lockNode(self.item_node, lock=False)
							self.item_node.setAttr('rh_bone_index', lock = False)
							self.item_node.setAttr('rh_bone_index', prev_index)
							self.item_node.setAttr('rh_bone_index', lock = True)											

					# delete constrain objects before unparenting
					connections = pymel.listConnections(mesh_bone)
					if connections:
						connections = list(set(connections))

					# Parent to UnAssigned Group
					pymel.parent(mesh_bone, self.unassigned_group)				

				if mesh_control:
					# make sure there are no external controls to the control objects
					# the bone doesn't count
					connections = pymel.listConnections(mesh_control)
					if connections:
						connections = list(set(connections))

					# unlock node and attributes
					pymel.lockNode(mesh_control, lock=False)
					attrs = ['rh_weapon','rh_vehicle','rh_item','rh_child_control','rh_item_control']
					for attr in attrs:
						if mesh_control.hasAttr(attr):
							mesh_control.setAttr(attr, lock=False)		
							mesh_control.deleteAttr(attr)												

					# get the parent before the rig_grp
					rig_grp = self.get_attribute_value(self.item_node, 'rh_rig_grp')
					del_parent = None
					if rig_grp:
						# remove rigging nodes but keep the control
						parent = rh_maya.get_obj_parent(mesh_control, parent_before=rig_grp)
						if parent:
							del_parent = parent

					# Parent to UnAssigned Group
					pymel.parent(mesh_control, self.unassigned_group)

					# Delete old rig chain
					if del_parent:
						children = pymel.listRelatives(rig_grp, c=True)
						if del_parent in children:
							pymel.delete(parent)	

		# update item vars
		self._init_item_()

		# refresh the ui
		self.update_ui()		


	def do_set_mesh(self):
		"""
		Main Set Mesh Method

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/20/2014 11:12:28 AM
		"""

		# clean attrs
		pymel.lockNode(self.temp_mesh, lock=False)
		for mat in self.temp_materials:
			pymel.lockNode(mat, lock=False)		
		
		bone = None		
		item_prefix = '{0}_'.format(self.item_type.lower())

		# need to make sure the new bone/control name doesnt already exists
		# increment the bone index and update the item node attribute
		if self.temp_bone:
			item_bone_index = self.get_attribute_value(self.item_node, 'rh_bone_index')	
			index_string = str( int(item_bone_index) ).zfill( 2 )
			new_bone_name = item_prefix + index_string	
			if pymel.objExists(new_bone_name):
				obj = pymel.PyNode(new_bone_name)
				if not obj == self.temp_bone:
					cmds.confirmDialog(title='Item Rigger: Add Mesh Error', m='WARNING:\nAn object with the same name as the newly added bone already exists in the scene!\nPlease rename the old bone or delete it.\n\nBone: {0}   >   New Name: {2}\n\nDelete or Rename:\nOld Bone: {1}'.format(self.temp_bone.nodeName(), obj.longName(), new_bone_name))
					return False

			if self.temp_control:
				new_control_name = item_prefix + index_string + '_anim'
				if pymel.objExists(new_control_name):
					obj = pymel.PyNode(new_control_name)
					if not obj == self.temp_control:
						cmds.confirmDialog(title='Item Rigger: Add Mesh Error', m='WARNING:\nAn object with the same name as the newly added control already exists in the scene!\nPlease rename the old control or delete it.\n\nControl: {0}   >   New Name: {2}\n\nDelete or Rename:\nOld Control: {1}'.format(self.temp_control.nodeName(), obj.longName(), new_bone_name))
						return False

		pymel.lockNode(self.temp_mesh, lock=False)		

		# get all the active item materials being used and make sure it isn't being used	
		self.item_materials = self.get_item_materials()
		new_material_group = True
		mesh_material_group = None
		for material_index, material_info in self.item_materials.iteritems():
			group_materials, material_group = material_info
			found_grp = False
			
			# need to do a len check and make sure all the materials on the new mesh exist in this group			
			if len(self.temp_materials) > 1:				
				for mat in group_materials:
					checked_mats = []
					failed_mats = []					
					for t_mat in self.temp_materials:
						if t_mat in group_materials:
							checked_mats.append(t_mat)
						else:
							failed_mats.append(t_mat)							
					if not failed_mats:
						pymel.parent(self.temp_mesh, material_group)
						mesh_material_group = material_group
						new_material_group = False
						found_grp = True
						break						
			
			else:
				temp_mat = self.temp_materials[0]
				for mat in group_materials:
					# if the mesh being added has an existing material grp, it needs to be parented under that group
					if mat == temp_mat:
						pymel.parent(self.temp_mesh, material_group)
						mesh_material_group = material_group
						new_material_group = False
						found_grp = True
						break
				
			# exit early
			if found_grp:
				break

		# create a new material group
		if new_material_group:
			mat_group = self.create_material_group(self.temp_materials)
			if mat_group:
				pymel.lockNode(mat_group, lock=False)				
				pymel.parent(self.temp_mesh, mat_group)
				mesh_material_group = mat_group

		pymel.lockNode(self.item_node, lock=False)

		# Skin to the selected bone
		rig_control = False
		if not self.temp_bone:
			# skin the mesh to the selected existing bone
			bone_name = self.add_bone_combo.currentText()
			bone = pymel.PyNode(bone_name)
		else:
			sel = pymel.ls(sl=True)
			pymel.select(cl=True)

			# update the new bone and attributes
			pymel.lockNode(self.temp_bone, lock=False)
			bone = self.temp_bone
			pymel.select(bone)
			pymel.lockNode(bone, lock=False)
			rh_maya.lock_channels(bone, lock=False)			
			rh_maya.disable_segment_compensate_scale([bone])
			pymel.lockNode(bone, lock=False)
			if not pymel.hasAttr(bone, 'rh_item_bone'):
				pymel.addAttr(bone, ln='rh_item_bone', niceName='ItemBone', at='bool', keyable=False, dv=1)				

			# freeze the bone orients			
			dag = False
			skincluster = False			
			connections = bone.listConnections()			
			if connections:				
				for conn in connections:
					if pymel.nodeType(conn) == 'dagPose':
						dag = True
					elif pymel.nodeType(conn) == 'skincluster':
						skincluster = True
			# make identity
			if not dag and not skincluster:
				try:
					cmds.makeIdentity(apply=True, t=1, r=1, s=1, n=0)
				except:
					cmds.warning('Joint being added alreayd has a skinCluster attached!\n Joint: {0}'.format(bone.nodeName()))

			pymel.select(sel)		

			# message for the bone being added
			if not pymel.hasAttr(self.temp_mesh, 'rh_bone'):
				print 'Temp Mesh: {0}'.format(self.temp_mesh)
				pymel.lockNode(self.temp_mesh, lock=False)
				pymel.addAttr(self.temp_mesh, at='message', ln= 'rh_bone', niceName='Bone')
			else:
				self.temp_mesh.setAttr('rh_bone', lock=False)
				connection = pymel.PyNode(self.temp_mesh.longName()+'.rh_bone')
				if connection:
					connection.disconnect()			
			cmds.connectAttr( bone.longName() + '.message', self.temp_mesh.longName() + '.rh_bone', f=True )
			self.temp_mesh.setAttr('rh_bone', lock=True)

			# if not a child of the item hierarchy add it
			bone_parent = pymel.listRelatives(bone, p=True)
			pymel.lockNode(bone, lock=False)
			set_default_parent = True
			if bone_parent:
				bone_parent = bone_parent[0]
				if bone_parent in self.get_item_bones():
					set_default_parent = False
				root_bone = self.get_attribute_value(self.item_node, 'rh_item_root')
				if root_bone:
					if bone_parent == root_bone:
						set_default_parent = False
			
			if set_default_parent:
				if self.item_type == 'Weapon':
					weapon_grip = pymel.PyNode('weapon_grip')
					if weapon_grip:
						pymel.parent(bone, weapon_grip)
				else:
					frame = pymel.PyNode('frame')
					if frame:
						pymel.parent(bone, frame)							

			# add bone attributes
			if not pymel.hasAttr(bone, self.item_type_attr):
				pymel.addAttr(bone, ln=self.item_type_attr, at='bool', keyable=False, dv=1)			
			if not pymel.hasAttr(bone, 'rh_item_bone_index'):
				pymel.addAttr(bone, ln='rh_item_bone_index', niceName='BoneIndex', at = 'double', defaultValue = 0.0, minValue = 0.0, maxValue = 60.0, keyable = False, h = False)					
			else:
				bone.setAttr('rh_item_bone_index', lock=False)
			if not pymel.hasAttr(bone, 'rh_parent'):
				pymel.addAttr(bone, at='message', ln= 'rh_parent', niceName='Parent')			

			# increment the bone index and update the item node attribute
			item_bone_index = self.get_attribute_value(self.item_node, 'rh_bone_index')
			index_string = str( int(item_bone_index) ).zfill( 2 )

			new_index = int(item_bone_index) + 1				
			self.item_node.setAttr('rh_bone_index', lock = False)
			self.item_node.setAttr('rh_bone_index', new_index)
			self.item_node.setAttr('rh_bone_index', lock = True)

			# set the bone to be the current item bone index
			bone.setAttr('rh_item_bone_index', item_bone_index)
			bone.setAttr(self.item_type_attr, lock=True)
			bone.setAttr('rh_item_bone_index', lock=True)
			bone.setAttr('radius', 4.0)

			# store this off
			self.last_bone_index_added = item_bone_index		

			# rename the bone base on the item_bone_index
			bone_name = item_prefix + index_string
			pymel.rename(bone, bone_name)	

			sel = pymel.ls(sl=True)
			if self.temp_control:
				pymel.lockNode(self.temp_control, lock=False)
				rh_maya.lock_channels(self.temp_control, lock=False)			
				sel = pymel.ls(sl=True)
				pymel.select(self.temp_control)
				cmds.delete(constructionHistory=True)	
				pymel.parent(self.temp_control, bone)
				cmds.makeIdentity(apply=True, t=1, r=1, s=1, n=0)
				maya.mel.eval('ResetTransformations')
				pymel.select(sel)

				if not pymel.hasAttr(self.temp_control, 'rh_item_control'):
					pymel.addAttr(self.temp_control, ln='rh_item_control', niceName='ItemControl', at='bool', keyable=False, dv=1)					

				pymel.parent(self.temp_control, self.unassigned_group)				

				rig_control = True
				parent_control = pymel.PyNode(self.parent_ctrl_combo.currentText())
			else:
				cmds.warning('Could not find the selected control: {0}'.format(self.temp_control))		

		# add mesh attributes
		# Material Group Attribute
		if not pymel.hasAttr(self.temp_mesh, 'rh_mat_group'):							
			pymel.addAttr(self.temp_mesh, at='message', ln= 'rh_mat_group', niceName='MaterialGroup')				

		if self.temp_mesh.hasAttr('rh_mat_group'):
			pymel.lockNode(self.temp_mesh, lock=False)
			self.temp_mesh.setAttr('rh_mat_group', lock=False)
			if not mesh_material_group:
				mesh_material_group = self.get_mesh_material_group(self.temp_mesh)
			if mesh_material_group:
				pymel.lockNode(mesh_material_group, lock=False)
				connection = pymel.PyNode(self.temp_mesh.longName()+'.rh_mat_group')
				if connection:
					connection.disconnect()				
				pymel.connectAttr(mesh_material_group + '.message', self.temp_mesh + '.rh_mat_group', f=True)				
				pymel.lockNode(mesh_material_group, lock=True)

		# See if mesh is already skinned
		skincluster = self.temp_mesh.listHistory(type="skinCluster")
		if not skincluster:
			self.keep_skinning = False

		# skin and lock mesh
		if not self.keep_skinning:
			rh_maya.skin_mesh([bone], self.temp_mesh)

		# add item attr
		pymel.lockNode(self.temp_mesh, lock=False)
		if not pymel.hasAttr(self.temp_mesh, self.item_type_attr):
			pymel.addAttr(self.temp_mesh, ln=self.item_type_attr, at='bool', keyable=False, dv=1)
		else:
			self.temp_mesh.setAttr(self.item_type_attr, lock=True)
		self.temp_mesh.setAttr(self.item_type_attr, lock=True)	

		# rig item control
		if rig_control:
			if parent_control:
				pymel.lockNode(self.temp_control, lock=False)
				if not self.temp_control.hasAttr(self.item_type_attr):					
					pymel.addAttr(self.temp_control, ln=self.item_type_attr, at='bool', keyable=False, dv=1)
				self.temp_control.setAttr(self.item_type_attr, lock=True)

				# connect parent control by message to this child control
				if not self.temp_control.hasAttr('rh_child_control'):
					pymel.addAttr(self.temp_control, at='message', ln= 'rh_child_control', niceName='ChildControl')
				else:
					self.temp_control.setAttr('rh_child_control', lock=False)
					connection = pymel.PyNode(self.temp_control.longName()+'.rh_child_control')
					if connection:
						connection.disconnect()	
				cmds.connectAttr( parent_control.longName() + '.message', self.temp_control.longName() + '.rh_child_control', f=True )
				self.temp_control.setAttr('rh_child_control', lock=True)

				# Mesh message for the control being added 
				if not self.temp_mesh.hasAttr('rh_control'):					
					pymel.addAttr(self.temp_mesh, at='message', ln= 'rh_control', niceName='Control')
				else:
					self.temp_mesh.setAttr('rh_control', lock=False)
					connection = pymel.PyNode(self.temp_mesh.longName()+'.rh_control')
					if connection:
						connection.disconnect()
				cmds.connectAttr( self.temp_control.longName() + '.message', self.temp_mesh.longName() + '.rh_control', f=True )				
				self.temp_mesh.setAttr('rh_control', lock=True)				

				# Rig the Item Control
				rh_maya.create_weapon_control( ctrl=self.temp_control, bone=bone, constraint_obj=parent_control, create_space_grps=True, separate_xforms=False )

				# connect bone parent message
				bone_parent = pymel.listRelatives(bone, p=True)
				if bone_parent:
					bone_parent = bone_parent[0]
					pymel.connectAttr( bone_parent.longName() + '.message', bone.longName() + '.rh_parent', f=True )				

			else:
				cmds.warning('Could not find the parent control: {0}'.format( self.parent_ctrl_combo.currentText()))				

		# reset temp variables
		self.temp_mesh = None
		self.temp_materials = None
		self.temp_bone = None
		self.temp_control = None
		self.parent_ctrl_picked = False

		return True


	def on_pressed_set_mesh(self):
		"""
		Add the item mesh
		Skin to the given/selected bone
		Rig to the given/selected control

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/18/2014 11:01:25 AM
		"""	

		selection = pymel.ls(sl=True)
		with pymel.UndoChunk():
			self.do_set_mesh()

		# update item variables		
		self._init_item_()

		# refresh the ui
		self.update_ui()
		
		pymel.select(selection)
		
		
	def reset_buttons(self):
		"""
		Reset button states

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/17/2014 9:43:27 PM
		"""	
		
		self.info_base_mesh_pushButton.setDown(False)
		self.info_mesh_pushButton.setDown(False)
		self.info_sel_bone_pushButton.setDown(False)
		self.info_control_pushButton.setDown(False)
		self.info_parent_control_pushButton.setDown(False)
		
		
	def on_pressed_info(self, info_type='base'):
		"""
		Give info on the current UI item

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/17/2014 9:43:27 PM
		"""

		info_msg = ''
		info_title = 'Info'

		if info_type == 'base':
			info_title = 'Add Base Mesh: Info'
			info_msg = 'Add the base mesh:\n\nThis is the root or rigid base portion of the item/weapon mesh.\nThis mesh should should have the primary material assigned as well.'
		elif info_type == 'mesh':
			info_title = 'Add Mesh: Info'
			info_msg = 'Add new mesh:\n\nThis is a new item/weapon mesh.\nThis mesh can be weighted to an existing bone or a newly selected bone'		
		elif info_type == 'bone':
			info_title = 'Pick or Add Bone: Info'
			info_msg = 'Pick or Add bone:\n\nWhen adding a new mesh you must choose a bone to skin the mesh to.\nThis can be an existing bone or you can select a bone from the scene.\n\nIf you want the new bone to be a child of an existing bone and follow that bone, make it a child of the bone you wish to follow prior to adding the new bone.\n\nIf you do not parent your new bone to a specific bone in the heirarchy, it will become a child of the weapon_grip bone.'
		elif info_type == 'rh_control':
			info_title = 'Add Control: Info'
			info_msg = 'Add a new Control:\n\nWhen choosing a new bone you must also choose a new control shape that will be used for animating the new bone that your mesh will be skinned to.'
		if info_type == 'parent_control':
			info_title = 'Pick Parent Control: Info'
			info_msg = 'Pick the Parent Control:\n\nWhen adding a new control, you must choose an existing item/weapon control to have it follow the item/weapon properly in a hierarchy.\n\nSelect the existing weapon control that you would like your new control to follow.'

		# update the down states
		self.reset_buttons()
		
		cmds.confirmDialog(title=info_title, m=info_msg)


	def on_pressed_material_hypershade(self):
		"""
		Graph material in the hypershade window

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 4:52:37 PM
		"""
		
		current_item = self.tw_meshes.currentItem()
		if not current_item:
			return False

		row_index = current_item.row()
		if not self.attachment_row_index == None:			
			if row_index < self.attachment_row_index:
				try:
					mesh_node = self.item_mesh_nodes[current_item.row()]
				except:
					cmds.warning('The selected mesh in the UI could not be found!!!')
					return
			else:		
				try:
					item_index = (current_item.row() - self.attachment_row_index) -1
					mesh_node = self.item_attachment_nodes[item_index]		
				except:
					cmds.warning('The selected mesh in the UI could not be found!!!')
					return
		else:
			try:
				mesh_node = self.item_mesh_nodes[current_item.row()]
			except:
				cmds.warning('The selected mesh in the UI could not be found!!!')
				return			
		
		mat_node = pymel.PyNode(current_item.text())		
		if mesh_node:
			pymel.select(mesh_node, r=True)
			cmds.refresh()
			pymel.hyperShade(rst=True)
			pymel.hyperShade(rsg=True)			
			maya.mel.eval('HypershadeWindow;')
			pymel.hyperShade(sns=True,ups=True, ds=True)
		elif mat_node:
			pymel.select(mat_node, r=True)
			cmds.refresh()
			pymel.hyperShade(rst=True)
			pymel.hyperShade(rsg=True)
			maya.mel.eval('HypershadeWindow;')
			pymel.hyperShade(sns=True,ups=True, ds=True)		
			


	def on_pressed_set_mesh_static(self, is_static):
		"""
		Flag the mesh attachment as static or not
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/8/2014 3:24:59 PM
		"""
		current_item = self.tw_meshes.currentItem()
		if not current_item:
			return False

		# get mesh and attributes
		try:
			item_index = (current_item.row() - self.attachment_row_index) -1
			mesh_node = self.item_attachment_nodes[item_index]		
		except:
			cmds.warning('The selected mesh in the UI could not be found!!!')
			return

		# see if custom rigging exists
		mesh_bone = self.get_attribute_value(mesh_node, 'rh_bone')

		if is_static:
			query_txt = 'Flagging the attachment as Static Mesh (S).\nThis attachment will be exported as a separate static mesh.\n\nMesh: {0}\n'.format(mesh_node.nodeName())
		else:
			query_txt = 'Flagging the attachment as a Deformable Mesh (D).\nThis attachment will be exported as a separate skeletal mesh.\n\nMesh: {0}\n'.format(mesh_node.nodeName())
			
		result = cmds.confirmDialog( title='Item Rigger: Attachment', message=query_txt, button=[ 'Yes', 'No','Cancel' ], defaultButton='No', cancelButton='Cancel',dismissString='Cancel' )
		if not result == 'Yes':			
			return False
		
		# add the attachment attribute
		pymel.lockNode(mesh_node, lock=False)
		self.do_add_mesh_attributes(mesh_node, bone=None, control=None, material_group=None, is_attachment=True, is_static=is_static)
		
		# update meshes ui()
		self.update_ui_meshes()
		

	def on_pressed_set_mesh_attachment(self):
		"""
		Flag the selected mesh as an attachment
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/3/2014 10:23:44 AM
		"""
		current_item = self.tw_meshes.currentItem()
		if not current_item:
			return False

		# get mesh and attributes
		try:
			mesh_node = self.item_mesh_nodes[current_item.row()]
		except:
			cmds.warning('The selected mesh in the UI could not be found!!!')
			return

		# see if custom rigging exists
		mesh_bone = self.get_attribute_value(mesh_node, 'rh_bone')

		query_txt = 'Are you sure you want to flag the mesh as a separate attachment?\nThis mesh will not be exported with the item. It will be exported as a separate static mesh.\n\nMesh: {0}\n'.format(mesh_node.nodeName())
		result = cmds.confirmDialog( title='Item Rigger: Flag Mesh as Attachment', message=query_txt, button=[ 'Yes', 'No','Cancel' ], defaultButton='No', cancelButton='Cancel',dismissString='Cancel' )
		if not result == 'Yes':			
			return False
		
		# add the attachment attribute
		pymel.lockNode(mesh_node, lock=False)
		self.do_add_mesh_attributes(mesh_node, bone=None, control=None, material_group=None, is_attachment=True, is_static=False)
		
		# update meshes ui()
		self.update_ui_meshes()
		
		
	def on_pressed_remove_mesh_attachment(self):
		"""
		Unflag the mesh as an attachment
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/3/2014 10:41:51 AM
		"""
		
		current_item = self.tw_meshes.currentItem()
		if not current_item:
			return False

		# get mesh and attributes
		try:
			item_index = (current_item.row() - self.attachment_row_index) -1
			mesh_node = self.item_attachment_nodes[item_index]
		except:
			cmds.warning('The selected mesh in the UI could not be found!!!')
			return

		# see if custom rigging exists
		attachment = self.get_attribute_value(mesh_node, 'rh_attachment')
		if not attachment:
			cmds.warning('The selected mesh is not flagged as an Attachment')
			return False

		query_txt = 'Are you sure you want to unflag the mesh as a separate attachment?\nThis mesh will now be exported with the item.\n\nMesh: {0}\n'.format(mesh_node.nodeName())
		result = cmds.confirmDialog( title='Item Rigger: UnFlag Mesh Attachment', message=query_txt, button=[ 'Yes', 'No','Cancel' ], defaultButton='No', cancelButton='Cancel',dismissString='Cancel' )
		if not result == 'Yes':			
			return False
		
		# add the attachment attribute
		pymel.lockNode(mesh_node, lock=False)
		mesh_node.setAttr('rh_attachment', lock=False)
		mesh_node.deleteAttr('rh_attachment')
		
		# remove the static mesh attribute that goes with the attachment attribute
		if pymel.hasAttr(mesh_node, 'rh_static_mesh'):
			mesh_node.setAttr('rh_static_mesh', lock=False)
			mesh_node.deleteAttr('rh_static_mesh')
		
		# update meshes ui()
		self.update_ui_meshes()		
		

	def on_pressed_remove_mesh(self):
		"""
		Handle removing a mesh piece and any of its associated rigging if possible

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 2:53:12 PM
		"""

		current_item = self.tw_meshes.currentItem()
		if not current_item:
			return False
		
		# get mesh and attributes
		row_index = current_item.row()
		mesh_node = None
		if not self.attachment_row_index == None:			
			if row_index < self.attachment_row_index:
				try:
					mesh_node = self.item_mesh_nodes[current_item.row()]
				except:
					cmds.warning('The selected mesh in the UI could not be found!!!')
					return
			else:		
				try:
					item_index = (current_item.row() - self.attachment_row_index) -1
					mesh_node = self.item_attachment_nodes[item_index]		
				except:
					cmds.warning('The selected mesh in the UI could not be found!!!')
					return
		else:
			mesh_node = self.item_mesh_nodes[row_index]
			
		if mesh_node == None:
			cmds.warning('The selected mesh in the UI could not be found in the item_mesh_nodes list!!!')
			return 

		# see if custom rigging exists
		mesh_bone = self.get_attribute_value(mesh_node, 'rh_bone')
		mesh_control = self.get_attribute_value(mesh_node, 'rh_control')		

		query_txt = 'Are you sure you want to remove the item mesh?\n\nMesh: {0}\n'.format(mesh_node.nodeName())
		result = cmds.confirmDialog( title='Item Rigger: Remove Mesh', message=query_txt, button=[ 'Yes', 'No','Cancel' ], defaultButton='No', cancelButton='Cancel',dismissString='Cancel' )
		if not result == 'Yes':			
			return False

		# Query if we want the rigging to be kept or removed
		remove_rigging = False
		if mesh_bone or mesh_control:
			if mesh_bone and mesh_control:
				query_txt = 'The mesh you are removing has associated bone and control objects?\n\n Bone: {0}\n Control: {1}\n\nWould you like to remove these from the item as well?'.format(mesh_bone.nodeName(), mesh_control.nodeName())
			elif mesh_bone:
				query_txt = 'The mesh you are removing has associated bone and/or control objects?\n\n Bone: {0}\n\nWould you like to remove the rigging of these objects from the item as well?'.format(mesh_bone.nodeName())
			elif mesh_control:
				query_txt = 'The mesh you are removing has associated bone and/or control objects?\n\n Control: {0}\n\nWould you like to remove the rigging of these objects from the item as well?'.format(mesh_control.nodeName())

			control_msg = ''
			no_remove_control = False
			if mesh_control:					

				# see if this control is a parent control
				connections = pymel.listConnections(mesh_control, type='transform')
				if connections:
					connections = list(set(connections))
					controls = [x for x in connections if x.hasAttr('rh_child_control')]
					if controls:
						for control in controls:							
							connection = pymel.PyNode(control.longName()+'.rh_child_control')
							if connection:
								parent_control = connection.get()
								if parent_control == mesh_control:									
									pymel.select(mesh_control)
									control_msg = 'The associated control has other animation controls connected to it. This will likely require a much more sophisticated approach as it will destroy the rigging relative to this control.'
									no_remove_control = True		

			no_remove_bone = False
			bone_msg = ''
			if mesh_bone:
				# there may be multiple child bones under this joint
				children = mesh_bone.getChildren(type='joint')				
				if children:
					pymel.select(mesh_bone)
					bone_msg = 'The associated bone has additional children joints. This will likely require a much more sophisticated approach as it will destroy the rigging below this joint.'
					no_remove_bone = True

				# there may be multiple item meshes skinned to this bone
				skinclusters = pymel.listConnections(mesh_bone, type='skinCluster')				
				if skinclusters:					
					skinclusters = list(set(skinclusters))
					if len(skinclusters) > 1:
						pymel.select(mesh_bone)
						bone_msg = 'The associated bone is assigned to multiple skinclusters. This will likely require a much more sophisticated approach as it will destroy the rigging below this joint.'
						no_remove_bone = True

			# We will only remove all rigging if no issues were found
			if not no_remove_control and not no_remove_bone:
				result = cmds.confirmDialog( title='Item Rigger: Remove Mesh', message=query_txt, button=[ 'Keep', 'Remove', 'Cancel' ], defaultButton='Keep', cancelButton='Cancel',dismissString='Cancel' )
				if result == 'Remove':
					remove_rigging = True
				if result == 'Cancel':
					return False
			else:
				if mesh_control or mesh_bone:					
					rigging_text = 'There was rigging found associated directly with this mesh.\n\nMesh Control: {0}\n\nMesh Bone: {1}\n\n The associated rigging will not be removed due to the issues found.\n'.format(control_msg, bone_msg)
					cmds.confirmDialog( title='Item Rigger: Remove Mesh', message=rigging_text)				

		pymel.waitCursor( state = True )
		self.do_remove_mesh(mesh_node, mesh_bone=mesh_bone, mesh_control=mesh_control, remove_rigging=remove_rigging)
		pymel.waitCursor( state = False )
		return True


	def on_pressed_mesh_remove(self, base_mesh=False):
		"""
		Remove the selected mesh entry

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/13/2014 1:55:11 PM
		"""
		
		self.remove_base_mesh_pushButton.setDown(False)

		if base_mesh:

			if not self.item_base_mesh:
				return			

			query_txt = 'Removing the item base mesh will invalidate most of the associated Item data!\nYou should be really sure that you want to do this.\n\nAre you sure you want to remove the base mesh?'
			result = cmds.confirmDialog( title='Item Rigger: Remove Base Mesh', message=query_txt, button=[ 'Yes', 'No', 'Cancel' ], defaultButton='No', cancelButton='Cancel',dismissString='Cancel' )
			if not result == 'Yes':
				return False			

			if self.item_base_mesh:
				if self.unassigned_group:
					pymel.lockNode(self.item_base_mesh, lock=False)
					pymel.lockNode(self.unassigned_group, lock=False)
					pymel.parent(self.item_base_mesh, self.unassigned_group)
					pymel.lockNode(self.unassigned_group, lock=True)
				else:
					cmds.warning('Couldnt find the _UNASSIGNED_ grp')
				pymel.lockNode(self.item_node, lock=False)
				self.item_node.setAttr('rh_mesh_base', lock=False)			

				# remove the message connection from the Item
				connection = pymel.PyNode(self.item_node.longName()+'.rh_mesh_base')
				if connection:
					connection.disconnect()		
				self.item_node.setAttr('rh_mesh_base', lock=True)

				# if Mat group has no other meshes then don't remove the shader attr
				mat_group = self.get_material_group(index=0)
				grp_meshes = self.get_material_group_meshes(index=0)
				if not grp_meshes:
					mats = self.get_item_materials()
					if mats:
						try:
							mat = mats[0][0]
							pymel.lockNode(mat, lock=False)
						except:
							pass

						if mat_group:
							pymel.lockNode(mat_group, lock=False)						
							mat_group.setAttr('rh_material', lock=False)

							# remove the material connection from the mat_grp
							attr = pymel.PyNode(mat_group.longName() + '.rh_material')
							if attr:
								incoming = attr.inputs(plugs=True)
								for plug in incoming:									
									plug.disconnect()								
							

							mat_group.setAttr('rh_material', lock=True)
						self.item_node.setAttr('rh_mesh_base', lock=False)

				# lock the item node
				pymel.lockNode(self.item_node, lock=False)

				pymel.lockNode(self.item_base_mesh, lock=False)
				if pymel.hasAttr(self.item_base_mesh, self.item_type_attr):
					self.item_base_mesh.setAttr(self.item_type_attr, lock=False)
					self.item_base_mesh.deleteAttr(self.item_type_attr)

				# clear the mesh name
				self.base_mesh_text.setText('')
				self.item_base_mesh = None

				# refresh the ui
				self.update_ui()				

		else:
			# clear the mesh name
			self.temp_bone = None
			self.temp_control = None
			self.temp_mesh = None
			self.temp_materials = None
			self.add_mesh_text.setText('')		
			self.remove_mesh_pushButton.setDisabled(True)

		
		self.update_ui()
		
		
	def update_parent_control_combo(self, control, quiet=False):
		"""
		Update the combo box for the selected parent control
		
		*Arguments:*
			* ``control`` The control pynode
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/8/2014 4:04:20 PM
		"""
		
		error_msg = 'Validating Selected Parent Ctrl:\n'
		
		# validate the selection
		if not control:
			selection = pymel.ls(sl=True, type='transform')
			if not len(selection) == 1:
				error_msg += 'You must select a single curve shape object in the scene that exists in the drop down list here!'
				cmds.warning(error_msg)
				return False
			else:
				control = selection[0]
	
		# make sure the joint isnt already under the hierarchy		
		shape = rh_maya.get_mesh_shape(control)
		if not shape:
			error_msg += 'You must select a single curve shape object!\nThis object does not have a shape.'
			cmds.warning(error_msg)
			return False
	
		# make sure the selection isnt geometry
		if pymel.nodeType(control) == 'mesh':		
			error_msg += 'You must select a single curve shape object!\nThis object appears to be geometry and not a curve shape object.'
			cmds.warning(error_msg)
			return False
		
		mesh_relatives = pymel.listRelatives(control, type='mesh')
		if mesh_relatives:
			error_msg += 'You must select a single curve shape object!\nThis object appears to be geometry and not a curve shape object.'
			cmds.warning(error_msg)
			return False
	
		# find it and set it in the UI
		if control in self.get_item_controls():
			index = 0			
			self.parent_ctrl_add_control_names = [x.nodeName() for x in self.item_controls if not any([x.nodeName() in self.item_base_ctrls])]
			for name in self.parent_ctrl_add_control_names:
				if control.nodeName() == name:
					self.parent_ctrl_combo.setCurrentIndex(index)
					self.parent_ctrl_combo.setStyleSheet('''QComboBox {color: black; background-color: orange }''')
					self.parent_ctrl_picked = True
					return True			
				index += 1
				
		error_msg += 'You must select a single curve shape object not already assigned to the item!'
		cmds.warning(error_msg)
		return False
	

	def on_pressed_parent_ctrl_picked(self):
		"""
		Update parent bone selected in the scene
		check against existing item controls

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/22/2014 12:37:31 AM
		"""
		
		self.update_parent_control_combo(None)
		

	def on_pressed_ctrl_picked(self):
		"""
		Update the bone picked

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/15/2014 5:31:09 PM
		"""		
		error_msg = 'Validating Selected Ctrl:\n'

		# validate the selection
		selection = pymel.ls(sl=True, type='transform')
		if not len(selection) == 1:			
			error_msg += 'You must select a single curve shape object!'
			cmds.warning(error_msg)
			return False

		# make sure the joint isnt already under the hierarchy
		control = selection[0]
		shape = rh_maya.get_mesh_shape(selection[0])
		if not shape:
			error_msg += 'You must select a single curve shape object!\nThis object does not have a shape.'
			cmds.warning(error_msg)
			return False

		# make sure the selection isnt geometry
		if pymel.nodeType(control) == 'mesh':		
			error_msg += 'You must select a single curve shape object!\nThis object appears to be geometry and not a curve shape object.'
			cmds.warning(error_msg)
			return False

		mesh_relatives = pymel.listRelatives(control, type='mesh')
		if mesh_relatives:
			error_msg += 'You must select a single curve shape object!\nThis object appears to be geometry and not a curve shape object.'
			cmds.warning(error_msg)
			return False

		if control in self.get_item_controls():			
			error_msg += 'You must select a single curve shape object not already assigned to the item!'
			cmds.warning(error_msg)
			return False

		# store in the UI until we hit accept
		self.temp_control = control		
		self.add_ctrl_pushButton.showNormal()
		self.add_ctrl_pushButton.setDown(False)		
		self.update_ui()
		
		return True	


	def on_pressed_ctrl_remove(self):
		"""
		Update the bone picked

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/15/2014 5:31:09 PM
		"""		
		# store in the UI until we hit accept
		self.temp_control = None
		self.add_ctrl_text.setText('')
		self.update_ui()

		return True	

	def on_pressed_bone_picked(self):
		"""
		Update the bone picked

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/15/2014 5:31:09 PM
		"""

		error_msg = 'Validating Selected Bone:\n'

		# validate the selection
		selection = pymel.ls(sl=True, type='joint')
		if not len(selection) == 1:
			error_msg += 'You must select a single joint object!'
			cmds.warning(error_msg)
			return False

		# make sure the joint isnt already under the hierarchy
		bone = selection[0]
		bone_parent = pymel.listRelatives(bone, p=True)
		if bone in self.get_item_bones():
			index = 0			
			for name in self.add_bone_combo_names:
				if bone.nodeName() == name:
					self.add_bone_combo.setCurrentIndex(index)
					self.add_bone_picked = True
					self.add_bone_combo.setStyleSheet('''QComboBox {color: black; background-color: orange }''')
					return True
				index += 1

			# Fall back to error
			error_msg += 'You must select a single joint object not already assigned to the item!'
			cmds.warning(error_msg)
			return False			

		# see if the bone already has a skincluster
		is_connected = self.check_bone_connected(bone)
		if is_connected:
			error_msg += 'The joint you picked seems to be already connected to a skincluster!'
			cmds.warning(error_msg)

		# store in the UI until we hit accept
		self.temp_bone = bone
		pymel.lockNode(bone, lock=False)

		# refresh the ui
		self.update_ui()

		# tell the user to parent their bone properly
		if bone_parent:
			bone_parent = bone_parent[0]
			if not bone_parent in self.get_item_bones():				
				add_bone_msg = 'PARENT THE SELECTED BONE NOW!!\n\nYou have selected a new bone to add to the Item.\nIf you want the bone to be a child of a specific bone, you must parent it appropriately in the item_root hierarchy.\n\nThe bone will otherwise default to becoming a child of the weapon_grip bone.'
				cmds.confirmDialog(title='Item Rigger: Add Bone', m=add_bone_msg)

		return True		


	def on_pressed_bone_remove(self):
		"""
		Update the bone picked

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/15/2014 5:31:09 PM
		"""	

		# store in the UI until we hit accept
		self.temp_bone = None
		self.sel_bone_text.setText('')
		self.add_bone_picked = False

		# refresh the ui
		self.update_ui()

		return True

	def on_pressed_sel_unassigned(self):
		"""
		Select the unassigned object

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/18/2014 8:58:20 PM
		"""

		if self.listView.selectedItems():
			sel_item = self.listView.selectedItems()[0].text()
			if not pymel.objExists(sel_item):
				return				
			node_longname = self.unassigned_names[self.listView.currentRow()]			
			node = pymel.PyNode(node_longname)		
			if node:
				self.unassigned_node = node
				pymel.select(self.unassigned_node)
		else:
			self.unassigned_node = None


	def on_cell_clicked(self, row_col):
		"""
		Enter a description of the function here.

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 1:44:32 PM
		"""
		
		mesh_types = ['(S)','(D)']
		row_index = self.tw_meshes.currentRow()
		col_index = self.tw_meshes.currentColumn()
		widget = self.tw_meshes.cellWidget(row_index, col_index)
		current_item = self.tw_meshes.currentItem()
		if col_index == 0 or col_index == 1:
			if current_item:
				name = current_item.data(0)
				if name:
					if any([x for x in mesh_types if name.startswith(x)]):
						name = name.split(' ')[1]					
					if cmds.objExists(name):
						node = pymel.PyNode(name)
						if node:
							pymel.select(node)


	def on_row_selection_changed(self):
		"""
		Handle row selection changing

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 12:38:15 PM
		"""

		row_index = self.tw_meshes.currentRow()
		widget = self.tw_meshes.cellWidget(row_index, 0)
		item = self.tw_meshes.item(row_index, 0)
		if item:			
			item_name = str(item.text())
			if ') ' in item_name:
				self.selected_item_name = item_name.split(') ')[1]
			else:
				self.selected_item_name = item_name
				


	def on_selected_listview(self):
		"""
		Select the current listView item

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/19/2014 12:20:38 PM
		"""
		
		if self.listView.selectedItems():
			name = self.listView.selectedItems()[0].text()
			if name:								
				if cmds.objExists(name):
					if self.unassigned_names:
						try:
							node_longname = self.unassigned_names[self.listView.currentRow()]
						except KeyError:
							node_longname = None
							
						if node_longname:
							if cmds.objExists(node_longname):
								node = pymel.PyNode(node_longname)
								if node:
									self.unassigned_node = node
									pymel.select(self.unassigned_node)
		else:
			self.unassigned_node = None


	def on_pressed_del_unassigned(self):
		"""
		Delete the selected unassigned mesh
		
		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/18/2014 8:58:36 PM
		"""

		self.delete_mesh_pushButton.setDown(False)
		original_selection = pymel.ls(sl=True)
		if self.listView.selectedItems():
			sel_item = self.listView.selectedItems()[0].text()
			node_longname = self.unassigned_names[self.listView.currentRow()]
			node = pymel.PyNode(node_longname)
			if node:
				# isolate selected				
				pymel.select(cl=True)
				pymel.selectMode(component=False)
				panel = pymel.getPanel( withFocus=True)				
				iso = False
				if panel.type() == 'modelEditor':				
					pymel.isolateSelect(panel, state=True)
					pymel.select(node)
					pymel.isolateSelect(panel, addSelected=True)
					pymel.refresh()
					iso =True
				else:
					pymel.select(node)

				# query user
				BUTTONS = YES, NO, CANCEL = 'Yes', 'No', 'Cancel'
				ret = cmds.confirmDialog( t='Delete Unassigned Mesh?', m='Are you sure you want to delete this mesh?\n\n Mesh: {0}'.format(node.nodeName()), b=BUTTONS, db=CANCEL )
				if iso:
					pymel.isolateSelect(panel, state=False)				
				if ret == CANCEL:
					return
				elif ret == YES:
					pymel.delete(node)								
					self.unassigned_node = None

					# refresh the ui
					self.update_ui_unassigned_meshes()

		try:
			pymel.select(original_selection, r=True)
		except:
			pass


	def do_add_base_mesh(self, mesh, mesh_materials):
		"""
		Setup the base mesh being added
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/6/2014 4:30:46 PM
		"""
		
		# See if mesh is already skinned
		skincluster = mesh.listHistory(type="skinCluster")
		if skincluster:
			non_joints = []
			non_joints_string = ''
			influences = rh_maya.get_skincluster_influences(mesh)
			for inf in influences:
				if not inf in self.get_item_bones():
					non_joints.append(inf)
					non_joints_string += ' {0}\n'.format(inf.nodeName())		
			if non_joints:
				query_txt = 'The mesh you are adding is already skinned and the joints that it is skinned to are not item joints.\n\nPlease correct then add the mesh again.\n\n Mesh: {0}\n Joints: {1}'.format(mesh.nodeName(), non_joints_string) 
				cmds.confirmDialog( title='Item Rigger: Add Mesh', message=query_txt)
				return False
	
		# check the existing base mesh material
		# the new/existing material being replaced cannot exist anywhere else in the current material groups
		if self.item_base_mesh:				
	
			# get all the active item materials being used and make sure it isn't being used		
			item_materials = self.get_item_materials()
			material_grp = None
			if len(item_materials) > 1:
	
				# loop through all of the item materials and see if the incoming material already exists
				for material_index, material_info in item_materials.iteritems():
					material, material_group= material_info							
					# does the current mat_group material, match the new base_mesh material
					if material in mesh_materials:
						material_grp = material_group
						# we want the new base_mesh material to be in the first material group
						# if its in a different group with other meshes, we need to make sure that group meshes can move as well
						# we ultimately dont want to shift materials
						if not int(material_index) == 0:
							# get the meshes in the other material_group
							new_mesh_grp_meshes = self.get_material_group_meshes(0)
							if not len(new_mesh_grp_meshes) == 1:
								# Other meshes in the group have a different material
								# Tis will scramble materials if this mesh is added
								cmds.confirmDialog(title='Add Base Mesh: Error', m='The mesh you are adding has a material that exists in the other meshes in the meshes original material group. This will cause materials to shift in game and that is not ideal.\n Mesh: {0} Material: {1}\n MatGroup: {2}'.format(mesh.nodeName(), mesh_material.nodeName(), material_group.nodeName()))
								return False
							else:
								# If there is only one mesh in the group its likely the new base mesh which we will be moving out since the material is different
								if not grp_meshes[0] == self.item_base_mesh:
									cmds.confirmDialog(title='Add Base Mesh: Error', m='The mesh you are adding has a different material than the one currently in the Mat_00 group. Assigning this mesh will cause materials to shift in game and that is not ideal.\n Mesh: {0}\n Mesh Material: {1}\n Current Base Mesh Material: {2}'.format(mesh.nodeName(), mesh_material.nodeName(), material.nodeName()))
									return False
								else:
									pymel.parent(self.item_base_mesh, self.item_node) 										
						else:
							# if the new base_mesh and self.base_mesh materials match this is good to go
							break
	
			elif len(item_materials) == 1:
				# if there is a single material make sure its the same
				material, material_group = item_materials[0]
				if not material in mesh_materials:
					mat_grp_meshes = self.get_material_group_meshes(index=0)
					if mat_grp_meshes:
						if len(mat_grp_meshes) > 0:
							# Other meshes in the group have a different material
							# Tis will scramble materials if this mesh is added
							cmds.confirmDialog(title='Add Base Mesh: Error', m='The mesh you are adding has a different material than the one currently on other Mat_00 gropu meshes. This will cause materials to shift in game and that is not ideal.\n Mesh: {0} Material: {1}\n MatGroup: {2}'.format(mesh.nodeName(), mesh_material.nodeName(), material_group.nodeName()))
							return False
				else:
					# same material then its fine
					pass
	
		# update the attributes/messages on the item node
		mesh_attr = 'rh_mesh_base'
		weap_base_attr = self.item_node.longName() + '.rh_mesh_base'
		mesh_msg_attr = mesh.longName() + '.message'
	
		pymel.lockNode(self.item_node, lock=False)
		self.item_node.setAttr('rh_mesh_base', lock=False)
	
		# add the message attr
		if not self.item_node.hasAttr(mesh_attr):
			pymel.addAttr(self.item_node, at= 'message', ln=mesh_attr)
		else:
			# remove existing connection to the attr
			input_conn = pymel.PyNode(self.item_node.longName()+'.rh_mesh_base')
			if input_conn:
				input_conn.disconnect()			
	
		# the attr should exists, so connect the attr to the mesh
		cmds.connectAttr(mesh_msg_attr, weap_base_attr, f=True)
		cmds.setAttr(weap_base_attr, lock=True)
		self.item_node.setAttr('rh_mesh_base', lock=True)
	
		# update the ui with the mesh name
		mesh_node = self.get_attribute_value(self.item_node, 'rh_mesh_base')
		if mesh_node:				
	
			# set the base mesh
			self.item_base_mesh = mesh	
	
			# add mesh attr
			pymel.lockNode(mesh, lock=False)
			
			if self.item_type == 'Weapon':
				# skin the mesh
				if not skincluster:				
					self.do_item_skin_mesh(['weapon_grip'], mesh)
					
				if not mesh.hasAttr(self.item_type_attr):
					pymel.addAttr(mesh, ln=self.item_type_attr, at='bool', keyable=False, dv=1)
					mesh.setAttr(self.item_type_attr, lock=True)
			else:
				# skin the mesh
				if not skincluster:				
					self.do_item_skin_mesh(['frame'], mesh)					
					
				if not mesh.hasAttr(self.item_type_att):
					pymel.addAttr(mesh, ln=self.item_type_attr, at='bool', keyable=False, dv=1)
					mesh.setAttr(self.item_type_attr, lock=True)			
	
			# sort the mesh into the proper Mesh sub group
			mat_group = self.get_material_group(index=0)
			if mat_group:
				pymel.lockNode(mat_group, lock=False)
	
				#pymel.lockNode(mat_group, lock=False)
				pymel.parent(mesh, mat_group)
	
				# update the material attribute on the mat_grp													
				mats = rh_maya.get_shader_connections(mesh)
				rh_maya.setAttrSpecial(mat_group, 'rh_material', mats, multi=True, keyable=False, h=False, lock=True)	
				pymel.lockNode(mat_group, lock=True)
			else:
				cmds.warning('A valid Mat group was not found!!')

	
		else:
			cmds.warning('When adding the base_mesh attributes the attr did not get set on the item node properly!\nThe attr got made but didnt get connected.')
			return False
		
		return True
		

	def on_pressed_mesh_picked(self, base_mesh=False):
		"""
		Update the item base mesh based on user input

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:30:11 PM
		"""	
		
		selection = pymel.ls(sl=True)

		# make sure the selected mesh is valid
		is_valid, mesh, mesh_materials, error_msg = self.validate_mesh(is_base=base_mesh)
		if not is_valid:
			cmds.warning(error_msg)			
			if selection:
				pymel.select(selection)
			return False
		
		# unlock parent and freeze transforms
		pymel.lockNode(mesh, lock=False)
		self.check_transforms(mesh)

		# see if the mesh given is the same as the existing mesh		
		if self.item_base_mesh:
			if mesh == self.item_base_mesh:
				cmds.warning('This is the same base mesh! Derp')				
				if selection:
					pymel.select(selection)				
				return False

		# store it in the UI until we hit accept
		if not base_mesh:
			if not self.item_base_mesh:
				cmds.warning('You must have a Base Mesh assigned to the item first!')				
				if selection:
					pymel.select(selection)				
				return False

			# Dont keep if its an existing item mesh
			if mesh in self.item_meshes.keys():
				cmds.warning('This mesh is already assigned to the item!\nMesh: {0}'.format(mesh.nodeName()))				
				if selection:
					pymel.select(selection)				
				return False

			# flag this off
			self.add_bone_picked = False

			# See if mesh is already skinned
			skincluster = mesh.listHistory(type="skinCluster")
			if skincluster:
				non_joints = []
				non_joints_string = ''
				influences = rh_maya.get_skincluster_influences(mesh)
				for inf in influences:
					if not inf in self.get_item_bones():
						non_joints.append(inf)
						non_joints_string += ' {0}\n'.format(inf.nodeName())

				if non_joints:		
					if len(non_joints) == 1:
						self.temp_bone = non_joints[0]
						self.add_bone_picked = True
					else:				
						if selection:
							pymel.select(selection)												
						query_txt = 'The mesh you are adding is already skinned and the joints that it is skinned to are not item joints.\n\nPlease correct then add the mesh again.\nYou may need to delete the history on the mesh to continue.\n\n Mesh: {0}\n Joints: {1}'.format(mesh.nodeName(), non_joints_string) 
						cmds.confirmDialog( title='Item Rigger: Add Mesh', message=query_txt)						
						return False				
				else:
					if influences:
						if len(influences) == 1:
							infl = influences[0]
							if not infl in self.item_bones:
								self.temp_bone = infl

				query_txt = 'The mesh you are adding is already skinned.\nIf this is intentional would you like to keep the skinning and any existing rigging?'				
				result = cmds.confirmDialog( title='Item Rigger: Add Mesh', message=query_txt, button=[ 'Keep Skinning', 'Delete Skinning', 'Cancel' ], defaultButton='Keep Skinning', cancelButton='Cancel', dismissString='Cancel' )			
				if result == 'Keep Skinning':
					self.keep_skinning = True
				elif result == 'Delete Skinning':
					self.temp_bone = None
				elif result == 'Cancel':
					self.temp_bone = None
					if selection:
						pymel.select(selection)											
					return False
			else:
				# attempt to load the bone if no skinning was found
				bone = self.get_attribute_value(mesh, 'rh_bone')
				if bone:
					self.temp_bone = bone
					if not self.temp_bone in self.item_bones:
						self.add_bone_picked = True				
				
			# keep existing control assigned
			control = self.get_attribute_value(mesh, 'rh_control')
			if control:
				self.temp_control = control
				parent_control = self.get_attribute_value(control, 'rh_child_control')
				if parent_control:
					self.update_parent_control_combo(parent_control)

			self.temp_mesh = mesh
			self.temp_materials = mesh_materials			
			self.update_ui()
			if selection:
				pymel.select(selection)									
			return True

		if base_mesh:
			add_mesh = self.do_add_base_mesh(mesh, mesh_materials)
			if selection:
				pymel.select(selection)

		self.update_ui()

	def on_scrollbar_changed( self, event ):
		"""
		Detect the scrollbar changing

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/15/2015 11:28:50 AM
		"""		

		if not self.vertical_bar.minimum() == self.vertical_bar.maximum(): #self.vertical_bar.isVisible():
			add_value = 0
			if not self.vertical_bar.value() == 0:
				self.update_anim_window_size( add = True )

	def get_item_export_path(self):
		"""
		Enter a description of the function here.
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/3/2014 11:27:25 AM
		"""

		item_folder = 'weapons'
		if not self.item_type == 'Weapon':
			item_folder = 'vehicles'
		export_path = None
		if self.item_name:
			export_path = os.path.join(PROJECT_ART_PATH, r'''{0}/{1}/export/'''.format(item_folder, self.item_name)).replace("\\","/")
		return export_path
	

	def on_pressed_accept_name(self):		
		"""
		Handle updating the item name

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:38:04 PM
		"""

		# Update the item name data
		item_name = self.textEditor.text()
		if not item_name:
			cmds.warning('You must set a valid name.')
			return False
		
		# is the item already named
		update_name = True
		if self.item_name:
			if item_name.lower() == self.item_name.lower():
				update_name = False				

		if update_name:
			self.item_name = item_name
			item_folder = 'weapons'
			if self.item_type == 'Vehicle':
				item_folder = 'vehicles'			

			# save the item file			
			item_base_path = os.path.join(PROJECT_ART_PATH, '''{1}/{0}/rig/{0}_rig.ma'''.format(item_name, item_folder)).replace("\\","/")
			try:
				os.makedirs(item_base_path)
			except:
				pass

			mark_for_add = False
			if not os.path.lexists(item_base_path):
				mark_for_add = True

			# save the file
			cmds.file(rename = os.path.basename(item_base_path))
			try:
				pymel.saveAs(item_base_path)
			except RuntimeError:
				pass

			# add to perforce		
			try:
				mark_add, error_msg = rh_maya.m_perforce.mark_for_add( item_base_path, quiet=True)			
			except:
				error_msg = 'Could not add the file to perforce: {0}'.format( item_base_path )
				cmds.warning( error_msg )		

			# Check to see if we already have a item node in the scene		
			if not self.item_node:
				item_node = rh_maya.weapon_create_rig(self.item_name)
				if item_node:
					self.item_node = item_node
					self._init_item_()				
				else:
					return False

			# update the item name
			self.update_item_name()
			
			message = 'Make sure to position your Mesh weapon handle on the origin!\nThe weapon should also be facing down the -Y axis.\n\nAlso, make sure your meshes are named appropriately for rigging.'
			cmds.confirmDialog(t='Item Rigger', m=message)

		# Turn off Settings Layout
		self.remove_layout(self.rename_layout)
		self.active_rename_layout = False			

		# Turn Item Named Layout
		self.create_item_name_ui()
		self.main_layout.addLayout(self.item_name_layout)
		self.active_item_name_layout = True

		self.update_ui()


	@Slot()
	def on_mesh_name_changed( self, row, col ):		
		"""
		If the value of the mesh name field has changed update it here

		*Arguments:*
		* ``row`` row index of currently changed cell.
		* ``col`` col index of currently changed cell.

		*Keyword Arguments:*
		* ``Argument`` Enter a description for the keyword argument here.

		*Returns:*
		* ``Value`` If any, enter a description for the return value here.

		*Examples:* ::

		Enter code examples here. (optional field)

		*Todo:*
		* Enter thing to do. (optional field)

		*Author:*
		* Randall Hess, randall.hess@gmail.com, 11/4/2014 12:29:37 PM
		"""		
		
		new_name = str(self.tw_meshes.item(row,col).text())
		if cmds.objExists(new_name):
			cmds.warning('An object with this name already exists! Name: {0}'.format(new_name))
			new_name = ''
			self.tw_meshes.blockSignals(True)
			self.tw_meshes.item(row, col).setText(self.selected_item_name)
			self.tw_meshes.blockSignals(False)			
			return
			
		if new_name == '' or not rh_maya.validate_text(new_name, numbers=True):
			cmds.confirmDialog(title = "ItemRigger: Warning", message = 'Your mesh names can not have special characters!\nName: {0}\n\nAvoid using these characters:\n{1}\n\nReverting back to the previous name.'.format( new_name, "!@#$%^&*()[]{};:,./<>?\|`~-=+" ) )
			self.tw_meshes.blockSignals(True)
			self.tw_meshes.item(row, col).setText(self.selected_item_name)
			self.tw_meshes.blockSignals(False)			
			return

		# if the name is the same just return
		try:						
			if new_name.lower() == self.selected_item_name.lower():
				return				
		except KeyError:
			pass
	
		# update mesh name data
		if new_name:
			if self.selected_item_name in self.item_meshes.keys():
				for mesh in self.item_meshes.keys():
					if mesh.nodeName() == self.selected_item_name:
						mesh_locked = mesh.isLocked()
						pymel.lockNode(mesh, lock=False)
						pymel.rename(mesh, new_name)
						if mesh_locked:
							pymel.lockNode(mesh, lock=True)
						
						# set Mesh type (D) or (S)
						if self.selected_item_name in self.item_attachment_names:
							# update name list
							index = self.item_attachment_names.index(self.selected_item_name)
							self.item_attachment_names.insert(index, new_name)
							self.item_attachment_names.remove(self.selected_item_name)
							attach_text = new_name
							if mesh.hasAttr('rh_static_mesh'):
								mesh_type = self.get_attribute_value(mesh, 'rh_static_mesh')
								if mesh_type:
									attach_text = '(S) {0}'.format(new_name)
								else:
									attach_text = '(D) {0}'.format(new_name)									
							self.tw_meshes.blockSignals(True)
							self.tw_meshes.item(row, col).setText(attach_text)
							self.tw_meshes.blockSignals(False)						
						break


	def on_pressed_copy_pivot(self):
		"""
		Copy pivot from source object to target object

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ```` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/27/2014 6:09:17 PM
		"""

		selection = pymel.ls(sl=True)
		if not len(selection) == 2:
			cmds.warning('You must select 2 objects. The source object then the target object to copy a pivot.')
			return

		# object must have a .matrix value
		for obj in selection:
			if not pymel.hasAttr(obj, 'matrix'):
				cmds.warning('You must select 2 TRANSFORM objects. The source object then the target object to copy a pivot.')				
				return

		source, target = selection

		# dont move certain objects
		if target in self.item_meshes.keys() or target in self.item_material_groups:
			cmds.warning('The target mesh you have selected is an item mesh. We dont change pivots on the meshes.')

		if target in self.get_item_controls():
			parent = rh_maya.get_obj_parent(target, parent_before='rig_grp')			
			if parent:
				with pymel.UndoChunk():
					all_constraints = {}
					pymel.select(cl=True)
					pymel.select(parent)
					# get the constraint source so we can rebuild
					constraints= pymel.listConnections(parent, type='constraint')
					constraints = list(set(constraints))
					if constraints:
						for const in constraints:
							target_nodes = rh_maya.get_constraint_targets(const)
							if target_nodes:
								if type(const) == pymel.nodetypes.ParentConstraint:
									all_constraints['parent'] = target_nodes
								elif type(const) == pymel.nodetypes.ScaleConstraint:
									all_constraints['scale'] = target_nodes

						# delete the constraints
						pymel.delete(constraints)

						# transfer the pivot
						rh_maya.transfer_pivot(source=source, target=parent, freeze=False)

						# rebuild the constraints
						for const, nodes in all_constraints.iteritems():
							if const == 'parent':
								constraint = pymel.parentConstraint(nodes, parent, mo=True, weight=1.0)							
							elif const == 'scale':
								constraint = pymel.scaleConstraint(nodes, parent, mo=True, weight=1.0)							
			else:
				with pymel.UndoChunk():
					# transfer the pivot
					rh_maya.transfer_pivot(source=source, target=target, freeze=False)				
		else:
			with pymel.UndoChunk():
				rh_maya.transfer_pivot(source=source, target=target, freeze=True)


	def on_pressed_ctrl_scale(self, scale):
		"""
		Scale selected controller

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/29/2014 4:45:40 PM
		"""

		new_sel = pymel.ls(sl=True, type='transform')
		with pymel.UndoChunk():		
			if len(new_sel) == 1:
				control = new_sel[0]
				if control:
					shape = control.getShape()
					if shape:
						pymel.select(cl=True)
						pymel.select(control)					
						pymel.selectMode(co=True)
						maya.mel.eval('SelectAll;')
						scale_val = 1.1
						if scale == 0:
							scale_val = -0.9
						maya.mel.eval('scale -r -ocp {0} {0} {0};'.format(scale_val))
						pymel.selectMode(o=True)
						pymel.select(cl=True)
						pymel.select(new_sel)
					else:
						cmds.warning('Select a single shape node.')
				else:
					cmds.warning('Select a single shape node.')
			else:
				cmds.warning('Select a single shape node.')


	def on_pressed_rot_90_axis(self, val):
		"""
		Rotate selected controller

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/29/2014 4:45:17 PM
		"""

		new_sel = pymel.ls(sl=True, type='transform')
		with pymel.UndoChunk():
			if len(new_sel) == 1:
				control = new_sel[0]	
				if control:
					shape = control.getShape()
					if shape:
						rot_val = 90
						#if not pos:
							#rot_val = -90
						x_val, y_val, z_val = [0.0, 0.0, 0.0]
						if val == 0:					
							x_val = rot_val
						elif val == 1:
							y_val = rot_val
						elif val == 2:
							z_val = rot_val					
						pymel.select(cl=True)
						pymel.select(control)
						pymel.selectMode(co=True)
						maya.mel.eval('SelectAll;')					
						maya.mel.eval('rotate -r -ocp -os -fo {0} {1} {2};'.format(x_val, y_val, z_val))
						#maya.mel.eval('scale -r -p 0cm 0cm 0cm {0} {0} {0};'.format(scale_val))
						pymel.selectMode(o=True)
						pymel.select(cl=True)
						pymel.select(new_sel)
					else:
						cmds.warning('Select a single shape node.')					
				else:
					cmds.warning('Select a single shape node.')				
			else:
				cmds.warning('Select a single shape node.')			
						

	def on_pressed_color_index_changed(self):
		"""
		Change color on selected shape

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 10/29/2014 6:03:38 PM
		"""

		sel = pymel.ls(sl=True)
		with pymel.UndoChunk():
			new_sel = pymel.ls(sl=True, type='transform')
			if len(new_sel) == 1:
				pymel.select(cl=True)
				control = new_sel[0]
				if control:
					shapes = control.getShapes()
					if shapes:
						for shape in shapes:
							color_index = self.set_color_combo.currentIndex() + 1
							shape.setAttr('overrideEnabled', True)
							shape.setAttr('overrideColor', color_index)
					else:
						cmds.warning('Select a single shape node to change the color on.')
				else:
					cmds.warning('Select a single shape node to change the color on.')					
			else:
				cmds.warning('Select a single shape node to change the color on.')
		pymel.select(sel)


	def on_pressed_create_listbox_control(self):
		"""
		Create a control from the listbox selection

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/24/2014 7:41:25 PM
		"""

		obj = None
		selection = pymel.ls(sl=True)
		if len(selection) == 1:
			obj = selection[0]
		else:
			cmds.warning('Select a single object to snap the newly created control object to!')
			return
			
		create_cmd = ''
		
		# get the name of the control from the selected comboBox item
		control_name = self.add_ctrl_combo.currentText()
		if not control_name:
			cmds.warning('Select a proper entry from the list of control names.')
			return
		
		if control_name == 'arrow':
			create_cmd = ('curve -d 1 -p 0 0.6724194 0.4034517 -p 0 0 0.4034517 -p 0 0 0.6724194 -p 0 -0.4034517 0 -p 0 0 -0.6724194 -p 0 0 -0.4034517 -p 0 0.6724194 -0.4034517 -p 0 0.6724194 0.4034517 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -n "arrow#"')
		elif control_name == 'cross':
			create_cmd = ('curve -d 1 -p 1 0 -1 -p 2 0 -1 -p 2 0 1 -p 1 0 1 -p 1 0 2 -p -1 0 2 -p -1 0 1 -p -2 0 1 -p -2 0 -1 -p -1 0 -1 -p -1 0 -2 -p 1 0 -2 -p 1 0 -1 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -n "cross#";')
		elif control_name == 'square':
			create_cmd = ('curve -d 1 -p -1 0 1 -p 1 0 1 -p 1 0 -1 -p -1 0 -1 -p -1 0 1 -k 0 -k 1 -k 2 -k 3 -k 4 -n "square#";')
		elif control_name == 'cube':
			create_cmd = ('curve -d 1 -p -0.5 0.5 0.5 -p 0.5 0.5 0.5 -p 0.5 0.5 -0.5 -p -0.5 0.5 -0.5 -p -0.5 0.5 0.5 -p -0.5 -0.5 0.5 -p -0.5 -0.5 -0.5 -p 0.5 -0.5 -0.5 -p 0.5 -0.5 0.5 -p -0.5 -0.5 0.5 -p 0.5 -0.5 0.5 -p 0.5 0.5 0.5 -p 0.5 0.5 -0.5 -p 0.5 -0.5 -0.5 -p -0.5 -0.5 -0.5 -p -0.5 0.5 -0.5 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -n "cube#";')
		elif control_name == 'orient':
			create_cmd = ('curve -d 3 -p 0.0959835 0.604001 -0.0987656 -p 0.500783 0.500458 -0.0987656 -p 0.751175 0.327886 -0.0987656 -p 0.751175 0.327886 -0.0987656 -p 0.751175 0.327886 -0.336638 -p 0.751175 0.327886 -0.336638 -p 1.001567 0 0 -p 1.001567 0 0 -p 0.751175 0.327886 0.336638 -p 0.751175 0.327886 0.336638 -p 0.751175 0.327886 0.0987656 -p 0.751175 0.327886 0.0987656 -p 0.500783 0.500458 0.0987656 -p 0.0959835 0.604001 0.0987656 -p 0.0959835 0.604001 0.0987656 -p 0.0959835 0.500458 0.500783 -p 0.0959835 0.327886 0.751175 -p 0.0959835 0.327886 0.751175 -p 0.336638 0.327886 0.751175 -p 0.336638 0.327886 0.751175 -p 0 0 1.001567 -p 0 0 1.001567 -p -0.336638 0.327886 0.751175 -p -0.336638 0.327886 0.751175 -p -0.0959835 0.327886 0.751175 -p -0.0959835 0.327886 0.751175 -p -0.0959835 0.500458 0.500783 -p -0.0959835 0.604001 0.0987656 -p -0.0959835 0.604001 0.0987656 -p -0.500783 0.500458 0.0987656 -p -0.751175 0.327886 0.0987656 -p -0.751175 0.327886 0.0987656 -p -0.751175 0.327886 0.336638 -p -0.751175 0.327886 0.336638 -p -1.001567 0 0 -p -1.001567 0 0 -p -0.751175 0.327886 -0.336638 -p -0.751175 0.327886 -0.336638 -p -0.751175 0.327886 -0.0987656 -p -0.751175 0.327886 -0.0987656 -p -0.500783 0.500458 -0.0987656 -p -0.0959835 0.604001 -0.0987656 -p -0.0959835 0.604001 -0.0987656 -p -0.0959835 0.500458 -0.500783 -p -0.0959835 0.327886 -0.751175 -p -0.0959835 0.327886 -0.751175 -p -0.336638 0.327886 -0.751175 -p -0.336638 0.327886 -0.751175 -p 0 0 -1.001567 -p 0 0 -1.001567 -p 0.336638 0.327886 -0.751175 -p 0.336638 0.327886 -0.751175 -p 0.0959835 0.327886 -0.751175 -p 0.0959835 0.327886 -0.751175 -p 0.0959835 0.500458 -0.500783 -p 0.0959835 0.604001 -0.0987656 -k 0 -k 0 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -k 16 -k 17 -k 18 -k 19 -k 20 -k 21 -k 22 -k 23 -k 24 -k 25 -k 26 -k 27 -k 28 -k 29 -k 30 -k 31 -k 32 -k 33 -k 34 -k 35 -k 36 -k 37 -k 38 -k 39 -k 40 -k 41 -k 42 -k 43 -k 44 -k 45 -k 46 -k 47 -k 48 -k 49 -k 50 -k 51 -k 52 -k 53 -k 53 -k 53 -n "orient#";')
		elif control_name == 'circleY':
			create_cmd = ('string $tc[] = `circle -c 0 0 0 -nr 0 1 0 -sw 360 -r 1 -d 3 -ut 0 -tol 0.01 -s 8 -ch 1`; $c=$tc[0];')
		elif control_name == 'circleZ':
			create_cmd = ('string $tc[] = `circle -c 0 0 0 -nr 0 0 1 -sw 360 -r 1 -d 3 -ut 0 -tol 0.01 -s 8 -ch 1`; $c=$tc[0];')
		elif control_name == 'circleX':
			create_cmd = ('string $tc[] = `circle -c 0 0 0 -nr 1 0 0 -sw 360 -r 1 -d 3 -ut 0 -tol 0.01 -s 8 -ch 1`;	$c=$tc[0];')
		elif control_name == 'sphere':	
			create_cmd = ('curve -d 1 -p 0 3 0 -p 0 2 -2 -p 0 0 -3 -p 0 -2 -2 -p 0 -3 0 -p 0 -2 2 -p 0 0 3 -p 0 2 2 -p 0 3 0 -p 2 2 0 -p 3 0 0 -p 2 -2 0 -p 0 -3 0 -p -2 -2 0 -p -3 0 0 -p -2 2 0 -p 0 3 0 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -k 16 -n "sphere#";')
		elif control_name == 'plus':
			create_cmd = ('curve -d 1 -p 0 1 0 -p 0 -1 0 -p 0 0 0 -p -1 0 0 -p 1 0 0 -p 0 0 0 -p 0 0 1 -p 0 0 -1 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -n "plus#";')
		else:
			cmds.warning('Select a proper entry from the list of control names.')
			return	

		# create the control
		with pymel.UndoChunk():
			pymel.select(cl=True)
			maya.mel.eval(create_cmd)

			control = None
			new_sel = pymel.ls(sl=True)
			if len(new_sel) == 1:
				control = new_sel[0]

			if control:		
				pymel.selectMode(co=True)
				maya.mel.eval('SelectAll;')
				scale_val = 3
				maya.mel.eval('scale -r -p 0cm 0cm 0cm {0} {0} {0};'.format(scale_val))
				pymel.selectMode(o=True)
				if obj:
					constraint = pymel.parentConstraint(obj, control, mo=False, weight=1.0)							
					if constraint:
						pymel.delete(constraint)
						
	
	def on_pressed_create_pivot_bone(self):
		"""
		Create a bone from the custom pivot context

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/24/2014 6:49:23 PM
		"""	

		with pymel.UndoChunk():
			rh_maya.create_pivot_bone()
			

	def on_pressed_transfer_mat(self):
		"""
		Copy material from mesh to other meshes
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/10/2014 10:08:17 AM
		"""
		
		with pymel.UndoChunk():
			rh_maya.transfer_shading_groups()
		

	def on_pressed_replace_mesh(self):
		"""
		Replace the item mesh with a new mesh, retaining skinweights and transform attributes
		
		*Arguments:*
			* ``None`` 
		
		*Keyword Arguments:*
			* ``None`` 
		
		*Returns:*
			* ``None`` 
		
		*Author:*
		* randall.hess, randall.hess@gmail.com, 11/9/2014 12:22:28 PM
		"""
		
		cmds.warning('Implement your own method to transfer skinweights to a new mesh and replace the shape to preserve all attributes')
		#with pymel.UndoChunk():			
			#rh_maya.replace_mesh()
			

	def on_pressed_create_cvc_bone(self):
		"""
		Create a joint from component selection

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/23/2014 3:22:45 PM
		"""

		with pymel.UndoChunk():
			rh_maya.create_cluster_bone()


	def on_pressed_rename(self):
		"""
		Handle renaming the item name

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:38:16 PM
		"""	

		if self.item_node:
			query_txt = 'Are you sure you want to rename the item mesh?\nIf you are unsure you probably dont want to do this.\n\n\nIf this item is already animated or used in game it will cause a lot of issues!!\n'
			result = cmds.confirmDialog( title='Item Rigger: Rename Item', message=query_txt, button=[ 'Yes', 'No','Cancel' ], defaultButton='No', cancelButton='Cancel',dismissString='Cancel' )
			if not result == 'Yes':			
				return False		

		# Turn Item Named Layout
		self.remove_layout(self.item_name_layout)
		self.active_item_name_layout = False

		# Turn off Export Layout
		if self.active_export_layout:
			self.remove_layout(self.export_layout)
			self.active_export_layout = False			

		# Turn On Settings Layout
		self.create_rename_item_ui()
		self.main_layout.addLayout(self.rename_layout)
		self.active_rename_layout = True

		self.textEditor.setFocus()		
		if self.item_name:
			self.textEditor.setText(self.item_name)
			self.accept_pushButton.setDisabled(False)


	def update_item_name(self):
		"""
		Update the item name and all associated names

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:37:42 PM
		"""

		if self.item_node:	
			# Update Item Name
			self.set_attribute_value(self.item_node, 'rh_item_name', self.item_name)

			# Update MESH grp name
			if self.item_mesh_group:			
				pymel.lockNode(self.item_mesh_group, lock = False)
				pymel.rename(self.item_mesh_group, 'MESH_' + self.item_name)				
				pymel.lockNode(self.item_mesh_group, lock = True)


	def retranslateUi(self):		
		self.setWindowTitle(QApplication.translate(WINDOW_TITLE, WINDOW_TITLE, None, QApplication.UnicodeUTF8))
	
	
	def create_material_group(self, materials):
		"""
		When adding a new mesh with a new material assigned
		Create a new material subgroup to organize meshes with

		*Arguments:*
			* ``None`` 

		*Keyword Arguments:*
			* ``None`` 

		*Returns:*
			* ``None`` 

		*Author:*
		* randall.hess, randall.hess@gmail.com, 9/11/2014 1:27:45 PM
		"""	
		
		with pymel.UndoChunk():
			# get the material index from the item node
			mat_index = self.item_node.getAttr('rh_material_index')
	
			# increment the material index and update the item node attribute
			new_index = int(mat_index + 1)
			index_string = str( new_index ).zfill( 2 )
			pymel.lockNode(self.item_node, lock=False)
			self.item_node.setAttr('rh_material_index', lock = False)
			self.item_node.setAttr('rh_material_index', new_index)
			self.item_node.setAttr('rh_material_index', lock = True)
	
			# create the new mat group under the mesh_grp and setup the material attribute message
			mat_group_name = 'Mat_' + index_string
			mat_group = pymel.group(empty=True, name=mat_group_name)
			rh_maya.lock_channels(mat_group)
			rh_maya.hide_channels(mat_group)
			mat_group.setAttr('v', keyable=False)
			
			rh_maya.setAttrSpecial(mat_group, 'rh_material', materials, multi=True, keyable=False, h=False, lock=True)	
			pymel.addAttr( mat_group, ln= 'rh_item_material_index', niceName = 'Material Index', at = 'double', defaultValue = new_index, minValue = 0.0, maxValue = 20.0, keyable = False, h = False )				
			mat_group.setAttr('rh_item_material_index', lock=True)
			pymel.parent(mat_group, self.item_mesh_group)	
		return mat_group


def run(*args, **kwargs):
	"""
	Opens the window for the Anim Exporter

	*Arguments:*
		* ``none ``

	*Keyword Arguments:*
		* ``none``

	*Returns:*
		* ``none``

	*Author:*
		* Randall.Hess
	"""

	global item_rigger_window
	try:
		item_rigger_window.close()
	except RuntimeError:
		pass
	except NameError:
		pass

	if cmds.window( WINDOW_TITLE, q=1, exists=1 ):
		cmds.deleteUI( WINDOW_TITLE, window=1 )

	item_rigger_window = ItemRigger()

if __name__ == '__main__':
	try:		
		run()
	except:		
		pass
