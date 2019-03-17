"""
Rigging Python Methods for use in Maya

Author: Randall Hess randall.hess@gmail.com
License: GNU General Public License v3.0
"""

import maya.mel as mel
import maya.cmds as cmds
import pymel.core as pymel


def get_obj_parent(obj, parent_before=None, parent_prefix=None):
	"""
	Recursive function to get objects parent

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 6/6/2016 11:10:56 AM
	"""	

	parent = pymel.listRelatives(obj, parent=True)
	if parent:
		parent = parent[0]
		if not parent_before == None:
			if parent == parent_before:
				return obj
		elif not parent_prefix == None:
			if parent.nodeName().startswith(parent_prefix):
				return parent
		parent = get_obj_parent(parent, parent_before=parent_before, parent_prefix=parent_prefix)
	else:
		parent = obj

	return parent


def skin_mesh(joints, mesh):
	"""
	Given joints and a mesh Smooth Bind the mesh

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 9/12/2014 5:22:10 PM
	"""

	if not joints:
		cmds.warning("A valid list of joints was not given to be skinned.")
		return False

	if not mesh:
		cmds.warning("A valid mesh was not given to be skinned.")
		return False

	pymel.select(mesh)
	pymel.lockNode(mesh, lock=False)

	# Delete history on the skinned mesh
	pymel.delete(mesh, constructionHistory=True)

	# freeze and reset transforms
	channels = ["tx","ty","tz","rx","ry","rz","sx","sz","sy"]
	for attr in channels:			
		cmds.setAttr(mesh.longName() + "." + attr, lock=False)

	try:
		mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")
		mel.eval("ResetTransformations;")	
	except:
		pass

	pymel.select(joints, add=True)
	for joint in joints:
		pymel.lockNode(joint, lock=False)

	# smooth bind	
	cluster_name = mesh.nodeName() + "_skinCluster"	
	new_skincluster = pymel.skinCluster(tsb=True, sm=0, bm=0, mi=4, name= cluster_name)

	return True


def disable_segment_compensate_scale(joints=[]):
	"""
	Turn off segment compensate scale on joints

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 8/18/2014 10:07:42 AM
	"""

	if not joints:	
		joints = pymel.ls(sl=True, type = "joint")

	for joint in joints:
		cmds.setAttr("{0}.segmentScaleCompensate".format(joint.longName()), 0)


def create_cluster_bone():
	"""
	Create a bone from either the object selection or the component selection

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 10/3/2014 5:20:22 PM
	"""

	obj = None
	obj_mode = False
	sel = pymel.ls(sl=True)
	if not sel:
		cmds.warning("You must select an object or component selection!")
		return

	component = cmds.selectMode(q=True,co=True)
	c = mel.eval("selectMode -q -co")
	print "Component Mode: {0}".format(component)
	print "C: {0}".format(c)
	cmds.refresh(f=True)

	mel.eval("PolySelectConvert 3")
	try:
		cluster = pymel.cluster(n="temp_cluster")[1]
	except:
		cmds.warning("You must select a deformable object!")
		return

	pymel.select(cl=True)
	new_joint = pymel.joint()
	cmds.refresh(f=True)
	new_joint.setAttr("radius", 4)
	constraint = pymel.parentConstraint(cluster, new_joint, mo = False)	
	cmds.refresh(f=True)
	pymel.delete(constraint)
	pymel.delete(cluster)

	pymel.select(sel)
	cmds.refresh(f=True)

	if component:
		pymel.hilite(u=True)
		sel = pymel.ls(sel)[0]
		pymel.select(new_joint, add=True)
		cmds.refresh(f=True)
		const = mel.eval("orientConstraint -offset 0 0 0 -weight 1;")[0]
		cmds.refresh(f=True)
		pymel.delete(const)

	cmds.refresh(f=True)

	pymel.select(new_joint)
	cmds.refresh(f=True)
	mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1;")
	pymel.selectMode(o=True)


def create_pivot_bone():
	"""
	Create a bone from the customPivot context

	In component mode of a mesh:
	Press "D" to go into custom pivot context
	  If you click on edges verts or faces the pivot will auto align
	  If you want to aim an axis click on the axis and ctrl+shift on another vert/edge/face to aim it
	  When you have the pivot you want run this to create the joint with that pivot

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 10/3/2014 5:17:19 PM
	"""

	# get these values	
	loc_xform = None
	loc_rp    = None

	# Get manipulator pos and orient	
	manip_pin = cmds.manipPivot(pinPivot=True)
	manip_pos = cmds.manipPivot(q=True, p=True)[0]
	manip_rot = cmds.manipPivot(q=True, o=True)[0]

	# delete existing temp objs
	temp_joint = None
	temp_loc   = None
	temp_cluster= None
	temp_joint_name = "temp_joint"
	temp_loc_name = "temp_loc"
	temp_cluster_name = "temp_cluster"
	temp_objs = [temp_joint_name, temp_loc_name]

	# get the selectMode
	sel_mode_obj       = cmds.selectMode(q=True, o=True)
	sel_mode_component = cmds.selectMode(q=True, co=True)		

	# store and clear selection
	selection = cmds.ls(sl=True)
	py_selection = pymel.ls(sl=True)
	if len(selection) == 0:
		cmds.warning("You must have a selection!")
		return	

	if len(selection) > 0:

		sel = selection[0]
		py_sel = py_selection[0]

		# create temp joint and set pos/rot
		cmds.select(cl=True)
		temp_joint= pymel.joint(n=temp_joint_name)
		temp_loc = pymel.spaceLocator(n=temp_loc_name)

		pivot_pos = mel.eval("manipPivot -q -p;")
		pivot_orient = mel.eval("manipPivot -q -o;")			

		if type(py_sel) == pymel.nodetypes.Transform:
			# snap loc to position			
			const = pymel.pointConstraint(sel, temp_loc, mo=False, w=1.0)
			pymel.delete(const)
			const = pymel.orientConstraint(sel, temp_loc, mo=False, w=1.0)
			pymel.delete(const)
		else:
			# get transform from parent object
			if type(py_sel.node()) == pymel.nodetypes.Mesh:
				parent = py_sel.node().getParent()
				if parent:
					const = pymel.pointConstraint(parent, temp_loc, mo=False, w=1.0)
					pymel.delete(const)
					const = pymel.orientConstraint(parent, temp_loc, mo=False, w=1.0)
					pymel.delete(const)

					# get the transforms
					loc_xform = pymel.xform(temp_loc, q=True, m=True, ws=True)
					loc_rp = pymel.xform(temp_loc, q=True, ws=True, rp=True)					

		# rotate the temp_loc if manip rot has been modified
		if not manip_rot == (0.0,0.0,0.0):				
			pymel.rotate(temp_loc, manip_rot)
		else:
			print "Rotation is Identity!"

		# move position to the cluster position
		if not manip_pos == (0.0,0.0,0.0):		
			pymel.xform(temp_loc, ws=True, t=manip_pos)

		# get the transforms
		loc_xform = pymel.xform(temp_loc, q=True, m=True, ws=True)
		loc_rp = pymel.xform(temp_loc, q=True, ws=True, rp=True)		

		# get the position from the component selection			
		if not type(py_sel) == pymel.nodetypes.Transform:
			cmds.select(selection, r=True)
			cmds.ConvertSelectionToVertices()
			try:
				cluster = cmds.cluster(n=temp_cluster_name)[1]
			except:
				cmds.warning("You must select a mesh object!")
				pymel.delete(temp_joint)
				pymel.delete(temp_loc)
				return

			# get the cluster position
			cmds.select(cl=True)		
			pos = cmds.xform(cluster, q=True, ws=True, rp=True)				

			# snap to the cluster
			const = pymel.pointConstraint(cluster, temp_loc, mo=False, w=1.0)
			pymel.delete(const)

			cmds.delete(cluster)

			# rotate the temp_loc if manip rot has been modified
			if not manip_rot == (0.0,0.0,0.0):				
				pymel.rotate(temp_loc, manip_rot)

			# move position to the cluster position
			if not manip_pos == (0.0,0.0,0.0):		
				pymel.xform(temp_loc, ws=True, t=manip_pos)				

			# get the transforms
			loc_xform = pymel.xform(temp_loc, q=True, m=True, ws=True)
			loc_rp = pymel.xform(temp_loc, q=True, ws=True, rp=True)	

		# remove temp loc
		pymel.delete(temp_loc)

	# modify the joint and stu
	if temp_joint:		
		if loc_xform and loc_rp:
			pymel.xform(temp_joint, m=loc_xform, ws=True)
			pymel.xform(temp_joint, piv=loc_rp, ws=True)			

		# freeze orient	
		pymel.select(temp_joint)	
		pymel.makeIdentity(apply=True, translate=True, rotate=True, scale=True, n=False)

	# unpin pivot
	cmds.manipPivot(pinPivot=False)


def get_skincluster_influences(mesh):
	"""
	Return the influences in the given mesh skinclusters
	*Arguments:*
		* ``mesh`` Geometry with skincluster

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``all_influences`` list of joints in the skincluster

	*Author:*
	* randall.hess, randall.hess@gmail.com, 1/15/2016 11:28:55 AM
	"""

	all_influences = []

	if mesh:	
		pymel.select(mesh, replace = True)		
		skincluster = mesh.listHistory(type="skinCluster")
		if skincluster:				
			# get the influence members
			influences = pymel.skinCluster(skincluster, q = True, inf = True)
			for infl in influences:
				if pymel.nodeType(infl) == "joint":
					if not infl in all_influences:
						all_influences.append(infl)

	return all_influences


def get_constraint_targets(constraint, ordered=False):
	"""
	Get the target nodes from a constraint

	*Arguments:*
		* ``constraint`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 10/27/2014 6:24:33 PM
	"""

	targets = []
	if constraint:
		conns = pymel.listConnections(constraint + ".target")
		if conns:
			conns = list(set(conns))
			for conn in conns:
				if not type(conn) == pymel.nodetypes.ParentConstraint and not type(conn) == pymel.nodetypes.ScaleConstraint:
					targets.append(conn)	
	return targets


def lock_channels(obj, lock=True):
	"""
	Lock channels

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* randall.hess, randall.hess@gmail.com, 11/6/2014 1:36:02 PM
	"""
	if not obj.isReadOnly():
		obj.setLocked(False)
		channels = ["translateX","translateY","translateZ","rotateX","rotateY","rotateZ","scaleX","scaleY","scaleZ"]
		for attr in channels:
			obj.setAttr(attr, lock = lock)	


def hide_channels(obj, hide=True):
	"""
	Hide channels

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* randall.hess, randall.hess@gmail.com, 11/6/2014 1:36:02 PM
	"""
	if not obj.isReadOnly():
		obj.setLocked(False)	
		channels = ["translateX","translateY","translateZ","rotateX","rotateY","rotateZ","scaleX","scaleY","scaleZ"]
		for attr in channels:
			if hide:
				obj.setAttr(attr, keyable=False, cb=False)
			else:
				obj.setAttr(attr, keyable=True, cb=True)


def transfer_pivot(source=None, target=None, freeze=True):
	"""
	Transfer the pivot from one object to another

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 10/27/2014 5:50:04 PM
	"""

	if not source:
		sel = pymel.ls(sl=True)
		if not len(sel) == 2:
			cmds.warning("You must select two objects to transfer pivot. Source object then Target object.")
			return False

		source = sel[0]
		target = sel[1]

	# unlock channels
	pymel.lockNode(target, lock=False)
	lock_channels(target, lock=False)

	# constrain to source
	const = pymel.parentConstraint(source, target, mo=False)
	pymel.delete(const)	

	if freeze:
		mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1;")

	return True

def rename_mesh_shapes(meshes=[], renamed_nodes=[]):
	"""
	Rename the shape objects forthe mesh

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* randall.hess, randall.hess@gmail.com, 7/29/2016 1:35:18 PM
	"""

	if not meshes:
		meshes = pymel.ls(sl = True, type = "transform")

	invalid_renames = ["initialShadingGroup"]

	if meshes:
		for mesh in meshes:
			if pymel.objExists(mesh):

				# get the shape relatives
				mesh_shapes = pymel.listRelatives(mesh, s = True)
				for shape in mesh_shapes:
					mesh_name = mesh.nodeName()
					new_obj_name = mesh.nodeName() + "Shape"
					if "|" in mesh.longName():
						new_name = mesh.longName().split("|")[-1] + "Shape"
						if shape.isLocked():
							continue
						try:
							shape.rename( new_name )
							if not new_name in renamed_nodes:
								renamed_nodes.append(new_name)
						except:
							print "Cannot rename read-only node: {0}".format(mesh.nodeName())

					else:
						new_name = rename_node(shape.nodeName(), new_obj_name)
						if not new_name in renamed_nodes:
							renamed_nodes.append(new_name)


def rename_mesh_deformers(meshes=[], renamed_nodes=[], quiet=True):
	"""
	Rename the deformers on the mesh, blendshapes and skinclusters

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* randall.hess, randall.hess@gmail.com, 7/29/2016 1:35:18 PM
	"""

	if not meshes:
		meshes = pymel.ls( sl = True )

	invalid_renames = ["initialShadingGroup"]

	if meshes:
		for mesh in meshes:
			if pymel.objExists(mesh):

				# get the history
				hist_objs = pymel.listHistory(mesh)
				valid_hist_objs = ["blendShape","groupParts","groupId","tweak","skinCluster"]
				for obj in hist_objs:

					if str( obj.nodeType() ) in valid_hist_objs:
						new_obj_name = mesh.nodeName() + "_" + obj.nodeType()
						if new_obj_name in renamed_nodes:
							if not quiet:
								cmds.warning("This object has already been renamed!\n Old_Object: {0}\n New_Object: {1}".format( obj.nodeName(), new_obj_name))

						if not obj.nodeName() in invalid_renames:
							new_name = rename_node(obj.nodeName(), new_obj_name)
							if not new_name in renamed_nodes:
								renamed_nodes.append(new_name)

				# get the shape relatives
				mesh_shapes = pymel.listRelatives(mesh, s = True)
				for shape in mesh_shapes:
					conns = shape.listConnections()
					if conns:
						conns = list(set(conns))
					for conn in conns:

						# dont rename a shadingEngine
						if isinstance(conn, pymel.nodetypes.ShadingEngine):
							if conn.nodeName().endswith(str(conn.nodeType())):
								continue

						new_obj_name = mesh.nodeName() + "_" + conn.nodeType()
						if new_obj_name in renamed_nodes:
							if not quiet:
								cmds.warning("This object has already been renamed!\n Old_Object: {0}\n New_Object: {1}".format( conn.nodeName(), new_obj_name ))

						if not conn.nodeName() in invalid_renames:
							new_name = rename_node(conn.nodeName(), new_obj_name)
							if not new_name in renamed_nodes:
								renamed_nodes.append(new_name)

	return renamed_nodes


def create_weapon_control(ctrl=None, bone=None, constraint_obj=None, create_space_grps=True, separate_xforms=False):
	"""
	Build a weapon ctrl based off of selection

	*Arguments:*
		* ``None```

	*Keyword Arguments:*
		* ``constraint_obj`` object to constrain to
		* ``create_space_grps`` create grp hier to facilitate space switching
		* ``separate_xforms`` create separate transform object for rotation and translation

	*Returns:*
		* ``Value`` If any, enter a description for the return value here.

	*Examples:* ::

	Enter code examples here. (optional field)

	*Todo:*
		* Enter thing to do. (optional field)

	*Author:*
	* randall.hess, randall.hess@gmail.com, 5/12/2015 1:45:55 PM
	"""

	if ctrl is None or bone is None:
		sel = pymel.ls(sl=True)
		if len(sel) >= 2:
			ctrl = sel[0]
			bone = sel[1]

		# get the anim object to constrain to
		if len(sel) == 3:
			constraint_obj = sel[2]

	if not ctrl is None and not bone is None:
		print "Ctrl:  {0}".format(ctrl)
		print "Bone: {0}".format(bone)

		# space switching objects
		snap_grp_name = bone.nodeName() + "_anim_SN"
		parent_handle_name = bone.nodeName() + "_anim_PH"

		# name of the anim ctrl
		ctrl_name = bone.nodeName() + "_anim"

		# rename the ctrl relative to the bone name
		if not ctrl.nodeName().lower() == ctrl_name.lower():
			pymel.rename(ctrl, bone.nodeName() + "_anim")		

		# remove existing grp
		grp_name = bone.nodeName() + "_grp"

		# check the heirarchy before building space_grps
		if create_space_grps:	

			# remove existing hierarchy groups
			if pymel.objExists(grp_name):
				if not pymel.objExists(parent_handle_name):
					create_space_grps = False			
				pymel.delete(grp_name)

		if pymel.objExists(snap_grp_name):
			pymel.delete(snap_grp_name)

		if pymel.objExists(parent_handle_name):
			pymel.delete(parent_handle_name)

		# make a group with a name relative to the bone name
		ctrl_grp = bone.nodeName() + "_grp"
		if pymel.objExists(ctrl_grp):	
			pymel.delete(ctrl_grp)

		# create top level parent grp
		parent_grp = pymel.group(empty=True, name=(bone.nodeName() + "_grp"))
		piv = cmds.xform(ctrl.nodeName(), q=True, rp=True, ws=True)
		xform = cmds.xform(ctrl.nodeName(), q=True, m=True, ws=True)
		cmds.xform(parent_grp.nodeName(), piv=piv, ws=True)

		# parent the grp under the rig_grp
		pymel.parent(parent_grp, "rig_grp")		

		# move the group
		temp_p_constraint = pymel.parentConstraint(ctrl, parent_grp, mo=False, weight=1.0)
		pymel.delete(temp_p_constraint)

		# create separate controls for separate transforms
		translate_anim = None
		translate_grp = None
		rotate_grp = None
		if separate_xforms:

			# create offset ctrl
			scale_val = 3.0
			translate_anim_name = bone.nodeName() + "_translate_anim"
			mel.eval('curve -d 1 -p -{0} {0} {0} -p {0} {0} {0} -p {0} {0} -{0} -p -{0} {0} -{0} -p -{0} {0} {0} -p -{0} -{0} {0} -p -{0} -{0} -{0} -p {0} -{0} -{0} -p {0} -{0} {0} -p -{0} -{0} {0} -p {0} -{0} {0} -p {0} {0} {0} -p {0} {0} -{0} -p {0} -{0} -{0} -p -{0} -{0} -{0} -p -{0} {0} -{0} -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -n "{1}";'.format(scale_val, translate_anim_name))
			translate_anim = pymel.general.PyNode(translate_anim_name)
			translate_anim.getShape().overrideEnabled.set(True)
			translate_anim.getShape().overrideColor.set(22)
			cmds.xform(translate_anim.nodeName(), m=xform, ws=True)
			cmds.xform(translate_anim.nodeName(), piv=piv, ws=True)
			cmds.select(translate_anim_name)
			cmds.select(cl = True)

			# parent the anim ctrl under the translate ctrl
			translate_grp = cmds.group(empty=True, name=(bone.nodeName() + "_translate_grp"))
			cmds.xform(translate_grp, piv=piv, ws=True)
			pymel.parent(translate_anim, translate_grp)
			rotate_grp = cmds.group(empty=True, name=(bone.nodeName() + "_rotate_grp"))
			cmds.xform(rotate_grp, piv=piv, ws=True)
			pymel.parent(translate_grp, parent_grp)
			cmds.select(translate_grp)
			mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")
			pymel.parent(rotate_grp, translate_anim)
			cmds.select(rotate_grp)
			mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")			
			pymel.parent(ctrl, rotate_grp)	
			cmds.select(ctrl.nodeName())
			mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")
			cmds.select(cl= True)

		# create hierarchy for space switching
		if create_space_grps:			
			snap_grp = pymel.group(empty=True, n=snap_grp_name)
			pymel.xform(snap_grp, piv=piv, ws=True)

			parent_handle = pymel.group(snap_grp, n=parent_handle_name)
			pymel.xform(parent_handle, piv=piv, ws=True)
			pymel.select(snap_grp)
			mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")			

			# query attributes to lock
			ts = set(["tx", "ty", "tz"])
			rs = set(["rx", "ry", "rz"])

			availAttrs = [] 
			attrsToLock = (ts | rs)

			# parent objects
			pymel.parent(parent_handle, parent_grp)
			pymel.select(parent_handle)
			mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")
			pymel.parent(snap_grp, parent_handle)
			pymel.select(snap_grp)
			mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")

			if separate_xforms:				
				pymel.parent(translate_grp, snap_grp)
			else:
				pymel.parent(ctrl, snap_grp)
				pymel.select(ctrl)
				try:
					mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")
				except:
					pass

		# parent the ctrl under the grp
		if not separate_xforms and not create_space_grps:
			pymel.parent(ctrl, parent_grp)

		# freeze the ctrl
		pymel.select(ctrl, r =True)
		if not separate_xforms and not create_space_grps:
			mel.eval("makeIdentity -apply true -t 1 -r 1 -s 1 -n 0 -pn 1")
			cmds.xform(ctrl.nodeName(), piv=piv, ws=True)

		# lock attributes after freezing transforms
		if separate_xforms:
			# lockAttrs
			channels = [".tx",".ty",".tz",".rx",".ry",".rz",".sx",".sy",".sz"]
			obj_locks = {}
			obj_locks[translate_anim] = []
			obj_locks[ctrl_name] = [".sx",".sy",".sz"]
			for obj_name, channels in obj_locks.iteritems():
				pymel.setAttr(obj_name + ".v", lock=False, keyable=False, cb=True)
				for attr in channels:			
					pymel.setAttr(obj_name + attr, lock=True, cb=True)

		# constrain the grp to the weapon_grip_anim
		attrs = [".tx",".ty",".tz",".rx",".ry",".rz",".sx",".sy",".sz"]
		for attr in attrs:
			pymel.setAttr("{0}{1}".format(bone, attr), lock=False)

		# object to constrain to
		if not bone.nodeName() == "weapon_grip" and not bone.nodeName() == "weapon_root":
			weapon_grip = "weapon_grip_anim"
			if cmds.objExists(weapon_grip):				
				if not constraint_obj:
					constraint_obj = weapon_grip
			elif cmds.objExists("frame_anim"):
				if not constraint_obj:
					constraint_obj = "frame_anim"					

		# constrain the control to a specific object/group
		if constraint_obj:
			p_constraint = pymel.parentConstraint(constraint_obj, parent_grp, mo=True, weight=1.0)			
			s_constraint = pymel.scaleConstraint(constraint_obj, parent_grp, mo=False, weight=1.0)

		# connect scale channel from anim controller to bone
		# this works properly in engine when not using SegmentScaleCompensate
		pymel.lockNode(bone, lock=False)
		scale_channels = [".sx",".sy",".sz"]
		for chan in scale_channels:
			try:
				pymel.connectAttr(ctrl.longName() + chan, bone.longName() + chan)			
			except:
				print "Failed connecting scale attribute from ctrl: {0} to the bone: {1}".format(ctrl.nodeName(), bone.nodeName())

		# constrain the bone to the anim ctrl
		p_constraint = pymel.parentConstraint(ctrl, bone, mo=False, weight=1.0)

		return ctrl

	else:
		print "Need to select a bone then a ctrl object"

	return None


def create_animatable_pivot( base_name = "weapon_root", parent_grp = "rig_grp", parent_obj = "weapon_root_grp", main_ctrl = "weapon_root_anim" ):
	"""
	Create an animatable pivot

	*Arguments:*
		* ``Argument`` Enter a description for the argument here.

	*Keyword Arguments:*
		* ``base_name`` base object we are driving
		* ``parent_grp`` grp we parent the top level object to
		* ``parent_obj`` top level group of the object we are driving
		* ``main_ctrl`` main object we are driving

	*Author:*
	* randall.hess, randall.hess@gmail.com, 5/26/2015 11:24:44 AM
	"""	
	
	plugin_name = "matrixNodes.mll"
	try:
		pymel.loadPlugin( plugin_name, quiet = True )
		pymel.pluginInfo( plugin_name, edit = True, autoload = True )
	except:
		cmds.warning("Could not load matrixNodes.mll plugin")
		return False		

	# Pivot object names
	pivot_grp_name = base_name + "_pivot_grp"
	offset_anim_name = base_name + "_pivot_offset_anim"
	pivot_anim_name = base_name + "_pivot_anim"
	locator_name = base_name + "_parent_locator"
	decomp_name = base_name + "_decompose"

	# Remove existing Objects
	obj_names = [ pivot_grp_name, offset_anim_name, pivot_anim_name, locator_name, decomp_name ]
	for name in obj_names:
		if pymel.objExists( name ):
			pymel.lockNode(name, lock=False)
			pymel.delete( name )

	## Create objects	
	# create pivot grp
	pivot_grp = pymel.group( name = pivot_grp_name )
	lock_channels(pivot_grp)
	hide_channels(pivot_grp)
	pivot_grp.setAttr("v", keyable=False)

	constrain_grp = pymel.group( name = "{0}_constrain".format(base_name) )
	constrain_parent_grp = pymel.group( name = "{0}_constrain_grp".format(base_name) )
	parent_constrain_grp = pymel.group( name = "{0}_constrain_PH".format(base_name) )
	snap_constrain_grp = pymel.group( name = "{0}_constrain_SN".format(base_name) )
	lock_channels(constrain_parent_grp)
	hide_channels(constrain_parent_grp)
	constrain_parent_grp.setAttr("v", keyable=False)
	pymel.parent( constrain_parent_grp, parent_grp)
	pymel.parent( parent_constrain_grp, constrain_parent_grp)
	pymel.parent( snap_constrain_grp, parent_constrain_grp)
	pymel.parent( constrain_grp, snap_constrain_grp)
	world_locator = pymel.general.spaceLocator( n = "{0}_world_spaceLoc".format(base_name) )
	lock_channels(world_locator)
	hide_channels(world_locator)
	world_locator.setAttr("v", keyable=False)
	pymel.setAttr(world_locator + ".v", 0)
	pymel.parent( world_locator, parent_grp)

	# assign attribute to weapon constrain
	pymel.addAttr( constrain_grp, ln= "rh_constraint_object", niceName = "Constraint Object", at = "double", defaultValue = 1.0, minValue = 1.0, maxValue = 1.0, keyable = True, h = False )

	# create offset ctrl
	scale_val = 5.0
	mel.eval('curve -d 1 -p -{0} {0} {0} -p {0} {0} {0} -p {0} {0} -{0} -p -{0} {0} -{0} -p -{0} {0} {0} -p -{0} -{0} {0} -p -{0} -{0} -{0} -p {0} -{0} -{0} -p {0} -{0} {0} -p -{0} -{0} {0} -p {0} -{0} {0} -p {0} {0} {0} -p {0} {0} -{0} -p {0} -{0} -{0} -p -{0} -{0} -{0} -p -{0} {0} -{0} -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -n "{1}";'.format(scale_val, offset_anim_name))		
	offset_anim = pymel.general.PyNode(offset_anim_name)
	offset_anim.getShape( ).overrideEnabled.set( True )
	offset_anim.getShape( ).overrideColor.set( 14 )	

	# create anim ctrl
	mel.eval('curve -d 1 -p 0 3 0 -p 0 2 -2 -p 0 0 -3 -p 0 -2 -2 -p 0 -3 0 -p 0 -2 2 -p 0 0 3 -p 0 2 2 -p 0 3 0 -p 2 2 0 -p 3 0 0 -p 2 -2 0 -p 0 -3 0 -p -2 -2 0 -p -3 0 0 -p -2 2 0 -p 0 3 0 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -k 16 -n "{0}";'.format(pivot_anim_name))				
	mel.eval("select -r {0}.cv[0:16] ;".format(pivot_anim_name))
	mel.eval("scale -r -ocp 2.0 2.0 2.0;")
	pivot_anim = pymel.PyNode( pivot_anim_name )	
	pivot_anim.getShape( ).overrideEnabled.set( True )
	pivot_anim.getShape( ).overrideColor.set( 13 )		

	# create parent locator
	parent_locator = pymel.general.spaceLocator( n = locator_name )
	pymel.setAttr( parent_locator + ".v", 0 )

	# create decomposeMatrix	
	pymel.nodetypes.DecomposeMatrix( n = decomp_name )
	decomp_node = pymel.general.PyNode( decomp_name )

	# parent the objects
	pymel.parent( offset_anim, pivot_grp )
	pymel.parent( pivot_anim, offset_anim )
	pymel.parent( parent_locator, pivot_grp)
	pymel.parent( pivot_grp, constrain_grp )

	pymel.select(cl=True)
	pymel.select(constrain_grp)
	pymel.select(world_locator, add=True)	

	# constrain obj to parent locator
	anim_constraint = pymel.parentConstraint( pivot_anim, parent_locator, mo = True, weight = 1.0 )
	obj_constraint = pymel.parentConstraint( parent_locator, parent_obj, mo = True, weight = 1.0 )

	# connectAttrs
	pymel.connectAttr( offset_anim.nodeName() + ".inverseMatrix", decomp_name + ".inputMatrix" )
	pymel.connectAttr( decomp_name + ".outputTranslate", obj_constraint + ".target[0].targetOffsetTranslate" )
	pymel.connectAttr( decomp_name + ".outputRotate", obj_constraint + ".target[0].targetOffsetRotate" )

	# lockAttrs
	channels = [".tx",".ty",".tz",".rx",".ry",".rz",".sx",".sy",".sz"]
	obj_locks = {}
	obj_locks[ offset_anim_name ] = [".sx",".sy",".sz"]
	obj_locks[ pivot_anim_name ] = [".sx",".sy",".sz"]	
	for obj_name, channels in obj_locks.iteritems():
		pymel.setAttr( obj_name + ".v", lock = False, keyable = False, cb = True )
		for attr in channels:			
			pymel.setAttr( obj_name + attr, lock = True, keyable = False, cb = True )

	# drive visibility from main control
	pymel.refresh()
	pymel.select( main_ctrl, replace = True )
	if (cmds.attributeQuery( "anim_pivot_vis", n=main_ctrl, ex=True)):
		pass	
	else:
		pymel.addAttr( main_ctrl, ln= "anim_pivot_vis", niceName = "Anim Pivot Vis", at = "double", defaultValue = 0.0, minValue = 0.0, maxValue = 1.0, keyable = True, h = False )

	pymel.setAttr( main_ctrl + ".anim_pivot_vis", keyable = False, cb = True )
	pymel.connectAttr( main_ctrl + ".anim_pivot_vis", offset_anim_name + ".visibility" )

	return True


def create_temp_curve(obj_name, square=False, cube=False, sphere=True):
	"""
	Create a temp curve object

	*Arguments:*
		* ``Argument`` Enter a description for the argument here.

	*Keyword Arguments:*
		* ``square`` square curve
		* ``cube`` cube curve
		* ``sphere`` sphere curve

	*Author:*
	* randall.hess, randall.hess@gmail.com, 5/26/2015 11:24:44 AM
	"""	
	
	obj_ctrl = obj_name + '_curve'
	if square == True:
		mel.eval('curve -d 1 -p -1 0 1 -p 1 0 1 -p 1 0 -1 -p -1 0 -1 -p -1 0 1 -k 0 -k 1 -k 2 -k 3 -k 4 -n "{0}";'.format(obj_ctrl))
	elif cube == True:
		scale_val = 6.0
		mel.eval( 'curve -d 1 -p -{0} {0} {0} -p {0} {0} {0} -p {0} {0} -{0} -p -{0} {0} -{0} -p -{0} {0} {0} -p -{0} -{0} {0} -p -{0} -{0} -{0} -p {0} -{0} -{0} -p {0} -{0} {0} -p -{0} -{0} {0} -p {0} -{0} {0} -p {0} {0} {0} -p {0} {0} -{0} -p {0} -{0} -{0} -p -{0} -{0} -{0} -p -{0} {0} -{0} -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -n "{1}";'.format( scale_val, obj_ctrl ) )
	elif sphere == True:
		mel.eval( 'curve -d 1 -p 0 3 0 -p 0 2 -2 -p 0 0 -3 -p 0 -2 -2 -p 0 -3 0 -p 0 -2 2 -p 0 0 3 -p 0 2 2 -p 0 3 0 -p 2 2 0 -p 3 0 0 -p 2 -2 0 -p 0 -3 0 -p -2 -2 0 -p -3 0 0 -p -2 2 0 -p 0 3 0 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -k 16 -n "{0}";'.format( obj_ctrl ) )		
		mel.eval( 'select -r {0}.cv[0:16] ;'.format(obj_ctrl) )
		mel.eval( 'scale -r -ocp 2.25 2.25 2.25;' )		
	else:
		mel.eval( 'curve -d 1 -p 0 3 0 -p 0 2 -2 -p 0 0 -3 -p 0 -2 -2 -p 0 -3 0 -p 0 -2 2 -p 0 0 3 -p 0 2 2 -p 0 3 0 -p 2 2 0 -p 3 0 0 -p 2 -2 0 -p 0 -3 0 -p -2 -2 0 -p -3 0 0 -p -2 2 0 -p 0 3 0 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -k 16 -n "{0}";'.format( obj_ctrl ) )	
	return obj_ctrl


def weapon_create_rig(weapon_name="WeaponName"):
	"""
	Create the base structure for a weapon rig

	*Arguments:*
		* ``None`` 

	*Keyword Arguments:*
		* ``None`` 

	*Returns:*
		* ``None`` 

	*Author:*
	* randall.hess, randall.hess@gmail.com, 9/11/2014 1:21:47 PM
	"""

	if pymel.objExists("Weapon"):
		try:
			pymel.lockNode("Weapon", lock=False)
			pymel.delete("Weapon")
		except:
			cmds.warning("There is currently a Weapon node in the scene that cannot be delete!\n\nThis needs to be removed to continue")
			return False

	# create Weapon	
	weapon_grp = pymel.group(empty=True, name ="Weapon")
	lock_channels(weapon_grp)
	hide_channels(weapon_grp)
	weapon_grp.setAttr("v", keyable=False)

	pymel.addAttr(weapon_grp, ln="rh_item_name", niceName="ItemName", dt="string", keyable=False)	
	pymel.addAttr(weapon_grp, ln="rh_item_data", niceName="ItemData", at="bool", keyable=False, dv=1)	
	pymel.addAttr(weapon_grp, ln="rh_weapon", niceName="Weapon", at="bool", keyable=False, dv=1)
	pymel.addAttr(weapon_grp, ln="rh_item_data_version", niceName = "ItemDataVersion", at = "double", defaultValue=1.0, minValue=1.0, maxValue = 100.0, keyable = False, h = False )
	pymel.addAttr(weapon_grp, ln="rh_item_version", niceName = "ItemVersion", at = "double", defaultValue = 1.0, minValue = 1.0, maxValue = 100.0, keyable = False, h = False )
	pymel.addAttr(weapon_grp, ln="rh_material_index", niceName = "MaterialIndex", at = "double", defaultValue = 0.0, minValue = 0.0, maxValue = 20.0, keyable = False, h = False )
	pymel.addAttr(weapon_grp, ln="rh_bone_index", niceName = "BoneIndex", at = "double", defaultValue = 0.0, minValue = 0.0, maxValue = 60.0, keyable = False, h = False )	
	pymel.addAttr(weapon_grp, at="message", ln= "rh_mesh_base", niceName="BaseMesh")
	pymel.addAttr(weapon_grp, at="message", ln= "rh_mesh_grp", niceName="MeshGrp")
	pymel.addAttr(weapon_grp, at="message", ln= "rh_rig_grp", niceName="RigGrp")
	pymel.addAttr(weapon_grp, at="message", ln= "rh_item_root", niceName="ItemRoot")
	pymel.addAttr(weapon_grp, at="message", ln= "rh_item_constraint_object", niceName="ItemConstraint")	
	pymel.addAttr(weapon_grp, ln="rh_item_edit", niceName="ItemEditMode", at="bool", keyable=False, dv=0)	

	# create rig_grp
	rig_grp = pymel.group(empty=True, name ="rig_grp")
	pymel.parent(rig_grp, weapon_grp)
	lock_channels(rig_grp)
	hide_channels(rig_grp)
	rig_grp.setAttr("v", keyable=False)

	# create weapon_root, weapon_grip	
	weapon_bones = {"weapon_root":None, "weapon_grip":"weapon_root"}
	weapon_root = pymel.joint(name="weapon_root")	
	weapon_grip = pymel.joint(name="weapon_grip")
	weapon_secondary_grip = pymel.joint(name="weapon_secondary_grip")
	disable_segment_compensate_scale([weapon_root,weapon_grip,weapon_secondary_grip])
	pymel.parent(weapon_grip, weapon_root)
	pymel.parent(weapon_secondary_grip, weapon_grip)
	pymel.parent(weapon_root, weapon_grp)
	pymel.select(weapon_root)
	if pymel.objExists("Bones"):
		pymel.lockNode("Bones", lock=False)
		pymel.delete("Bones")		
	bone_layer = pymel.createDisplayLayer(name="Bones")
	pymel.lockNode(bone_layer, lock=True)

	pymel.addAttr("weapon_root", at="message", ln= "rh_mesh", niceName="Mesh")
	pymel.addAttr("weapon_root", at="message", ln= "rh_owner", niceName="Owner")
	pymel.addAttr("weapon_root", at="message", ln= "character", niceName="character")	
	pymel.addAttr("weapon_root", ln="export", dt="string", keyable=False)
	pymel.addAttr("weapon_root", ln="slot", dt="string", keyable=False)
	pymel.addAttr("weapon_root", ln="rh_item_bone", niceName="ItemBone", at="bool", keyable=False, dv=1)	
	pymel.addAttr("weapon_root", ln="rh_item", niceName="Item", at="bool", keyable=False, dv=1)
	pymel.addAttr("weapon_root", ln="rh_weapon", niceName="Weapon", at="bool", keyable=False, dv=1)
	pymel.addAttr("weapon_grip", ln="rh_item", niceName="Item", at="bool", keyable=False, dv=1)
	pymel.addAttr("weapon_grip", ln="rh_item_bone", niceName="WeaponBone", at="bool", keyable=False, dv=1)
	pymel.addAttr("weapon_secondary_grip", ln="rh_item", niceName="Item", at="bool", keyable=False, dv=1)
	pymel.addAttr("weapon_secondary_grip", ln="rh_item_bone", niceName="ItemBone", at="bool", keyable=False, dv=1)

	# unassigned grp
	unassigned_grp = pymel.group(empty=True, name ="_UNASSIGNED_")
	lock_channels(unassigned_grp)
	hide_channels(unassigned_grp)
	unassigned_grp.setAttr("v", keyable=False)
	pymel.lockNode(unassigned_grp, lock=True)

	# create mesh grp
	mesh_grp = pymel.group(empty=True, name = "MESH_" + weapon_name)
	pymel.parent(mesh_grp, weapon_grp)
	lock_channels(mesh_grp)
	hide_channels(mesh_grp)
	mesh_grp.setAttr("v", keyable=False)

	pymel.select(mesh_grp)
	if pymel.objExists("Mesh"):
		pymel.lockNode("Mesh", lock=False)
		pymel.delete("Mesh")	
	mesh_layer = pymel.createDisplayLayer( name = "Mesh" )	
	pymel.lockNode(mesh_layer, lock=True)
	pymel.select(cl=True)	

	# First material group
	mat_group = pymel.group(empty=True, name ="Mat_00")
	lock_channels(mat_group)
	hide_channels(mat_group)
	mat_group.setAttr("v", keyable=False)

	pymel.addAttr(mat_group, at="message", ln= "rh_material", multi=True, niceName="Material", keyable=False, h=False)		
	pymel.addAttr( mat_group, ln= "rh_item_material_index", niceName = "Material Index", at = "double", defaultValue = 0.0, minValue = 0.0, maxValue = 20.0, keyable = False, h = False )	
	mat_group.setAttr("rh_material", lock=True)
	mat_group.setAttr("rh_item_material_index", lock=True)
	pymel.parent(mat_group, mesh_grp)	

	# connect to weapon grps
	cmds.connectAttr( rig_grp.nodeName() + ".message", "Weapon.rh_rig_grp", f=True )
	cmds.connectAttr( mesh_grp.nodeName() + ".message", "Weapon.rh_mesh_grp", f=True )
	cmds.connectAttr( weapon_root.nodeName() + ".message", "Weapon.rh_item_root", f=True )

	# rig base bones
	obj_ctrl = create_temp_curve("weapon_root", square=True)	
	obj_ctrl = pymel.PyNode(obj_ctrl)		
	root_ctrl = create_weapon_control(ctrl=obj_ctrl, bone=weapon_root, constraint_obj=None, 
	                                  create_space_grps=True, 
	                                  separate_xforms=False)

	pymel.select(root_ctrl, r=True)
	rename_mesh_shapes()
	root_ctrl.getShape().overrideEnabled.set(True)
	root_ctrl.getShape().overrideColor.set(14)	

	# Shape the Root Anim Curve
	cmds.setAttr("weapon_root_animShape.controlPoints[0].xValue", 0)
	cmds.setAttr("weapon_root_animShape.controlPoints[0].yValue", -30)
	cmds.setAttr("weapon_root_animShape.controlPoints[0].zValue", -10)	
	cmds.setAttr("weapon_root_animShape.controlPoints[1].xValue", 0)
	cmds.setAttr("weapon_root_animShape.controlPoints[1].yValue", 30)
	cmds.setAttr("weapon_root_animShape.controlPoints[1].zValue", -10)
	cmds.setAttr("weapon_root_animShape.controlPoints[2].xValue", 0)
	cmds.setAttr("weapon_root_animShape.controlPoints[2].yValue", 30)
	cmds.setAttr("weapon_root_animShape.controlPoints[2].zValue", 10)
	cmds.setAttr("weapon_root_animShape.controlPoints[3].xValue", 0)
	cmds.setAttr("weapon_root_animShape.controlPoints[3].yValue", -30)
	cmds.setAttr("weapon_root_animShape.controlPoints[3].zValue", 10)
	cmds.setAttr("weapon_root_animShape.controlPoints[4].xValue", 0)
	cmds.setAttr("weapon_root_animShape.controlPoints[4].yValue", -30)
	cmds.setAttr("weapon_root_animShape.controlPoints[4].zValue", -10)	

	# Add Global Scale Attr
	pymel.refresh()
	pymel.select( root_ctrl, replace = True )	
	pymel.addAttr( root_ctrl, ln= "global_scale", niceName = "Global Scale", at = "double", defaultValue = 1.0, minValue = 0.0, maxValue = 10.0, keyable = True, h = False )
	pymel.setAttr( root_ctrl + ".global_scale", keyable = True, cb = True )
	pymel.connectAttr( root_ctrl + ".global_scale", root_ctrl + ".sx")	
	pymel.connectAttr( root_ctrl + ".global_scale", root_ctrl + ".sy")
	pymel.connectAttr( root_ctrl + ".global_scale", root_ctrl + ".sz")	
	pymel.setAttr( root_ctrl + ".global_scale", keyable=True)

	# Create the Grip Anim Ctrl
	obj_ctrl = create_temp_curve("weapon_grip", cube=True)	
	obj_ctrl = pymel.PyNode(obj_ctrl)
	grip_ctrl = create_weapon_control(ctrl=obj_ctrl, bone=weapon_grip, constraint_obj=root_ctrl, 
	                                  create_space_grps=True, 
	                                  separate_xforms=False)
	pymel.select(grip_ctrl, r=True)
	rename_mesh_shapes()	
	grip_ctrl.getShape( ).overrideEnabled.set( True )
	grip_ctrl.getShape( ).overrideColor.set( 22 )

	# Create the Secondary Grip Anim Ctrl
	obj_ctrl = create_temp_curve("weapon_secondary_grip", sphere=True)	
	obj_ctrl = pymel.PyNode(obj_ctrl)
	sec_grip_ctrl = create_weapon_control(ctrl=obj_ctrl, bone=weapon_secondary_grip, constraint_obj=grip_ctrl, 
	                                      create_space_grps=True, 
	                                      separate_xforms=False)
	pymel.select(sec_grip_ctrl, r=True)
	rename_mesh_shapes()	
	sec_grip_ctrl.getShape( ).overrideEnabled.set( True )
	sec_grip_ctrl.getShape( ).overrideColor.set( 18 )
	pymel.addAttr(sec_grip_ctrl, ln="rh_item_control", niceName="ItemControl", at="bool", keyable=False, dv=1)	
	pymel.addAttr(sec_grip_ctrl, ln="rh_item", niceName="Item", at="bool", keyable=False, dv=1)	

	pymel.select(cl=True)


	# animatable pivot
	create_animatable_pivot(base_name="weapon_root", parent_grp="rig_grp", 
	                        parent_obj="weapon_root_grp", 
	                        main_ctrl="weapon_root_anim")

	# add weapon attrs to the anim ctrls
	pymel.addAttr(root_ctrl, ln="rh_item_control", niceName="ItemControl", at="bool", keyable=False, dv=1)
	pymel.addAttr(root_ctrl, ln="rh_item", at="bool", niceName="Item", keyable=False, dv=1)

	pymel.addAttr("weapon_grip_anim", ln="rh_item", at="bool", niceName="Item", keyable=False, dv=1)
	pymel.addAttr("weapon_grip_anim", ln="rh_item_control", niceName="ItemControl", at="bool", keyable=False, dv=1)	

	pymel.addAttr("weapon_root_pivot_offset_anim", ln="rh_item", niceName="Item", at="bool", keyable=False, dv=1)
	pymel.addAttr("weapon_root_pivot_offset_anim", ln="rh_item_control", niceName="ItemControl", at="bool", keyable=False, dv=1)	
	pymel.addAttr("weapon_root_pivot_anim", ln="rh_item", niceName="Weapon", at="bool", keyable=False, dv=1)
	pymel.addAttr("weapon_root_pivot_anim", ln="rh_item_control", niceName="ItemControl", at="bool", keyable=False, dv=1)	

	# assign attribute to weapon constrain
	weapon_constrain = pymel.PyNode("weapon_root_constrain")
	pymel.connectAttr(weapon_constrain.nodeName() + ".message", "Weapon.rh_item_constraint_object", f=True )
	pymel.setAttr(weapon_constrain.nodeName() + ".rh_constraint_object", lock=True)		

	# lock it down
	pymel.lockNode(rig_grp, lock=True)
	pymel.lockNode(mesh_grp, lock=True)
	pymel.lockNode(mat_group, lock=True)
	pymel.setAttr("weapon_root.rh_weapon", lock=True)	
	pymel.lockNode(weapon_root, lock=True)
	pymel.lockNode(weapon_grip, lock=True)	
	pymel.lockNode(weapon_secondary_grip, lock=True)	
	pymel.lockNode("weapon_root_grp", lock=True)
	pymel.lockNode("weapon_root_anim", lock=True)
	pymel.lockNode("weapon_grip_grp", lock=True)
	pymel.lockNode("weapon_grip_anim", lock=True)
	pymel.lockNode("weapon_root_constrain", lock=True)
	pymel.lockNode("weapon_root_constrain_grp", lock=True)
	pymel.lockNode("weapon_secondary_grip_grp", lock=True)
	pymel.lockNode("weapon_secondary_grip_anim", lock=True)	
	pymel.lockNode("weapon_root_world_spaceLoc", lock=True)
	pymel.lockNode("weapon_root_decompose", lock=True)
	pymel.lockNode("Mesh", lock=True)
	pymel.lockNode("Bones", lock=True)

	# lock weapon attrs
	pymel.lockNode("Weapon", lock=False)
	pymel.setAttr("Weapon.rh_mesh_base", lock=True)
	pymel.setAttr("Weapon.rh_item_data_version", lock=True)
	pymel.setAttr("Weapon.rh_item_data", lock=True)
	pymel.setAttr("Weapon.rh_weapon", lock=True)
	pymel.setAttr("Weapon.rh_item_version", lock=True)
	pymel.setAttr("Weapon.rh_material_index", lock=True)
	pymel.setAttr("Weapon.rh_bone_index", lock=True)
	pymel.setAttr("Weapon.rh_item_name", lock=True)
	pymel.setAttr("Weapon.rh_mesh_grp", lock=True)
	pymel.setAttr("Weapon.rh_rig_grp", lock=True)
	pymel.setAttr("Weapon.rh_item_root", lock=True)
	pymel.setAttr("Weapon.rh_item_constraint_object", lock=True)

	# lock this last
	pymel.lockNode(weapon_grp, lock=True)	

	return weapon_grp



