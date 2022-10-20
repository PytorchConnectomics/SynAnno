from flask import session
import json


def reload_json(path):
    ''' Loads the Json and overwrites the current session information with its content

        Args:
            path: Path to the Json
    '''
    # open the json data and save it to the session
    f = open(path)
    data = json.load(f)

    # write the data to the session
    session['data'] = [data['Data'][i:i+session.get('per_page')]
                       for i in range(0, len(data['Data']), session.get('per_page'))]

