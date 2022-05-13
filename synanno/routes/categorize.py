from flask import render_template, session

# import the package app 
from synanno import app

import os
import json


@app.route('/categorize')
def categorize():
    return render_template('categorize.html', images=session.get('data')[0], page=0, n_pages=session.get('n_pages'))