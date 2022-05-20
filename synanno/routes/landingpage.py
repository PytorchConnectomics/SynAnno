from flask import render_template


from synanno import app


@app.route("/")
def landing():
    return render_template("landingpage.html")