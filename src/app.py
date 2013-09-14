from flask import Flask
from mongokit import Connection

MONGODB_HOST = 'localhost'
MONGODB_PORT = 27017

app = Flask(__name__)
app.config.from_object(__name__)

mongoConnection = Connection(	app.config['MONGODB_HOST'],
				app.config['MONGODB_PORT'])

DBSession = mongoConnection['cloudDB']
