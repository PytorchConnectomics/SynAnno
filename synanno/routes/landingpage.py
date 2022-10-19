from synanno import app

from jinja2 import Template # for function type hint
from flask import render_template  # to render the template


@app.route("/")
def landing() -> Template:
    # render the template of the landing page
    return render_template("landingpage.html") 