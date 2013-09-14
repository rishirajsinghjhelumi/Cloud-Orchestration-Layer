from sys import argv
from os import system

from setuptools.command import easy_install
from mongokit import Connection

mongoConnection = Connection()
DBSession = mongoConnection['cloudDB']

def getPhysicalMachines(fileName):

	f = open(fileName,"r").read().splitlines()
	physicalMachines = [line for line in f]
	return physicalMachines

def getImageFiles(fileName):

	f = open(fileName,"r").read().splitlines()
	imageFiles = [line for line in f]
	return imageFiles

def getVMTypesDict(fileName):

	f = open(fileName,"r").read()
	vmTypes = eval(f)
	return vmTypes

def getPackages():

	f = open("installs","r").read().splitlines()
	packages = [line for line in f]
	return packages

def savePhysicalMachines(machines):

	for machine in machines:
		idCounter = DBSession.machines.count() + 1
		user , ip = machine.split('@')
		tempMachine = {	'_id' : idCounter , 
				'location' : machine , 
				'user' : user , 
				'ip' : ip}
		DBSession.machines.insert(tempMachine)

def saveImageFiles(images):

	for image in images:
		idCounter = DBSession.images.count() + 1
		name = image.split('/')[-1]
		user , ip = image.split(':')[0].split('@')
		tempImage = {	'_id' : idCounter , 
				'location' : image , 
				'name' : name , 
				'user' : user , 
				'ip' : ip}
		DBSession.images.insert(tempImage)

def saveVMTypes(vmTypes):

	for vmType in vmTypes['types']:
		DBSession.vmtypes.insert(vmType)

def installPackage(package):
	easy_install.main(["-U", package])

def copyImagesToServer():

	images = DBSession.images.find()
	for image in images:
		location = image['location']
		fileName = "../src/images/" + image['name'] + "__" + str(image['_id'])
		system('scp "%s" "%s" ' % (location , fileName) )


if __name__ == "__main__":

	mongoConnection.drop_database('cloudDB')

	savePhysicalMachines(getPhysicalMachines(argv[1]))
	saveImageFiles(getImageFiles(argv[2]))
	saveVMTypes(getVMTypesDict(argv[3]))

	copyImagesToServer()


