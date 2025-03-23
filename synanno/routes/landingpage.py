# flask util functions
from flask import Blueprint, render_template

# for type hinting

# define a Blueprint for landingpage routes
blueprint = Blueprint("landingpage", __name__)


@blueprint.route("/")
def landing():
    return render_template("landingpage.html")


@blueprint.route("/viewer")
def viewer():
    return render_template("viewer.html")
