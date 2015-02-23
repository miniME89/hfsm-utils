from flask import Flask, request, abort, jsonify
import json
import hashlib

app = Flask(__name__)

applications = {}

@app.route("/applications", methods=['GET'])
def getApplications():
    return jsonify({'applications': applications.values()})

@app.route("/applications/<int:applicationId>", methods=['GET'])
def getApplication(applicationId):
    application = applications[applicationId]
    if len(application) == 0:
        abort(404)

    return jsonify({'application': application[0]})

@app.route('/applications', methods=['POST'])
def addApplication():
    if not request.json:
        abort(400)

    application = {
        'name': request.json.get('name', ''),
        'category': request.json.get('category', ''),
        'description': request.json.get('description', ''),
        'binding': request.json.get('binding', ''),
        'endpoint': request.json.get('endpoint', []),
        'parameters': {
            'input': request.json.get('parameters', {}).get('input', []),
            'output': request.json.get('parameters', {}).get('output', [])
        }
    }
    application['id'] = hashlib.md5(json.dumps({'name': application['name'], 'endpoint': application['endpoint'], 'binding': application['binding']}, sort_keys=True)).hexdigest();
    applications[application['id']] = application

    return jsonify({'application': application}), 201

if __name__ == "__main__":
    app.run(debug=True, port=7000)
