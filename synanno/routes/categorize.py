from crypt import methods
from flask import render_template, session, request, Response

# import the package app 
from synanno import app
from flask_cors import cross_origin


@app.route('/categorize')
def categorize():
    return render_template('categorize.html', pages=session.get('data'))


@app.route('/pass_flags', methods=['POST'])
@cross_origin()
def pass_flags():
    flag = request.form.getlist('flag[]')
    print("Debug")
    print(flag)
    
    data = session.get('data')

    page_nr, img_nr, f = flag
    data[int(page_nr)][int(img_nr)]['Error_Description'] = str(f)

    session['data'] = data
    print(session['data'])
    return Response(status = 200)
