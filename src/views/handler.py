from app import app
from flask import request

@app.errorhandler(404)
def page_not_found(e):
	return "404 Not Found !!!!"
