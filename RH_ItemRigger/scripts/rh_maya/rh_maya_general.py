"""
General Python Methods for use in Maya

Author: Randall Hess randall.hess@gmail.com
License: GNU General Public License v3.0
"""

import os
import re
import collections
import time
import contextlib

import maya.mel as mel
import maya.cmds as cmds
import pymel.core as pymel



def get_duplicated_node_names():
	"""
	Get nodes from the scene with the same names

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* randall.hess, randall.hess@gmail.com, 11/23/2014 11:27:15 AM
	"""

	node_names = []
	scene_nodes = pymel.ls("*")

	for node in scene_nodes:
		node = node.split("|")[-1]
		node_names.append(node)


	same_node_names = [x for x, y in collections.Counter(node_names).items() if y > 1]

	return same_node_names
	
	
def get_scene_namespaces():
	"""
	Return a list of namespaces

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* randall.hess, randall.hess@gmail.com, 11/6/2014 1:36:02 PM
	"""
	try:
		cmds.namespace(setNamespace=":")
	except:
		pass

	ignore_names = ["UI","shared"]
	all_namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True)
	namespaces = []
	for namespace in all_namespaces:
		if not any ([x in namespace for x in ignore_names]):
			namespaces.append(namespace)
	return namespaces

	
def validate_text(text, numbers=False):
	"""
	Make sure that incoming text is good

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* randall.hess, randall.hess@gmail.com, 9/6/2014 4:52:39 PM
	"""

	bad_characters = [" ","*","&",""]
	# Option 1: Invalidate one char in string.
	#re1 = re.compile(r"[<>/{}[\]~`]");
	if " " in text:
		cmds.warning("Space Character in Weapon Name: {0}".format(text))
		return False

	if not numbers:
		bad_numbers = re.search(r"\d", text)
		if bad_numbers:
			cmds.warning("Invalid Numbers in Weapon Name: {0}".format(bad_numbers.group(0)))
			return False

	bad_character = re.search(r".*[\%\$\^\*\@\!\-\(\)\:\;\"\"\{\}\[\]\`\~\#\<\>\.\?\+\=\,\/\\\|\&].*", text)
	if bad_character:
		cmds.warning("Invalid Characters in Weapon Name: {0}".format(bad_character.group(0)))
		return False

	return True


def safeDeleteAttr(obj, attr):
	"""
	Safely Remove attribute from object

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* Charles.Wardlaw @kattkieru - http://www.skeletalstudios.com/
	"""

	if isinstance(obj, (str, unicode)):
		node = pymel.PyNode(obj)
	elif isinstance(obj, pymel.PyNode):
		node = obj

	if not node.hasAttr(attr):
		return True

	node.setLocked(False)
	node.setAttr(attr, lock=False)
	try:
		node.deleteAttr(attr)
		return True
	except:
		return False
	
	
def setAttrSpecial(obj, attr, value, prefix=None, channelBox=None, cb=None,
                   preserveValue=False, multi=False, keyable=False, k=False,
                   lock=False, l=False, append=False, **kwargs):
	"""
	Custom setAttr method

	*Arguments:*
		* ``None``

	*Keyword Arguments:*
		* ``None``

	*Returns:*
		* ``None``

	*Author:*
	* Charles.Wardlaw @kattkieru - http://www.skeletalstudios.com/
	"""

	if channelBox is None and cb is None:
		# special-- nothing was passed in
		channelBox = True
	elif channelBox is False or cb is False:
		channelBox = False
	else:
		channelBox = channelBox or cb
	keyable = keyable or k
	lock = lock or l

	attributeType = kwargs.pop("type", None)

	oldValue = None

	if not isinstance(obj, pymel.PyNode):
		obj = pymel.PyNode(obj)
		pymel.lockNode(obj, lock=False)

	attrName = "_".join([prefix, attr]) if prefix is not None else attr

	print(" Setting attr: %s (value %s)" % (attrName, str(value)))

	if attributeType is None:
		# try to intelligently guess the type from what"s been passed in
		if isinstance(value, (list,tuple)):
			if not len(value):
				raise ValueError("setAttrSpecial: empty list passed in.")
			if isinstance(value[0], pymel.PyNode) or isinstance(value[0], (str, unicode)) and cmds.objExists(value[0]):
				attributeType = "message"
				multi = True
			elif len(value) == 3 and unicode(value[0]).isnumeric():
				attributeType = "float3"
		elif isinstance(value, (pymel.dt.Point, pymel.dt.Vector)):
			attributeType = "float3"
		elif isinstance(value, pymel.PyNode) or pymel.objExists(value):
			attributeType = "message"
		elif isinstance(value, unicode) or isinstance(value, str):
			attributeType = "string"
		elif "enumName" in kwargs:
			attributeType="enum"
		elif value is True or value is False:
			attributeType = "bool"
		elif unicode(value).isnumeric():
			attributeType = "float"

	# we have the info-- create the attribute
	attrData = {"multi":multi}

	if attributeType in ["string", "unicode"]:
		attrData["dt"] = "string"
	else:
		attrData["at"] = attributeType

	attrData.update(kwargs)

	try:
		if attributeType == "enum":
			oldValue = obj.attr(attrName).get(asString=True)
		else:
			oldValue = obj.attr(attrName).get()
	except:
		pass

	safeDeleteAttr(obj, attrName)
	# this could still be a compound attribute which cannot be deleted naturally
	if not obj.hasAttr(attrName):
		obj.addAttr(attrName, **attrData)

	if attributeType == "float3":
		childData = deepcopy(attrData)
		childData.pop("at")
		for axis in "XYZ":
			if not obj.hasAttr(attrName+axis):
				obj.addAttr(attrName+axis, p=attrName, at="float", **childData)

		# have to do a second loop because the attribute isn"t "finished"
		# and available for edit until all three are created
		for axis in "XYZ":
			obj.attr(attrName+axis).set(k=False)
			obj.attr(attrName+axis).set(cb=channelBox)

	pAttr = obj.attr(attrName)

	if preserveValue:
		if oldValue is not None:
			value = oldValue

	# doing the set down here is better because string attrs seem
	# to have trouble with default values. Also, this lets you
	# set the float3"s in one go
	if value is not None:
		if attributeType == "message":
			if multi:
				objects = []
				if append and oldValue is not None:
					objects += oldValue

				if isinstance(value, (list, tuple)):
					for item in value:
						if not item in objects:
							objects.append(item)
						else:
							if not isinstance(value, list):
								objects.append(value)

					incoming = pAttr.inputs(plugs=True)
					for plug in incoming:
						pAttr == plug
						pAttr.disconnect()

					added_items = []
					for index, item in enumerate(objects):
						if isinstance(item, pymel.PyNode):
							if not item in added_items:
								added_items.append(item)
							else:
								continue
						pymel.connectAttr(item+".message", pAttr[index], f=True)

					incoming = pAttr.inputs(plugs=True)
					for plug in incoming:
						print "  Plug: {0}".format(plug)

				elif isinstance(value, pymel.PyNode):
					pymel.connectAttr((value + ".message"), (obj + "." + attrName), f=True)					

		elif attributeType == "string":
			# have to convert to string for non-string values
			# or PyMEL kicks up an error
			if multi:
				for index, v in enumerate(value):
					pAttr[index].set(str(v))
			else:
				pAttr.set(str(value))
		else:
			if multi:
				if not attributeType == "float3":
					for index, v in enumerate(value):
						pAttr[index].set(float(v))
			else:
				try:
					pAttr.set(value)
				except Exception as e:
					log("Unable to set value on parameter %s-- %s" % (obj, e.message))

	if not keyable:
		pAttr.set(k=False)
		pAttr.set(cb=channelBox)
	else:
		pAttr.set(k=keyable)

	if lock:
		pAttr.lock()

	return(pAttr)

