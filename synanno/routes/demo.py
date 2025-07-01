import logging

import pandas as pd
from flask import Blueprint, current_app, render_template, session

import synanno.backend.ng_util as ng_util
from synanno import initialize_global_variables
from synanno.backend.processing import (
    calculate_number_of_pages_for_neuron_section_based_loading,
    determine_volume_dimensions,
    load_cloud_volumes,
)
from synanno.routes.opendata import (
    calculate_scale_factor,
    handle_neuron_view,
    set_coordinate_resolution,
)

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

blueprint = Blueprint("demo", __name__)


@blueprint.route("/demo", methods=["GET"])
def demo():
    """Displays a loading page and resets the session storage.

    Returns:
        Renders the loading page.
    """

    # Reset logic
    session.clear()
    initialize_global_variables(current_app)

    return render_template("demo_setup.html", next_route="/demo_annotation")


@blueprint.route("/demo_annotation", methods=["GET"])
def demo_init():
    """Initializes the demo data and renders the annotation view.

    Returns:
        Renders the annotation view after initializing the demo data.
    """
    # Upload logic
    current_app.view_style = "view_style"
    current_app.tiles_per_page = 12

    current_app.crop_size_x = 256
    current_app.crop_size_y = 256
    current_app.crop_size_z = 6

    current_app.coordinate_order = {"x": (4, 8), "y": (4, 8), "z": (33, 33)}

    source_url = "gs://h01-release/data/20210601/4nm_raw"
    target_url = "gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol"
    neuropil_url = "gs://h01-release/data/20210601/proofread_104"

    current_app.synapse_data = pd.read_csv("/app/h01/h01_104_materialization.csv")

    load_cloud_volumes(source_url, target_url, neuropil_url, "~/.cloudvolume/secrets")

    current_app.vol_dim = determine_volume_dimensions()

    set_coordinate_resolution()
    calculate_scale_factor()

    current_app.vol_dim_scaled = tuple(
        int(a * b) for a, b in zip(current_app.vol_dim, current_app.scale.values())
    )

    current_app.selected_neuron_id = 2325998949

    handle_neuron_view(neuropil_url)
    current_app.neuron_ready = "true"
    current_app.n_pages = calculate_number_of_pages_for_neuron_section_based_loading()

    if current_app.ng_version is None:
        ng_util.setup_ng(
            app=current_app._get_current_object(),
            source="precomputed://" + source_url,
            target="precomputed://" + target_url,
            neuropil="precomputed://" + neuropil_url,
        )

    page = 1
    return render_template(
        "annotation.html",
        page=page,
        n_pages=current_app.n_pages,
        grid_opacity=current_app.grid_opacity,
        neuron_id=current_app.selected_neuron_id,
        neuronReady=current_app.neuron_ready,
        neuronSections=current_app.sections,
        synapsePointCloud=current_app.snapped_point_cloud,
        activeNeuronSection=(
            current_app.page_section_mapping[page][0]
            if page in current_app.page_section_mapping
            else 0
        ),
        activeSynapseIDs=current_app.synapse_data.query("page == @page").index.tolist(),
    )
