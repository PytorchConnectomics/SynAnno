# flask util functions
from flask import render_template

# for type hinting
from jinja2 import Template

from flask import Blueprint
from flask import current_app as app


# define a Blueprint for landingpage routes
blueprint = Blueprint("landingpage", __name__)


@blueprint.route("/")
def landing() -> Template:
    # render the template of the landing page
    return render_template("landingpage.html")


@blueprint.route("/viewer")
def shark_view() -> Template:
    # render the template of the shark view
    return render_template("viewer.html")
