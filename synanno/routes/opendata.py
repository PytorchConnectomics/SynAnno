import json
import logging

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, flash, jsonify, render_template, request
from flask_cors import cross_origin
from werkzeug.datastructures import MultiDict

import synanno.backend.ng_util as ng_util
from synanno.backend.neuron_processing.load_neuron import (
    load_neuron_skeleton,
    neuron_to_bytes,
)
from synanno.backend.neuron_processing.load_synapse_point_cloud import (
    convert_to_point_cloud,
    create_neuron_tree,
    filter_synapse_data,
    get_neuron_coordinates,
    neuron_section_lookup,
    snap_points_to_neuron,
)
from synanno.backend.neuron_processing.partition_neuron import (
    compute_sections,
    sort_sections_by_traversal_order,
)
from synanno.backend.processing import (
    calculate_number_of_pages,
    determine_volume_dimensions,
    load_cloud_volumes,
    retrieve_instance_metadata,
    update_slice_number,
)

# Setup logging
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

# Define a Blueprint for opendata routes
blueprint = Blueprint("open_data", __name__)


@blueprint.route("/open_data", defaults={"task": "annotate"})
@blueprint.route("/open_data/<string:task>", methods=["GET"], endpoint="open_data_task")
def open_data(task: str):
    """Renders open-data view that lets user specify the source, target, and json file.

    Args:
        task: Defined through the path chosen by the user |  'draw', 'annotate'

    Returns:
        Renders the open-data view
    """
    current_app.draw_or_annotate = task

    if current_app.source_image_data:
        flash(
            "Click 'Reset Backend' to clear the memory, start a new task, "
            "and start up a Neuroglancer instance."
        )
        return render_template(
            "opendata.html",
            modecurrent="d-none",
            modenext="d-none",
            modereset="inline",
            mode=current_app.draw_or_annotate,
            view_style="synapse",
            neuronReady="false",
        )
    return render_template(
        "opendata.html",
        modenext="disabled",
        mode=current_app.draw_or_annotate,
        view_style="synapse",
        neuronReady="false",
    )


def save_coordinate_order_and_crop_size(form: MultiDict):
    """Save the coordinate order and crop size to the session and current_app.

    Args:
        form: The form data from the request.
    """
    current_app.coordinate_order = {
        c: (
            form.get("res-source-" + str(i + 1)),
            form.get("res-target-" + str(i + 1)),
        )
        for i, c in enumerate(list(form.get("coordinates")))
    }

    coordinate_order = list(current_app.coordinate_order.keys())

    current_app.crop_size_x = int(
        form.get("crop_size_c" + str(coordinate_order.index("x")))
    )
    current_app.crop_size_y = int(
        form.get("crop_size_c" + str(coordinate_order.index("y")))
    )
    current_app.crop_size_z = int(
        form.get("crop_size_c" + str(coordinate_order.index("z")))
    )

    if (
        current_app.crop_size_x == 0
        or current_app.crop_size_y == 0
        or current_app.crop_size_z == 0
    ):
        flash(
            "The crop sizes have to be larger than zero, the current setting will "
            "result in a crash of the backend!",
            "error",
        )
        raise ValueError(
            "A crop size was set to 0, this will result in a crash of the backend!"
        )


def load_json_to_metadata(file_json):
    """Load the provided JSON file into the metadata DataFrame.

    Args:
        file_json: The JSON file provided by the user.
    """
    try:
        # Read JSON file as a dictionary
        json_data = json.load(file_json)  # file_json is a file-like object

        # Extract "Proofread Time" (store it as a dictionary in the app context)
        if "Proofread Time" in json_data and isinstance(
            json_data["Proofread Time"], dict
        ):
            current_app.proofread_time = json_data["Proofread Time"]
        else:
            logger.warning(
                "Proofread Time missing or invalid in JSON. Setting default."
            )
            current_app.proofread_time = {
                "start_grid": None,
                "finish_grid": None,
                "difference_grid": None,
                "start_categorize": None,
                "finish_categorize": None,
                "difference_categorize": None,
            }

        # Extract metadata
        if "Metadata" not in json_data:
            raise ValueError("Invalid JSON format: 'Metadata' key is missing!")

        metadata_records = json_data["Metadata"]

        # Load into DataFrame
        expected_columns = set(current_app.df_metadata.columns)
        df_new_metadata = pd.DataFrame(metadata_records)

        # Ensure all required columns exist
        actual_columns = set(df_new_metadata.columns)
        missing_columns = expected_columns - actual_columns
        extra_columns = actual_columns - expected_columns

        if missing_columns:
            logger.error(f"Missing columns in JSON: {missing_columns}")
            raise ValueError(f"Missing columns in JSON: {missing_columns}")

        if extra_columns:
            logger.warning(
                f"Extra columns in JSON: {extra_columns} (they will be ignored)"
            )

        # Convert None values to default values based on column types
        for col, dtype in current_app.df_metadata.dtypes.items():
            if dtype == "int64":  # Integers cannot have None, set default as -1 or 0
                df_new_metadata[col] = df_new_metadata[col].fillna(-1).astype(int)
            elif dtype == "float64":  # Floats can have NaN
                df_new_metadata[col] = df_new_metadata[col].astype(float)
            elif dtype == "object":  # Strings & JSON objects
                df_new_metadata[col] = df_new_metadata[col].fillna("")

        # Reorder DataFrame to match expected format
        df_new_metadata = df_new_metadata[current_app.df_metadata.columns]

        # Assign the new DataFrame to the app's metadata
        current_app.df_metadata = df_new_metadata

        # Sort and update slices
        current_app.df_metadata.sort_values(["Page", "Image_Index"], inplace=True)
        update_slice_number(current_app.df_metadata.to_dict("records"))

    except json.JSONDecodeError:
        logger.error("Invalid JSON file: Failed to parse.")
        raise ValueError("Invalid JSON format! Please provide a valid JSON file.")

    except Exception as e:
        logger.error(f"Error loading JSON: {str(e)}")
        raise


def set_coordinate_resolution():
    """Set the coordinate resolution for the source and target cloud volumes."""
    current_app.coord_resolution_source = np.array(
        [int(res[0]) for res in current_app.coordinate_order.values()]
    ).astype(int)
    current_app.coord_resolution_target = np.array(
        [int(res[1]) for res in current_app.coordinate_order.values()]
    ).astype(int)


def calculate_scale_factor():
    """Calculate the scale factor for the source and target cloud volumes."""
    coordinate_order = list(current_app.coordinate_order.keys())
    current_app.scale = {  # noqa: C416
        c: v
        for c, v in zip(
            coordinate_order,
            np.where(
                current_app.coord_resolution_target
                / current_app.coord_resolution_source
                > 0,
                current_app.coord_resolution_target
                / current_app.coord_resolution_source,
                1,
            ),
        )
    }


def validate_cloud_volume_urls(source_url: str, target_url: str, neuropil_url: str):
    """Validate the provided cloud volume URLs.

    Args:
        source_url: URL to the source cloud volume.
        target_url: URL to the target cloud volume.
        neuropil_url: URL to the neuropil cloud volume.

    Returns:
        True if all URLs are valid, False otherwise.
    """
    return all(
        any(bucket in url for bucket in current_app.config["CLOUD_VOLUME_BUCKETS"])
        for url in [source_url, target_url, neuropil_url]
    )


def handle_neuron_view(neuropil_url: str):
    """Handle the neuron view processing.

    Args:
        neuropil_url: URL to the neuropil cloud volume.
    """
    current_app.synapse_data["materialization_index"] = (
        current_app.synapse_data.index.to_series()
    )
    current_app.synapse_data = filter_synapse_data(
        current_app.selected_neuron_id, current_app.synapse_data
    )
    current_app.synapse_data.reset_index(drop=True, inplace=True)

    pruned_neuron = load_neuron_skeleton(neuropil_url, current_app.selected_neuron_id)

    # pruned_neuron = navis_neuron(neuron_skeleton_swc_path)

    current_app.neuron_skeleton = neuron_to_bytes(pruned_neuron)

    sections, pruned_neuron, node_traversal_lookup = compute_sections(
        pruned_neuron, merge=True
    )

    sorted_sections = sort_sections_by_traversal_order(sections, node_traversal_lookup)

    neuron_coords = get_neuron_coordinates(pruned_neuron)
    neuron_tree = create_neuron_tree(neuron_coords)
    neuron_sec_lookup = neuron_section_lookup(sorted_sections, node_traversal_lookup)

    point_cloud = convert_to_point_cloud(current_app.synapse_data)
    indices_of_near_neuron = snap_points_to_neuron(point_cloud, neuron_tree)

    for index in current_app.synapse_data.index:
        node_id = indices_of_near_neuron[index] + 1
        section_idx, traversal_index = neuron_sec_lookup[node_id]
        current_app.synapse_data.at[index, "node_id"] = int(node_id)
        current_app.synapse_data.at[index, "section_index"] = int(section_idx)
        current_app.synapse_data.at[index, "tree_traversal_index"] = int(
            traversal_index
        )

    current_app.synapse_data["node_id"] = current_app.synapse_data["node_id"].astype(
        int
    )
    current_app.synapse_data["section_index"] = current_app.synapse_data[
        "section_index"
    ].astype(int)
    current_app.synapse_data["tree_traversal_index"] = current_app.synapse_data[
        "tree_traversal_index"
    ].astype(int)

    current_app.synapse_data = current_app.synapse_data.sort_values(
        ["section_index", "tree_traversal_index"], ascending=[True, True], inplace=False
    )
    current_app.synapse_data.reset_index(drop=True, inplace=True)

    point_cloud = convert_to_point_cloud(current_app.synapse_data)
    indices_of_near_neuron = snap_points_to_neuron(point_cloud, neuron_tree)

    snapped_point_coordinates = neuron_coords[indices_of_near_neuron]

    current_app.snapped_point_cloud = [
        int(x) for x in snapped_point_coordinates.flatten()
    ]

    current_app.sections = sorted_sections


def handle_synapse_view():
    """Handle the synapse view processing."""
    preid = int(request.form.get("preid")) if request.form.get("preid") else None
    postid = int(request.form.get("postid")) if request.form.get("postid") else None

    if preid is None:
        preid = 0
    if postid is None:
        postid = len(current_app.synapse_data.index)

    current_app.synapse_data["materialization_index"] = (
        current_app.synapse_data.index.to_series()
    )
    current_app.synapse_data = current_app.synapse_data.query(
        "index >= @preid and index <= @postid"
    )
    current_app.synapse_data.reset_index(drop=True, inplace=True)


@blueprint.route("/upload", methods=["GET", "POST"])
def upload_file():
    """Upload the source, target, and json file specified by the user.

    Rerenders open-data view, enabling the user to start the annotation or draw process.

    Returns:
        Renders the open-data view, with additional buttons enabled
    """
    current_app.view_style = request.form.get("view_style")

    save_coordinate_order_and_crop_size(request.form)

    source_url = request.form.get("source_url")
    target_url = request.form.get("target_url")
    neuropil_url = request.form.get("neuropil_url")

    if validate_cloud_volume_urls(source_url, target_url, neuropil_url):
        bucket_secret_json = (
            json.loads(request.files.get("secrets_file").read())
            if request.files.get("secrets_file")
            else "~/.cloudvolume/secrets"
        )
        load_cloud_volumes(source_url, target_url, neuropil_url, bucket_secret_json)
    else:
        flash(
            "Please provide at least the paths to valid source and target "
            " cloud volume buckets!",
            "error",
        )
        return render_template(
            "opendata.html",
            modenext="disabled",
            mode=current_app.draw_or_annotate,
            neuronReady="false",
        )

    set_coordinate_resolution()
    calculate_scale_factor()

    current_app.vol_dim = determine_volume_dimensions()
    current_app.vol_dim_scaled = tuple(
        int(a * b) for a, b in zip(current_app.vol_dim, current_app.scale.values())
    )

    nr_instances = 0

    file_json = request.files["file_json"]
    if file_json.filename:
        load_json_to_metadata(file_json)
        nr_instances = len(current_app.df_metadata.index)

    if current_app.view_style == "neuron":
        if (
            current_app.selected_neuron_id == 0
            or current_app.selected_neuron_id is None
        ):
            flash(
                "Please select a valid neuron under 'Synapse Selection' "
                "by clicking 'Choose a Neuron'.",
                "error",
            )
            return render_template(
                "opendata.html",
                modenext="disabled",
                mode=current_app.draw_or_annotate,
                view_style="neuron",
                neuronReady="false",
            )

        handle_neuron_view(neuropil_url)
        current_app.neuron_ready = "true"
    elif current_app.view_style == "synapse":
        handle_synapse_view()

    if nr_instances == 0:
        nr_instances = len(current_app.synapse_data.index)
    current_app.n_pages = calculate_number_of_pages(nr_instances, current_app.per_page)

    retrieve_instance_metadata(page=0, mode=current_app.draw_or_annotate)

    if current_app.ng_version is None:
        ng_util.setup_ng(
            app=current_app._get_current_object(),
            source="precomputed://" + source_url,
            target="precomputed://" + target_url,
            neuropil="precomputed://" + neuropil_url,
        )

    flash("Data ready!")
    return render_template(
        "opendata.html",
        modecurrent="disabled",
        modeform="formFileDisabled",
        view_style=current_app.view_style,
        mode=current_app.draw_or_annotate,
        neuronReady=current_app.neuron_ready,
        neuronSection=current_app.sections,
        synapsePointCloud=current_app.snapped_point_cloud,
    )


@blueprint.route("/set-data/<string:task>", methods=["GET"], endpoint="set_data_task")
@blueprint.route("/set-data")
def set_data(task: str = "annotate"):
    """Used by the annotation and the draw view to set up the session.

    Annotation view: Setup the session, calculate the grid view, render annotation view
    Draw view: Reload the updated JSON, render the draw view

    Args:
        task: Identifies and links the downstream process: annotate | draw

    Returns:
        Renders either the annotation or the draw view dependent on the user action
    """
    if task == "draw":
        data = current_app.df_metadata.query('Label != "Correct"').sort_values(
            by="Image_Index"
        )
        data = data.to_dict("records")
        return render_template("draw.html", images=data)
    else:
        page = 0
        data = (
            current_app.df_metadata.query("Page == @page")
            .sort_values(by="Image_Index")
            .to_dict("records")
        )

        return render_template(
            "annotation.html",
            images=data,
            page=page,
            n_pages=current_app.n_pages,
            grid_opacity=current_app.grid_opacity,
            neuron_id=current_app.selected_neuron_id,
            neuronReady=current_app.neuron_ready,
            neuronSection=current_app.sections,
            synapsePointCloud=current_app.snapped_point_cloud,
        )


@blueprint.route("/get_instance", methods=["POST"])
@cross_origin()
def get_instance():
    """Serves one of two Ajax calls from annotation.js, passing instance specific info

    Returns:
        The instance specific data
    """
    coordinate_order = list(current_app.coordinate_order.keys())

    str(request.form["mode"])
    load = str(request.form["load"])
    page = int(request.form["page"])
    index = int(request.form["data_id"])

    if load == "full":
        with current_app.df_metadata_lock:

            number_of_slices = len(current_app.source_image_data[str(index)])

            middle_slice = int(
                current_app.df_metadata.loc[
                    (current_app.df_metadata["Page"] == page)
                    & (current_app.df_metadata["Image_Index"] == index),
                    "Middle_Slice",
                ].item()
            )

            data = current_app.df_metadata.query(
                "Page == @page & Image_Index == @index"
            ).to_dict("records")[0]

        range_min = data["Adjusted_Bbox"][coordinate_order.index("z") * 2]

        data = json.dumps(data)

        final_json = jsonify(
            data=data,
            number_of_slices=number_of_slices,
            halflen=middle_slice,
            range_min=range_min,
            host=current_app.config["IP"],
            port=current_app.config["PORT"],
        )

    elif load == "single":
        data = current_app.df_metadata.query(
            "Page == @page & Image_Index == @index"
        ).to_dict("records")[0]

        data = json.dumps(data)

        final_json = jsonify(data=data)

    return final_json


@blueprint.route("/neuro", methods=["POST"])
@cross_origin()
def neuro():
    """Serves an Ajax request from annotation.js or draw_module.js, shifting the view
    focus with in the running NG instance and passing the link for the instance to the
    frontend.

    Returns:
        Passes the link to the NG instance as json.
    """
    coordinate_order = list(current_app.coordinate_order.keys())

    mode = str(request.form["mode"])
    center = {}
    if mode == "annotate":
        center["z"] = int(int(request.form["cz0"]) * current_app.scale["z"])
        center["y"] = int(int(request.form["cy0"]) * current_app.scale["y"])
        center["x"] = int(int(request.form["cx0"]) * current_app.scale["x"])
    elif mode == "draw":
        center["z"] = int(
            (current_app.vol_dim[coordinate_order.index("z")] // 2)
            * current_app.scale["z"]
        )
        center["y"] = int(
            (current_app.vol_dim[coordinate_order.index("y")] // 2)
            * current_app.scale["y"]
        )
        center["x"] = int(
            (current_app.vol_dim[coordinate_order.index("x")] // 2)
            * current_app.scale["x"]
        )

    if current_app.ng_version is not None:
        with current_app.ng_viewer.txn() as s:
            s.position = [
                center[coordinate_order[0]],
                center[coordinate_order[1]],
                center[coordinate_order[2]],
            ]

    else:
        raise Exception("No NG instance running")

    logger.info(
        f"Neuroglancer instance running at {current_app.ng_viewer}, centered at "
        f"{coordinate_order[0]},{coordinate_order[1]},{coordinate_order[2]}: "
        f"{center[coordinate_order[0]], center[coordinate_order[1]]}, "
        f"{center[coordinate_order[2]]}."
    )

    final_json = jsonify(
        {
            "ng_link": "http://"
            + current_app.config["IP"]
            + ":9015/v/"
            + str(current_app.ng_version)
            + "/"
        }
    )

    return final_json


@blueprint.route("/enable_neuropil_layer", methods=["POST"])
def enable_neuropil_layer():
    """Enable the neuropil neuron segmentation layer in the global Neuroglancer."""
    with current_app.ng_viewer.txn() as s:
        s.layers["neuropil"].selectedAlpha = 0.5
        s.layers["neuropil"].notSelectedAlpha = 0.1
    return jsonify({"status": "neuropil layer enabled"})


@blueprint.route("/disable_neuropil_layer", methods=["POST"])
def disable_neuropil_layer():
    """Disable the neuropil neuron segmentation layer in the global Neuroglancer."""
    with current_app.ng_viewer.txn() as s:
        s.layers["neuropil"].selectedAlpha = 0.0
        s.layers["neuropil"].notSelectedAlpha = 0.0
    return jsonify({"status": "neuropil layer disabled"})


@blueprint.route("/launch_neuroglancer", methods=["GET", "POST"])
def launch_neuroglancer():
    source_url = request.args.get("source_url")
    target_url = request.args.get("target_url")
    neuropil_url = request.args.get("neuropil_url")

    if not hasattr(current_app, "ng_viewer") or current_app.ng_viewer is None:
        ng_util.setup_ng(
            app=current_app._get_current_object(),
            source="precomputed://" + source_url,
            target="precomputed://" + target_url,
            neuropil="precomputed://" + neuropil_url,
        )

    ng_url = (
        f"http://{current_app.config['NG_IP']}:"
        f"{current_app.config['NG_PORT']}/v/{current_app.ng_viewer.token}/"
    )
    return jsonify({"ng_url": ng_url})


@blueprint.route("/load_materialization", methods=["POST"])
def load_materialization():
    materialization_path = request.json.get("materialization_url")

    if materialization_path is None or materialization_path == "":
        return jsonify({"error": "Materialization path is missing."}), 400
    try:
        logger.info("Loading the materialization table...")
        path = materialization_path.replace("file://", "")
        current_app.synapse_data = pd.read_csv(path)

        logger.info("Materialization table loaded successfully!")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logger.info(f"Failed to load materialization table: {e}")
        return jsonify({"error": str(e)}), 500


@blueprint.route("/get_neuron_id", methods=["GET"])
def get_neuron_id():
    """Get the current coordinates of the Neuroglancer instance."""
    return jsonify({"selected_neuron_id": current_app.selected_neuron_id})
