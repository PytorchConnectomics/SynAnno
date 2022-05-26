from flask import render_template

from synanno import app

@app.route('/draw')
def draw():
    return render_template('manual_annotate.html')