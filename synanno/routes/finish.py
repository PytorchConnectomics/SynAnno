# flask 
from flask import render_template, session, send_file

# os and process dependent imports
import os
import os.path
import shutil

# import the package app 
from synanno import app
import synanno

# json dependent imports
import json


@app.route('/final_page')
def final_page():
    return render_template('exportdata.html')

@app.route('/export')
def export_data():
    final_filename = 'results-' + session.get('filename')
    # Exporting the final json and pop session
    if session.get('data') and session.get('n_pages'):
        final_file = dict()
        final_file['Data'] = sum(session['data'], [])
        with open(os.path.join(app.config['PACKAGE_NAME'],os.path.join(app.config['UPLOAD_FOLDER']),final_filename), 'w') as f:
            json.dump(final_file, f)
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'],final_filename), as_attachment=True, attachment_filename=final_filename)
    else:
        return render_template('exportdata.html')


@app.route('/reset')
def reset():

    # reset progress bar 
    synanno.progress_bar_status = {"status":"Loading Source File", "percent":0}

    # pop all the session content.
    for key in list(session.keys()):
        session.pop(key)

    # delete all the uploaded h5 files
    if os.path.exists(os.path.join('.', os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']))):
        for filename in os.listdir(os.path.join('.', os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']))):
            file_path = os.path.join(
                os.path.join('.', os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER'])), filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

    # delete json file.
    if os.path.isfile(os.path.join('.', 'synAnno.json')):
        os.remove(os.path.join('.', 'synAnno.json'))

    # delete static images
    image_folder = './synanno/static/Images/'
    if os.path.exists(image_folder):
        try:
            shutil.rmtree(image_folder)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    return render_template('opendata.html', modenext='disabled')
