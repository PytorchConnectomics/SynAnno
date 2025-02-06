$(document).ready(function () {
  // update the instance specific values
  $(".image-card-btn").on("click", function () {
    var data_id = $(this).attr("data_id");
    var page = $(this).attr("page");
    var label = $(this).attr("label");

    // update the label in the backend
    req = $.ajax({
      url: "/update-card",
      type: "POST",
      data: { data_id: data_id, page: page, label: label },
    });

    // update the label in the frontend
    req.done(function (data) {
      if (label === "Unsure") {
        $("#id" + data_id)
          .removeClass("unsure")
          .addClass("correct");
        $("#id-a-" + data_id).attr("label", "Correct");
      } else if (label === "Incorrect") {
        $("#id" + data_id)
          .removeClass("incorrect")
          .addClass("unsure");
        $("#id-a-" + data_id).attr("label", "Unsure");
      } else if (label === "Correct") {
        $("#id" + data_id)
          .removeClass("correct")
          .addClass("incorrect");
        $("#id-a-" + data_id).attr("label", "Incorrect");
      }
    });
  });

  // Enable the neuropil neuron segmentation layer
function enableNeuropilLayer() {
  fetch('/enable_neuropil_layer', { method: 'POST' })
      .then(response => response.json())
      .then(data => console.log(data.status))
      .catch(error => console.error('Error enabling neuropil layer:', error));
}

// Disable the neuropil neuron segmentation layer
function disableNeuropilLayer() {
  fetch('/disable_neuropil_layer', { method: 'POST' })
      .then(response => response.json())
      .then(data => console.log(data.status))
      .catch(error => console.error('Error disabling neuropil layer:', error));
}

  // link to the NG, edited when ever right clicking an instance in the grid view
  var ng_link;

  // variables for the coordinates of the focus of the view with in the NG
  var cz0;
  var cy0;
  var cx0;

  // retrieve and set the information for the modal instance view
  $(".image-card-btn").bind("contextmenu", async function (e) {
    e.preventDefault();

    // instance identifiers
    var data_id = $(this).attr("data_id");
    var page = $(this).attr("page");

    // the instance label
    var label = $(this).attr("label");

    // we are currently in the annotation mode
    var mode = "annotate";

    // we require the information about the whole instance
    var load = "full";

    // retrieve the info from the backend
    req_data = $.ajax({
      url: "/get_instance",
      type: "POST",
      data: { mode: mode, load: load, data_id: data_id, page: page },
    });

    // update the modal
    await req_data.done(function (data) {
      data_json = JSON.parse(data.data);
      $("#rangeSlices").attr("min", data.range_min);
      $("#rangeSlices").attr("max", data.range_min + data.slices_len - 1);
      $("#rangeSlices").val(data.halflen);
      $("#rangeSlices").attr("data_id", data_id);
      $("#rangeSlices").attr("page", page);

      $("#minSlice").html(0);
      $("#maxSlice").html(data.slices_len - 1);

      $("#imgDetails-EM").addClass(label.toLowerCase());
      $("#imgDetails-EM").attr(
        "src",
        staticBaseUrl + data_json.EM + "/" + data_json.Middle_Slice + ".png",
      );
      $("#imgDetails-GT").attr(
        "src",
        staticBaseUrl + data_json.GT + "/" + data_json.Middle_Slice + ".png",
      );
      $("#detailsModal").modal("show");

      cz0 = data_json.cz0;
      cy0 = data_json.cy0;
      cx0 = data_json.cx0;
    });

    // retrieve the updated NG link
    req_ng = $.ajax({
      url: "/neuro",
      type: "POST",
      data: { cz0: cz0, cy0: cy0, cx0: cx0, mode: "annotate" },
    });

    req_ng.done(function (data) {
      ng_link = data.ng_link;
    });
  });

  $("#ng-link").on("click", function () {
    // update the NG link on click
    $("#ng-iframe").attr("src", ng_link);
  });

  // with in the modal view retrieve the instance specific data
  // to switch between the slices
  $("#rangeSlices").on("input", function () {
    // the current slice index
    var rangeValue = $(this).val();

    // the instance identifiers
    var data_id = $(this).attr("data_id");
    var page = $(this).attr("page");

    // we are currently in the annotation mode
    var mode = "annotate";

    // we only require the path to load a single slice and the corresponding GT
    var load = "single";

    // retrieve the information from the backend
    req = $.ajax({
      url: "/get_instance",
      type: "POST",
      data: { mode: mode, load: load, data_id: data_id, page: page },
    });

    // update the slice and GT that is depicted
    req.done(function (data) {
      data_json = JSON.parse(data.data);
      $("#imgDetails-EM").attr("src", staticBaseUrl + data_json.EM + "/" + rangeValue + ".png");
      $("#imgDetails-GT").attr("src", staticBaseUrl + data_json.GT + "/" + rangeValue + ".png");
    });
  });
});

// modal view: decrease the opacity of the GT mask
function dec_opacity() {
  var value = $("#value-opacity").attr("value");
  var new_value = value - 0.1;
  if (new_value < 0) {
    new_value = 0;
  }
  $("#value-opacity").attr("value", new_value);
  $("#value-opacity").text(new_value.toFixed(1));
  $("#imgDetails-GT").css("opacity", new_value);
}

// modal view: increase the opacity of the GT mask
function add_opacity() {
  var value = $("#value-opacity").attr("value");
  var new_value = parseFloat(value) + 0.1;
  if (new_value >= 1) {
    new_value = 1;
  }
  $("#value-opacity").attr("value", new_value);
  $("#value-opacity").text(new_value.toFixed(1));
  $("#imgDetails-GT").css("opacity", new_value);
}

// grid view: decrease the opacity of the GT masks
function dec_opacity_grid() {
  var value = $("#value-opacity-grid").attr("value");
  var new_value = value - 0.1;
  if (new_value < 0) {
    new_value = 0;
  }
  $("#value-opacity-grid").attr("value", new_value);
  $("#value-opacity-grid").text(new_value.toFixed(1));
  $('[id^="imgEM-GT-"]').each(function () {
    $(this).css("opacity", new_value);
  });

  // ajax sending the new grid opacity to the backend
  req = $.ajax({
    url: "/set_grid_opacity",
    type: "POST",
    data: { grid_opacity: new_value },
  });
}

// grid view: increase the opacity of the GT masks
function add_opacity_grid() {
  var value = $("#value-opacity-grid").attr("value");
  var new_value = parseFloat(value) + 0.1;
  if (new_value >= 1) {
    new_value = 1;
  }
  $("#value-opacity-grid").attr("value", new_value);
  $("#value-opacity-grid").text(new_value.toFixed(1));
  $('[id^="imgEM-GT-"]').each(function () {
    $(this).css("opacity", new_value);
  });

  // ajax sending the new grid opacity to the backend
  req = $.ajax({
    url: "/set_grid_opacity",
    type: "POST",
    data: { grid_opacity: new_value },
  });
}

// toggle the GT mask in the modal view
function check_gt() {
  var checkbox = document.getElementById("check-gt");
  if (checkbox.checked == false) {
    $("#imgDetails-GT").css("display", "none");
    $("#check-em").prop("disabled", true);
  } else {
    $("#imgDetails-GT").css("display", "block");
    $("#check-em").prop("disabled", false);
  }
}

// toggle the image in the modal view
function check_em() {
  var checkbox = document.getElementById("check-em");
  if (checkbox.checked == false) {
    $("#imgDetails-GT").css("background-color", "black");
    $("#imgDetails-GT").css("opacity", "1");
    $("#check-gt").prop("disabled", true);
  } else {
    $("#imgDetails-GT").css("background-color", "transparent");
    $("#imgDetails-GT").css("opacity", "1");
    $("#check-gt").prop("disabled", false);
  }
}
