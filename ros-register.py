import roslib.message
import rosgraph
import rospy
import json
import yaml
import re
import socket
import requests
try:
    from cStringIO import StringIO  # Python 2.x
except ImportError:
    from io import StringIO  # Python 3.x

regexArray = re.compile(r'\[[^\]]*\]')
rosTimeTypes = ['time', 'duration']
rosPrimitiveTypes = ['bool', 'byte', 'char', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64', 'float32', 'float64', 'string']
rosTypesMapping = {
    'Boolean': ['bool'],
    'Integer': ['int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64'],
    'Float': ['float32', 'float64'],
    'String': ['byte', 'char', 'string']
}

def getTopics():
    master = rosgraph.Master('/rostopic')
    topics = master.getTopicTypes()
    topics = [{'topic': topic[0], 'type': topic[1]} for topic in topics if not topic[0].endswith(('/cancel', '/feedback', '/goal', '/result', '/status'))]

    return topics

def getActions():
    master = rosgraph.Master('/rostopic')
    topics = master.getTopicTypes()
    topics = [{'topic': topic[0][:-7], 'type': topic[1][:-6]} for topic in topics if topic[0].endswith('/result')]

    return topics

def getServices():
    master = rosgraph.Master('/rosservice')
    services = master.getSystemState()[2]
    services = [{'topic': service[0]} for service in services]

    for service in services:
        serviceUri = master.lookupService(service['topic'])
        service['type'] = getServiceType(service['topic'], serviceUri)

    return services

def getServiceType(serviceName, serviceUri):
    dest_addr, dest_port = rospy.parse_rosrpc_uri(serviceUri)
    if rosgraph.network.use_ipv6():
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(5.0)
        s.connect((dest_addr, dest_port))
        header = { 
            'probe': '1',
            'md5sum': '*',
            'callerid': '/rosservice',
            'service': serviceName
        }
        rosgraph.network.write_ros_handshake_header(s, header)

        return rosgraph.network.read_ros_handshake_header(s, StringIO(), 2048).get('type', None)
    finally:
        if s is not None:
            s.close()

def getTopicMessage(messageType):
    message = decodeObject(messageType, None)

    return message['value']

def getActionMessage(messageType):
    goalMessage = decodeObject(messageType + 'Goal', None)
    resultMessage = decodeObject(messageType + 'Result', None)

    return (goalMessage['value'], resultMessage['value'])

def getServiceMessage(messageType):
    def decodeService(instance):
        prop = []
        properties = dict(zip(instance.__slots__, instance._slot_types))
        for propertyName, propertyType in properties.items():
            prop.append(decodeType(propertyType, propertyName))

        return prop

    propertyTypeClass = roslib.message.get_service_class(messageType)

    requestMessage = decodeService(propertyTypeClass()._request_class())
    responseMessage = decodeService(propertyTypeClass()._response_class())

    return (requestMessage, responseMessage)

def decodeType(propertyType, propertyName):
    if propertyType in rosTimeTypes:
        return decodeTime(propertyType, propertyName)
    elif propertyType in rosPrimitiveTypes:
        return decodePrimitive(propertyType, propertyName)
    elif regexArray.search(propertyType) is not None:
        return decodeArray(propertyType, propertyName)
    else:
        return decodeObject(propertyType, propertyName)

def decodePrimitive(propertyType, propertyName):
    prop = {}
    prop['name'] = propertyName

    #map ROS primitive type
    primitiveType = 'Unknown'
    for primitiveTypeMap, primitiveTypeMaps  in rosTypesMapping.items():
        if propertyType in primitiveTypeMaps:
            primitiveType = primitiveTypeMap

    prop['type'] = primitiveType

    if primitiveType == 'Boolean':
        prop['value'] = True
    elif primitiveType == 'Integer':
        prop['value'] = 0
    elif primitiveType == 'Float':
        prop['value'] = 0.0
    elif primitiveType == 'String':
        prop['value'] = ''

    return prop

def decodeTime(propertyType, propertyName):
    prop = {}
    prop['type'] = 'Object'
    prop['name'] = propertyName
    prop['value'] = []

    prop['value'].append({
        'type': 'Integer',
        'name': 'secs',
        'value': 0
    })
    prop['value'].append({
        'type': 'Integer',
        'name': 'nsecs',
        'value': 0
    })

    return prop

def decodeArray(propertyType, propertyName):
    prop = {}
    prop['type'] = 'Array'
    prop['name'] = propertyName
    prop['value'] = []

    arrayType = regexArray.sub('', propertyType)
    prop['value'].append(decodeType(arrayType, ''))

    return  prop

def decodeObject(propertyType, propertyName, o=None):
    prop = {}
    prop['type'] = 'Object'
    prop['name'] = propertyName
    prop['value'] = []

    #get ROS message
    propertyTypeClass = roslib.message.get_message_class(propertyType)
    propertyTypeInstance = propertyTypeClass()

    #read and convert properties of the message recursively
    properties = dict(zip(propertyTypeInstance.__slots__, propertyTypeInstance._slot_types))
    for propertyName, propertyType in properties.items():
        prop['value'].append(decodeType(propertyType, propertyName))

    return prop

topics = getTopics()
for topic in topics:
    message = getTopicMessage(topic['type'])
    application = {
        'name': topic['topic'],
        'category': "ROS Topics",
        'description': "",
        'binding': "ROS",
        'endpoint': [
            {
                'type': 'String',
                'name': 'topic',
                'value': topic['topic']
            },
            {
                'type': 'String',
                'name': 'type',
                'value': 'publish'
            }
        ],
        'parameters': {
            'input': message,
            'output': []
        }
    }
    headers = {
        'content-type': 'application/json'
    }

    response = requests.post('http://localhost:7000/applications', data=json.dumps(application), headers=headers);
    print response

actions = getActions()
for action in actions:
    goalMessage, resultMessage = getActionMessage(action['type'])
    application = {
        'name': action['topic'],
        'category': "ROS Actions",
        'description': "",
        'binding': "ROS",
        'endpoint': [
            {
                'type': 'String',
                'name': 'topic',
                'value': action['topic']
            },
            {
                'type': 'String',
                'name': 'type',
                'value': 'action'
            }
        ],
        'parameters': {
            'input': goalMessage,
            'output': resultMessage
        }
    }
    headers = {
        'content-type': 'application/json'
    }

    response = requests.post('http://localhost:7000/applications', data=json.dumps(application), headers=headers);
    print response

services = getServices()
for service in services:
    requestMessage, responseMessage = getServiceMessage(service['type'])
    application = {
        'name': service['topic'],
        'category': "ROS Services",
        'description': "",
        'binding': "ROS",
        'endpoint': [
            {
                'type': 'String',
                'name': 'topic',
                'value': service['topic']
            },
            {
                'type': 'String',
                'name': 'type',
                'value': 'service'
            }
        ],
        'parameters': {
            'input': requestMessage,
            'output': responseMessage
        }
    }
    headers = {
        'content-type': 'application/json'
    }

    response = requests.post('http://localhost:7000/applications', data=json.dumps(application), headers=headers);
    print response
