from flask import render_template, session, request

from synanno import app

from PIL import Image
from io import BytesIO
import numpy as np
import base64
import json
import re

@app.route('/draw')
def draw():
    return render_template('draw.html', pages=session.get('data'))

@app.route('/save_canvas', methods=['POST'])
def save_canvas():
    image_data = re.sub('^data:image/.+;base64,', '', request.form['imageBase64'])
    im = Image.open(BytesIO(base64.b64decode(image_data)))

    patch_size = session['patch_size']
    im = im.resize((patch_size, patch_size), Image.ANTIALIAS)
    im.save('CAVAS.png')

    print(np.array(im).shape)

    return json.dumps({'result': 'success'}), 200, {'ContentType': 'application/json'}
