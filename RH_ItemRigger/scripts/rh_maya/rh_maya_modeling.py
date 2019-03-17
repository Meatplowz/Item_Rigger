"""
Modeling or Mesh Methods for use in Maya

Author: Randall Hess randall.hess@gmail.com
License: GNU General Public License v3.0
"""


import maya.cmds as cmds
import pymel.core as pymel


def get_mesh_materials(mesh, info=False):
	"""
	Get the materials from a mesh

	*Arguments:*
		* ``mesh`` PyNode Mesh

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``Material`` List of Pynode Shaders assigned to the mesh

	*Author:*
	* randall.hess, randall.hess@gmail.com, 9/11/2014 12:12:26 PM
	"""	
	
	# get shapes of selection:
	mesh_shapes = mesh.getShapes()
	if not mesh_shapes:
		return None
	
	mesh_materials = []	
	for mesh_shape in mesh_shapes:
		# ignore intermediate shape
		if pymel.hasAttr(mesh_shape, 'intermediateObject'):
			if mesh_shape.getAttr('intermediateObject'):
				continue

			# get shading groups from shapes:
			shading_grps = pymel.listConnections(mesh_shape,type='shadingEngine')
			if not shading_grps:
				continue
			shading_grps = list(set(shading_grps))
			
			# get the materials:			
			mats = pymel.ls(pymel.listConnections(shading_grps),materials=True)
			if not mats:
				continue
			
			mats = list(set(mats))
			for mat in mats:
				if not mat in mesh_materials:
					mesh_materials.append(mat)
					
			# return dict
			print mesh
			if info:
				material_dict = {}
				shading_dict = {}
				index = 0
				for index in range(0, len(shading_grps)):
					faces = pymel.sets(shading_grps[index], q=True)
					if faces:
						mat = pymel.ls(pymel.listConnections(shading_grps[index]), materials=True)
						if mat:
							if len(mat) == 1:
								mat = mat[0]
								shading_dict[mat] = faces
							else:
								shading_dict[mat] = faces
					index += 1							
				return shading_dict						
					

	return mesh_materials
	
	
def get_mesh_shape(mesh):
	"""
	Get the shape from a pyNode object

	*Arguments:*
		* ``mesh`` Pynode Mesh

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``Shape`` Or None

	*Author:*
	* randall.hess, randall.hess@gmail.com, 9/11/2014 12:12:07 PM
	"""		
	shapes = mesh.getShape()
	if shapes:
		return shapes
	else:
		return None
		
		
def transfer_shading_groups(source=None, targets=[]):
	"""
	Transfer shading group from the selected object to the target objects

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 5/18/2014 1:16:20 PM
	"""

	original_selection = pymel.ls(sl=True)
	if not source:
		selection = pymel.ls(sl=True)
		if len(selection) > 1:
			source = selection[0]
			targets = [selection[x] for x in range(1, len(selection))]

	if source and targets:
		materials = None
		shapes = pymel.ls(source, dag=True, s=True)
		if shapes:			
			shading_groups = pymel.listConnections(shapes, type='shadingEngine')
			if shading_groups:
				materials = pymel.ls(pymel.listConnections(shading_groups), materials=True)
	
		if materials:
			print 'Assigning materials: {0} \nto objects: {1}'.format( materials, targets )
			for group in shading_groups:
				for target in targets:
					pymel.sets(group, e=True, forceElement=target)

	pymel.select(original_selection)
	
	
def get_shader_connections(mesh, debug=False):
	"""
	Get the connected materials from a mesh

	*Arguments:*
		* ``mesh`` PyNode Mesh

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``Material`` List of Pynode Shaders assigned to the mesh

	*Author:*
	* randall.hess, randall.hess@gmail.com, 9/11/2014 12:12:26 PM
	"""	
	
	if not mesh:
		cmds.warning('No valid mesh given!')
		return
	
	shapes = mesh.getShapes()
	if not shapes:
		cmds.warning('{0} has no shape!'.format(mesh.nodeName()))
		return
	
	for mesh_shape in shapes:
		if pymel.hasAttr(mesh_shape, 'intermediateObject'):
			if mesh_shape.getAttr('intermediateObject'):
				continue
			shading_engines = []
			if pymel.hasAttr(mesh_shape, 'instObjGroups'):    
				group_attrs = pymel.listAttr(mesh_shape + '.instObjGroups')
				print 'Group Attrs: {0}'.format(group_attrs)
				for i in group_attrs:			
					attr = mesh_shape + '.' + i
					try:
						insta_attrs = pymel.listAttr(attr)
					except pymel.MayaAttributeError:
						pass						
					for insta in insta_attrs:
						try:
							conns = pymel.listConnections(mesh_shape + '.' + insta, type='shadingEngine')
						except pymel.MayaAttributeError:
							continue
						if debug:
							print conns
						print_attr = False
						if conns:
							conns = list(set(conns))
						for conn in conns:
							if not conn in shading_engines:
								shading_engines.append(conn)
							if debug:
								if not print_attr:
									print 'Attr: {0}'.format(insta)
									print_attr = True
								print ' {0}'.format(conn)

	materials = []
	if shading_engines:
		for shader in shading_engines:
			mats = pymel.ls(pymel.listConnections(shader),materials=True)
			if not mats:
				continue		
			else:
				if len(mats) == 1:
					mat = mats[0]
					materials.append(mat)				

	if debug:
		print 'Object: {0} Materials:'.format(mesh)
		for mat in materials:
			print ' {0}\n'.format(mat)
		
	return materials
	
	
def validate_mesh(mesh, mesh_type=None, uv_num=3):
	"""
	Make sure the mesh passes proper tests
	
	*Arguments:*
		* ``None`` 
	
	*Keyword Arguments:*
		* ``None`` 
	
	*Returns:*
		* ``None`` 
	
	*Author:*
	* randall.hess, randall.hess@gmail.com, 9/11/2014 6:33:01 PM
	"""

	#mesh_type == 'Weapon'
	#valid_material
	#valid_texture_paths
	#valid_mesh_transforms
	
	'''UVS'''
	error_msg = ''
	# determine if map1 has any uvs
	indices = cmds.polyUVSet(mesh.longName(), query=True, allUVSetsIndices=True)
	if indices:
		num_uvs = len(indices)
		if num_uvs > uv_num:
			error_msg += 'The mesh has more uv channels than is required.\n Max UVs:{0}\n Num UVs:{1}\n'.format(uv_num, num_uvs)
			
		for uv_index in indices:
			uv_name = cmds.getAttr(mesh.longName() + '.uvSet['+str(uv_index)+'].uvSetName')			
			uv_count = cmds.polyEvaluate(mesh.longName(), uv=True, uvs=uv_name)
			if uv_count == 0:			
				error_msg +='The uv channel {0} does not have any uvs. Name: {1}\n '.format(uv_index, uv_name)
				
	# make sure mesh isnt using 'lambert1' default material
	materials = get_mesh_materials(mesh)
	for mat in materials:
		if mat.nodeName() == 'lambert1':
			error_msg +='The mesh has the default material (lambert1), assigned.\nPlease assign a unique material to the mesh. Name: {0}\n '.format(mesh.nodeName())

	if error_msg:
		return False, error_msg
	
	
	return True, 'Mesh is valid'

