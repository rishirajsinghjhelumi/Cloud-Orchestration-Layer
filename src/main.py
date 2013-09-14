from app import app
from app import DBSession

import views.virtualMachine
import views.imageService
import views.handler
import views.blockStorage

@app.route("/",methods=['GET','POST'])
def indexPage():
	
	return "Cloud Orchestration Application...."

if __name__ == "__main__":

	app.run(host='0.0.0.0',debug=True)
