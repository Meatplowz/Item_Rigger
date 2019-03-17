"""
Maya Export Methods

Author: Randall Hess randall.hess@gmail.com
License: GNU General Public License v3.0
"""

import os
import maya.cmds as cmds
import maya.mel as mel
import pymel.core as pymel

import rh_maya_rigging

PERFORCE = None

# See my blog post for cleaning FBX files groups, layer, un-wanted meshes or nodes
# https://techanimator.blogspot.com/2017/04/flexible-fbx-with-fbx-python-sdk.html
try:
	import FBX_Scene
except:
	pass


def can_write_file(filepath):
	"""
	Make sure the user can write to a file

	*Arguments:*
	   * ``filepath`` File we want to write

	*Keyword Arguments:*
	   * ``None``   

	*Returns:*
	   * ``Bool``           Bool if the file can be written
	   * ``error_message``  Message to pass back for fail cases

	*Author:*
	* randall.hess, randall.hess@gmail.com, 09/02/2018 3:41:59 PM
	"""		

	# make sure we can save the current maya scene        
	error_msg = ''

	# see if there is a valid file
	if filepath is None:
		return False, 'A valid filepath was not given.'

	# make sure this is a valid file
	if not os.path.isfile(filepath):

		# if we have perforce access see if the file is in the depot
		if PERFORCE:
			# try to get the latest revision
			pass
			
		# This may be a new file
		if not os.path.isfile(filepath):
			return True, ''           

	# check the file attribute to see if it is writable
	file_is_writable = False
	if os.access(filepath, os.W_OK):
		file_is_writable = True
		return True, 'The File is already writable: {0}'.format(filepath)

	# make sure we can call p4 operations
	if PERFORCE:

		# checkout the file
		pass		

		# final check to make sure the file is writable
		if not os.access(filepath, os.W_OK):
			return False, 'File failed to check out and is not writable!'

		return True, 'File is now open for edit: {0}'.format(filepath)

	else:
		error_msg = 'The File is not writable and Perforce operations are not accessible to check out the file.\n{0}'.format(filepath)
		return False, error_msg	


def get_export_file(start_path=None, file_mode=0, caption='Export FBX File' ):
	"""
	Browse for the export file

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 3/16/2015 11:08:56 AM
	"""

	start_dir = ''
	if start_path:
		start_dir = start_path

	# pop open the dialog
	fbx_filter = "*.fbx Files ( *.fbx )"
	export_path = cmds.fileDialog2( fileFilter=fbx_filter, dialogStyle=1, fileMode=file_mode,
	                                startingDirectory=start_dir, caption=caption )		
	if export_path == None:
		return None
	else:
		export_path = export_path[0]
	
	# make sure the file is fbx
	if not export_path.lower().endswith('.fbx'):
		cmds.warning("You must set an fbx file to export!")
		return None
	
	# make sure the path is in the project animation directory
	export_path = export_path.lower().replace("\\","/")	

	return export_path


def set_fbx_options(custom_dict=None, reset=False, bake=False, start=None, end=None):
	"""
	Pass in a dictionary of values and sets FBX options accordingly for export.

	*Arguments:*
		* ``none``

	*Keyword Arguments:*
		* ``custom_dict`` Dictionary of option settings.
			Keys and default values:
			{
				'ascii': True, ( FBXExportInAscii )
				'upAxis': y, ( FBXExportUpAxis )
				'animationOnly': False, ( FBXExportAnimationOnly )
				'skeleton': True, ( FBXExportSkeleton )
				'skin': True, ( FBXExportSkin )
				'constraints': False, ( FBXExportConstraints )
				'cameras': True, ( FBXExportCameras )
				'shapes': True, ( FBXExportShapes )
				'scaleFactor': 1.0 ( FBXExportScaleFactor )
			}
		* ``reset`` Resets FBX options and returns.

	*Returns:*
		* ``True`` on success
		* ``False`` on error with custom_dict	

	*TODO:* ::
		*Find FBXExportSkeleton / Find out why it exists in theory but does not exist in practice

	*Author:*
	* Jason.Parks
	* randall.hess, randall.hess@gmail.com, 11/24/2014 6:23:20 PM
	"""	

	# Reset options
	pymel.mel.FBXResetExport()

	# FBX option default values
	option_dict = {
	    'ascii': True,
	    'upAxis': 'z',
	    'animationOnly': False,
	    'skeleton': True,
	    'skin': True,
	    'constraints': False,
	    'cameras': False,
	    'shapes': True,
	    'scaleFactor': 1.0,
	    'smoothMesh':False,
	    'smoothingGroups':True,
	    'hardEdges':False,
	    'tangents':False,
	}

	if custom_dict:
		option_dict = custom_dict

	# Set options according to option_dict values
	pymel.mel.FBXExportInAscii(v=option_dict['ascii'])
	pymel.mel.FBXExportUpAxis(option_dict['upAxis' ])
	pymel.mel.FBXExportAnimationOnly(v=option_dict['animationOnly'])
	pymel.mel.FBXExportSkins(v=option_dict['skin'])
	pymel.mel.FBXExportConstraints(v=option_dict['constraints'])
	pymel.mel.FBXExportCameras(v=option_dict['cameras'])
	pymel.mel.FBXExportShapes(v=option_dict['shapes'])
	pymel.mel.FBXExportScaleFactor(option_dict['scaleFactor'])
	pymel.mel.FBXExportSmoothMesh(v=option_dict['smoothMesh'])
	pymel.mel.FBXExportSmoothingGroups(v=option_dict['smoothingGroups'])
	pymel.mel.FBXExportHardEdges(v=option_dict['hardEdges'])
	pymel.mel.FBXExportTangents(v=option_dict['tangents'])

	if bake:
		# frame range
		pymel.mel.FBXExportBakeComplexAnimation(v=True)
		pymel.mel.FBXExportBakeComplexStart(v=start)
		pymel.mel.FBXExportBakeComplexEnd(v=end)

	return True
	

def export_weapon(item_type='Weapon'):
	"""
	Export a weapon model/rig

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 3/16/2015 9:41:51 AM
	"""

	error_msg = ''
	debug = False

	old_selection = pymel.ls(sl = True)

	# Get the weapon_root
	weapon_root = None
	weapon_mesh = None
	weapon_export_file = None

	try:
		weapon_root = cmds.ls( 'weapon_root' )[0]
	except:
		error_msg = '\n\nThis {0} file does not have a weapon_root skeleton hierarchy. This is not going to work.'.format(item_type)
		return False, error_msg		

	# if selection is one
	if len( old_selection ) == 1:		
		selection = old_selection[0]
		parent = None

		# list ancestors parent
		try:
			parent = pymel.listRelatives( selection, parent = True )
		except:
			mesh_found = False
			if pymel.nodeType(selection) == 'transform':
				if selection.nodeName().startswith('MESH_'):
					mesh_found = True	
			if not mesh_found:
				error_msg = 'The selection is not valid!'
				return False, error_msg

		if parent:
			parent = parent[0]			
			if parent.nodeName().startswith( 'MESH_' ):			
				weapon_mesh = parent
			elif selection.startswith('MESH_'):
				weapon_mesh = selection			

		elif selection.startswith('MESH_'):
			weapon_mesh = selection			

	# if we dont have a 'MESH_' grp found
	if not weapon_mesh:
		error_msg = '\n\nThe {0} mesh or {0} MESH_ group must be selected to export.'.format(item_type)
		return False, error_msg	

	try:
		# get MESH export file
		weapon_export_file = pymel.getAttr( weapon_mesh + '.export_filepath' )
	except:
		try:
			# get weapon_root export file
			weapon_export_file = pymel.getAttr( weapon_root + '.export_filepath' )
		except:
			pass

	# Create the export filename from the MESH grp naming
	if not weapon_export_file:
		
		weapon_export_file = get_export_file(start_path=None, file_mode=0, 
		                                    caption='Export FBX File')	
		
		if not weapon_export_file:
			return False, 'Export file not given!'
		
		# validate the weapon export file and if we can export
		weapon_export_file = weapon_export_file.replace('//', '/')		
		
		try:
			# set weapon_root export file
			pymel.lockNode(weapon_mesh, lock=False)	
			if not weapon_mesh.hasAttr('export'):
				pymel.addAttr(weapon_mesh, ln='export_filepath', dt = 'string', keyable = False )				
			weapon_mesh.setAttr('export_filepath', weapon_export_file)
			pymel.lockNode(weapon_mesh, lock=True)
		except:
			pass

	# make sure the file is writable
	try:			
		can_export, error_msg = can_write_file(weapon_export_file)
	except:
		can_export = False
		error_msg = 'The file given cannot be written. File:{0}'.format(weapon_export_file)

	if not can_export:
		return False, error_msg	

	# check the weapon mesh
	if not weapon_mesh or not pymel.objExists(weapon_mesh):
		error_msg = 'The {0} mesh is not assigned to the weapon root message!'.format(item_type)
		return False, error_msg	

	# get the skincluster from the weapon mesh
	weapon_mesh_name = weapon_mesh
	py_weapon_mesh = pymel.PyNode(weapon_mesh_name)
	if not py_weapon_mesh:
		error_msg = 'The {0} mesh was not found!'.format(item_type)
		return False, error_msg
	weapon_meshes = [py_weapon_mesh]

	# get the influence objects
	skinned_joints = {}	
	all_materials = []
	non_skinned_meshes = False

	pymel.select(weapon_mesh, replace=True)

	# clean off unicode starting characters
	weapon_mesh = str( weapon_mesh )
	if not weapon_mesh.startswith( 'MESH' ) and not weapon_mesh == 'MESH':		
		# handle a single mesh selected weapon
		skincluster = mel.eval( 'findRelatedSkinCluster {0};'.format( weapon_mesh_name ) )	
		if skincluster:	
			# check if it's a skinCluster
			if cmds.nodeType(skincluster) != 'skinCluster':
				error_msg = 'The mesh does not have a valid skinCluster!\nWeapon Mesh: {0}'.format( weapon_mesh )
				return False, error_msg
		else:
			error_msg = 'The mesh does not have a skinCluster!'
			return False, error_msg
	else:		
		meshes = pymel.ls( py_weapon_mesh, dag = True, type = 'transform', shapes = False)

		# make sure all meshes are skinned under the export group		
		for mesh in meshes:			
			mesh_shape = mesh.listRelatives(s=True, ni=True)
			if mesh_shape:				
				pymel.select( mesh, replace = True )
				skincluster = mesh.listHistory(type="skinCluster")
				if not skincluster:
					non_skinned_meshes = True
					error_msg += ' ' + mesh.nodeName() + '\n'					

		# return if unskinned meshes were found
		if non_skinned_meshes:			 
			error_pre = 'You have non-skinned meshes in your export group. Please fix or remove them.\n\n' + error_msg
			return False, error_pre

		renamed_shading_grps = []
		for mesh in meshes:
			# make sure the transform has shapes
			if mesh.getShapes():
				pymel.select( mesh, replace = True )		
				skincluster = mesh.listHistory(type="skinCluster")
				if skincluster:

					# store off the mesh piece to export
					if not mesh in weapon_meshes:
						weapon_meshes.append(mesh)

					# get the influence members# get the influence members
					influences = rh_maya_rigging.get_skincluster_influences(mesh)
					if len(influences) == 0:						
						error_msg = 'No influence objects found in the skinCluster!\n Mesh: {0}\n SkinCluster: {1}'.format( mesh_name, skincluster )
						print error_msg

					else:
						for infl in influences:
							if not pymel.nodeType( infl ) == 'joint':
								print 'WARNING!! Influence is not a joint!\nInfluence: {0}'.format( infl )
							else:
								skinned_joints[ infl ] = skincluster[0]

	# get a list of the export bones	
	# base bones, bones that are skinned and bones that are constrained to be animated
	export_objects = []

	# weapon_base bones
	base_bones = ['weapon_root','weapon_grip','weapon_mag','weapon_muzzle_flash','weapon_secondary_grip','weapon_trigger']
	for bone in base_bones:
		if not cmds.objExists(bone):
			continue
		pynode = pymel.PyNode(bone)
		if pynode:
			export_objects.append(pynode)

	# add the skinned joints
	for joint in skinned_joints.keys():
		if not joint in export_objects:
			export_objects.append(joint)

	# get the anim joints	
	all_joints = pymel.ls('weapon_root', dag = True, type = 'joint')
	
	## OPTIONAL: only export constrained joints
	#anim_joints = []
	#for joint in all_joints:				
		#parent_constraints = pymel.listConnections( joint, type = "parentConstraint" )					
		#if parent_constraints:
			#parent_constraints = list( set( parent_constraints ) )
			#if len( parent_constraints ) > 0:
				## assuming if a parent constraint is found this is an animatable weapon joint
				#anim_joints.append( joint )
	# add the anim joints
	#for joint in anim_joints:
		#if not joint in export_objects:
			#export_objects.append( joint )
	
	# select for export 
	pymel.select( clear = True )
	pymel.select( export_objects )

	# get all mesh parents	
	# flag the parents to export up the hierarchy,
	# if we dont do this the remove fbx post process procedure will delete joints we need	
	for mesh in weapon_meshes:
		mesh_parents = mesh.getAllParents()
		if mesh_parents:
			for obj in mesh_parents:
				if not obj in weapon_meshes:
					weapon_meshes.append( obj )

	# do a check to make sure mesh names aren't found in the bone names
	joint_names = [j.nodeName() for j in export_objects]
	mesh_names = [m.nodeName() for m in weapon_meshes]

		# make sure camera names aren't in joint or mesh names
	maya_names = ['persp','front','side','top','left','bottom']
	dupe_names = set(maya_names).intersection(set(joint_names))
	if dupe_names:
		if len( dupe_names ) > 0:
			dupe_string = ''
			for dupe in dupe_names:
				dupe_string += dupe + "\n"
			error_msg = '\nYou have joint names with the same names as reserved Maya names, this is not valid.\nPlease fix the joint names to continue.\n\Rename Joint Objects:\n{0}'.format( dupe_string )
			return False, error_msg

	dupe_names = set(maya_names).intersection(set(mesh_names))
	if dupe_names:
		if len( dupe_names ) > 0:
			dupe_string = ''
			for dupe in dupe_names:
				dupe_string += dupe + "\n"
			error_msg = '\nYou have mesh names with the same names as reserved Maya names, this is not valid.\nPlease fix the mesh names to continue.\n\Rename Mesh Objects:\n{0}'.format( dupe_string )
			return False, error_msg

	dupe_names = set(mesh_names).intersection(set(joint_names))	
	if dupe_names:
		if len( dupe_names ) > 0:
			dupe_string = ''
			for dupe in dupe_names:
				dupe_string += dupe + "\n"
			error_msg = '\nYou have mesh names with the same names as your bone names, this is not valid.\nPlease fix the mesh names to continue.\n\Rename Mesh Objects:\n{0}'.format( dupe_string )			
			return False, error_msg
			
	if debug:
		print 'Exporting Selection'
		print ' Bones:'
		for obj in export_objects:
			print '  {0}'.format( obj )		
		print ' Meshes:'
	
	# select meshes for export
	for mesh in weapon_meshes:
		pymel.select( weapon_meshes, add = True )
		if debug: print '  {0}'.format( mesh )

	if debug: print '\n'

	# print selected
	sel = cmds.ls(sl=True)
	
	# weapon export options
	fbx_options = { 'ascii': True,
	                'upAxis': 'z',
	                'animationOnly': False,
	                'skeleton': True,
	                'skin': True,
	                'constraints': False,
	                'cameras': False,
	                'shapes': False,
	                'scaleFactor': 1.0,
	                'smoothMesh':False,
	                'smoothingGroups':True,
	                'hardEdges':False,
	                'tangents':False,
	                }

	set_fbx_options(custom_dict=fbx_options)	
	try:
		pymel.mel.FBXExport( f= weapon_export_file, s=True ) #@UndefinedVariable
	except:
		error_msg = 'Error running FBX Export!\nCheck path for invalid characters.\nThe file may also not be getting checked out.\n\nPath: {0}'.format( weapon_export_file )
		return False, error_msg

	# mark the export file for add	
	# Perforce Add Operation	

	# select original selection
	pymel.select( clear = True )
	pymel.select( old_selection )	

	# Process FBX File to Clean out objects we dont need
	# See my blog post on how to Post Process FBX files after exporting them
	# https://techanimator.blogspot.com/2017/04/flexible-fbx-with-fbx-python-sdk.html
	#for mesh in weapon_meshes:		
		#export_objects.append( mesh )
	#print '\n-Cleaning {0} FBX-'.format(item_type)
	#update_weapon_fbx = Fbx_Scene.update_weapon_scene(weapon_export_file, export_objects)
	#if not update_weapon_fbx:
		#error_msg = 'Error running FBX {0} Update\nPath: {1}'.format( item_type, weapon_export_file )
		#return False, error_msg

	export_status = '\n{0} Exported:\n{1}'.format( item_type, weapon_export_file )
	return True, export_status


def export_weapon_prep(quiet=False, item_type='Weapon'):
	"""
	Based on the objects selected determine how to export the weapon or weapon parts

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 2/26/2016 10:06:26 AM
	"""

	selection = pymel.ls( sl = True )

	# Try to find a singular weapon MESH
	if len( selection ) == 0:
		meshes = pymel.ls('MESH_*')
		if meshes:
			if len(meshes) == 1:
				selection = [meshes[0]]

	# get the parent 'MESH' groups from selection for exporting
	parents = {}
	log_export = ''
	if not quiet:
		log_export = '{0} Export\n'.format(item_type)
	do_export = None

	# loop through selection to find like parents
	for obj in selection:
		if not pymel.nodeType(obj) == 'transform':
			log_export += '\nFAILED Exporting: {0}'.format( obj )
			log_export += '\n  The {0} Mesh or {0} MESH group was not selected.'.format(item_type)
			do_export = False
			break

		parent = None
		try:
			parent = pymel.listRelatives( obj, parent = True )[0]
		except:
			pass
		if parent:

			# check current object name first
			check_parent = True
			if obj.startswith('MESH_'):
				if not obj.nodeName() in parents.keys():
					parents[obj] = []								
					check_parent = False

			if check_parent:
				if parent.nodeName().startswith('MESH_'):
					if parent in parents.keys():
						values = parents[parent]
						if not obj in values:
							values.append( obj )
						parents[parent] = values
					else:
						parents[parent] = [obj]
				else:				
					log_export += '\nFAILED Exporting: {0}'.format( obj )
					log_export += '\n  The MESH group is not named correctly.\n  It should be "MESH_{0}Name"\n\n  Make sure there are no extra spaces or underscores in the name.'.format(item_type)
					do_export = False					

		else:
			if obj.nodeName().startswith('MESH_'):
				if not obj in parents.keys():
					parents[obj] = []

	# export each weapon selection	
	for parent, children in parents.iteritems():
		if parent.startswith('MESH_PARTS_'):
			for child in children:
				do_export, return_msg = export_weapon_part(child, parent)				
				log_export += return_msg + '\n'				
		else:
			pymel.select(parent)
			do_export, return_msg = export_weapon(item_type=item_type)
			log_export += return_msg + '\n'

	#return_msg = 'Nothing valid was selected to export.'
	if do_export == None:
		log_export = 'Nothing was selected to export!'

	if not quiet:
		cmds.confirmDialog( t='{0} Export: Status'.format(item_type) , m=log_export, b='OK' )

	return True, log_export


def export_weapon_part(weapon_mesh, parent, weapon_export_file=None, is_static_mesh=False):
	"""
	Export chunks of weapon parts into different fbx files

	*Arguments:*
		* ``part`` Mesh object representing a part of a weapon
		* ``parent`` Mesh objects parent Group "MESH_PARTS_"

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 2/25/2016 5:20:38 PM
	"""

	old_selection = cmds.ls(sl=True)	
	debug = False

	# save channels for moving and resetting	
	stored_channels = {}	

	# get the weapon export path
	if not weapon_export_file:		
		error_msg = 'Failed to genearate the weapon export file'
		return False, error_msg
	else:
		if not os.path.lexists(os.path.basename(weapon_export_file)):
			try:
				os.makedirs(os.path.basename(weapon_export_file))		
			except:
				pass

	# make sure the path is valid
	try:			
		can_export, error_msg = can_write_file(weapon_export_file)
	except:
		can_export = False
		error_msg = 'Failed to validate export file with Perforce.'

	if not can_export:
		return False, error_msg	

	# names for filtering in the fbx cleanup
	export_names = [str(parent), str(weapon_mesh)]	
	for name in export_names:
		cmds.lockNode(name, lock=False)

	# objects to keep after export	
	export_objects = [parent, weapon_mesh]		

	# clean off unicode starting characters
	weapon_mesh = str(weapon_mesh)

	# select the weapon_mesh
	cmds.select(weapon_mesh, replace=True)	

	# determine if this is a skinned mesh or static mesh		
	skincluster = mel.eval( 'findRelatedSkinCluster {0};'.format( weapon_mesh ) )	
	if skincluster:		
		# get the influence members
		influences = cmds.skinCluster(skincluster, q = True, inf = True)
		if len(influences) == 0:						
			error_msg = 'No influence objects found in the skinCluster!\n Mesh: {0}\n SkinCluster: {1}'.format( weapon_mesh, skincluster )
			print error_msg		
		else:
			# add base bones
			base_bones = ['weapon_root','weapon_grip']
			for bone in base_bones:
				if cmds.objExists( bone ):
					export_objects.append( bone )
					export_names.append( bone )

			for infl in influences:
				if not cmds.nodeType( infl ) == 'joint':
					print 'Warning!! Influence is not a joint!\nInfluence: {0}'.format( infl )
				else:
					export_objects.append( infl )
					export_names.append( infl )
	else:
		is_static_mesh = True

	if is_static_mesh:

		# check scale
		scale_channels = ['.sx','.sy','.sz']
		for attr in scale_channels:
			value = pymel.getAttr( weapon_mesh + attr )
			if not value == 1:
				return False, '\n FAILED: Your mesh has improper scale values. You must Freeze Transformations!\n Mesh: {0}'.format( weapon_mesh )

		# store then zero out the translation values
		pymel.setAttr( weapon_mesh + '.v', lock = False, keyable = False, cb = True )
		channels = ['.tx','.ty','.tz','.rx','.ry','.rz']
		for attr in channels:			
			locked = pymel.getAttr( weapon_mesh + attr, lock = True)			
			value = pymel.getAttr( weapon_mesh + attr )
			locked = pymel.setAttr( weapon_mesh + attr, lock = False)
			stored_channels[ attr ] = value
			if not '.s' in attr:
				pymel.setAttr( weapon_mesh + attr, 0.0 )

		# rotation values should also be zero
		# check rotation values

	# select for export
	export_objects = list(set(export_objects))
	export_names = list(set(export_names))
	pymel.select( clear = True )
	pymel.select( export_objects )
	pymel.select( weapon_mesh, add = True )

	# print selected
	export_selection = cmds.ls( sl = True )
	if debug:
		print 'Exporting Selection'
		for obj in export_selection:
			print ' {0}'.format( obj )

	# EXPORT
	set_fbx_options()
	try:
		pymel.mel.FBXExport( f= weapon_export_file, s=True ) #@UndefinedVariable
	except:
		error_msg = 'Error running FBX Export!\nCheck path for invalid characters.\nThe file may also not be getting checked out.\n\nPath: {0}'.format( weapon_export_file )
		return False, error_msg

	# select original selection
	pymel.select( clear = True )
	pymel.select( old_selection )

	# reset static mesh channels
	if is_static_mesh:
		for attr, value in stored_channels.iteritems():			
			pymel.setAttr( weapon_mesh + attr, value )	

	## Process FBX File to Clean out objects we dont need
	#update_weapon_fbx = RHPython.Core.Py_Fbx.update_weapon_scene( weapon_export_file, export_names )	
	#if not update_weapon_fbx:
		#error_msg = 'Error running FBX Weapon Update\nPath: {0}'.format( weapon_export_file )
		#return False, error_msg	

	return True, '\n{0}'.format( weapon_export_file )