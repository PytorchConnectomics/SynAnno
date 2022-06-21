from flask import render_template, session

from synanno import app

@app.route('/draw')
def draw():
    return render_template('draw_mask.html', pages=session.get('data'))