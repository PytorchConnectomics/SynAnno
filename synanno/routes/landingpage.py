# import the package app
from synanno import app

# flask util functions
from flask import render_template

# for type hinting
from jinja2 import Template


@app.route("/")
def landing() -> Template:
    # render the template of the landing page
    return render_template("landingpage.html")
