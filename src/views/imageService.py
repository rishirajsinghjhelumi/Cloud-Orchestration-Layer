from app import app
from app import DBSession

from flask import request
from flask import jsonify

@app.route("/image/list",methods=['POST', 'GET'])
def imageList():

	images = []
	for image in list(DBSession.images.find()):
		tempImage = {}
		tempImage['id'] = image['_id']
		tempImage['name'] = image['name']
		images.append(tempImage)

	return jsonify(images = images)
