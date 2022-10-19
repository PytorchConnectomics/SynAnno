# flask 
from flask import render_template, session, send_file

# os and process dependent imports
import os
import os.path
import shutil

# import the package app 
from synanno import app
import synanno

# to zip folder
import shutil



@app.route('/export_json')
def export_json():
    return render_template('export_json.html')

@app.route('/export_masks')
def export_masks():
    return render_template('export_masks.html')

@app.route('/export/<string:data_type>', methods=['GET'])
def export_data(data_type):
    if data_type == 'json':
        path_json = session.get('path_json').split
        # Exporting the final json
        if session.get('data') and session.get('n_pages'):

            return send_file(os.path.join(os.path.join(app.root_path,app.config['UPLOAD_FOLDER']), app.config['JSON']), as_attachment=True, attachment_filename=app.config['JSON'])
        else:
            return render_template('export_json.html')
    elif data_type == 'mask':
        total_folder_path = os.path.join(os.path.join(app.root_path,app.config['STATIC_FOLDER']),'custom_masks')
        if os.path.exists(total_folder_path):
            # create zip of folder
            shutil.make_archive(total_folder_path, 'zip', total_folder_path)
            return send_file(os.path.join(os.path.join(app.root_path,app.config['STATIC_FOLDER']), 'custom_masks.zip'), as_attachment=True)
        else:
            return render_template('export_masks.html')    


@app.route('/reset')
def reset():

    # reset progress bar 
    synanno.progress_bar_status = {"status":"Loading Source File", "percent":0}

    # reset time
    synanno.proofread_time = dict.fromkeys(synanno.proofread_time, None)

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
    if os.path.isfile(os.path.join(os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']),app.config['JSON'])):
        os.remove(os.path.join(os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']),app.config['JSON']))

    # delete static images
    image_folder = './synanno/static/Images/'
    if os.path.exists(os.path.join(image_folder, "Img")):
        try:
            shutil.rmtree(os.path.join(image_folder, "Img"))
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    if os.path.exists(os.path.join(image_folder, "Syn")):
        try:
            shutil.rmtree(os.path.join(image_folder, "Syn"))
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    # delete masks zip file.
    if os.path.isfile(os.path.join('./synanno/static/', 'custom_masks.zip')):
        os.remove(os.path.join('./synanno/static/', 'custom_masks.zip'))

    # delete custom masks
    image_folder = './synanno/static/custom_masks/'
    if os.path.exists(image_folder):
        try:
            shutil.rmtree(image_folder)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    return render_template('landingpage.html')
