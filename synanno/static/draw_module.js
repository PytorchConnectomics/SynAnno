$(document).ready(function () {
  // path where to save the custom masks
  const base_mask_path = "/static/Images/Mask/";

  $('[id^="drawButton-"]').click(async function () {
    var [page, data_id, label] = $($(this))
      .attr("id")
      .replace(/drawButton-/, "")
      .split("-");

    // we are currently in drawing mode
    var mode = "draw";

    // we require the information about the whole instance
    var load = "full";

    req_data = $.ajax({
      url: "/get_instance",
      type: "POST",
      data: {
        mode: mode,
        load: load,
        data_id: data_id,
        page: page,
        base_mask_path: base_mask_path,
      },
    });

    // set the base image to the center slice
    await req_data.done(function (data) {
      data_json = JSON.parse(data.data);
      $("#imgDetails-EM").addClass(label.toLowerCase());
      $("#imgDetails-EM").attr(
        "src",
        staticBaseUrl + data_json.EM + "/" + data_json.Middle_Slice + ".png",
      );

      // curve mask
      if (data.custom_mask_path_curve === null) {
        $("#imgDetails-EM-GT-curve").addClass("d-none");
      } else {
        $(new Image())
          .attr("src", data.custom_mask_path_curve + "?" + Date.now())
          .load(function () {
            $("#imgDetails-EM-GT-curve").attr("src", this.src);
          });
        $("#imgDetails-EM-GT-curve").removeClass("d-none");
      }

      // pre-synaptic coordinate mask
      if (data.custom_mask_path_pre === null) {
        $("#imgDetails-EM-GT-circlePre").addClass("d-none");
      } else {
        $(new Image())
          .attr("src", data.custom_mask_path_pre + "?" + Date.now())
          .load(function () {
            $("#imgDetails-EM-GT-circlePre").attr("src", this.src);
          });
        $("#imgDetails-EM-GT-circlePre").removeClass("d-none");
      }

      // post-synaptic coordinate mask
      if (data.custom_mask_path_post === null) {
        $("#imgDetails-EM-GT-circlePost").addClass("d-none");
      } else {
        $(new Image())
          .attr("src", data.custom_mask_path_post + "?" + Date.now())
          .load(function () {
            $("#imgDetails-EM-GT-circlePost").attr("src", this.src);
          });
        $("#imgDetails-EM-GT-circlePost").removeClass("d-none");
      }

      // update the range slider
      $("#rangeSlices").attr("min", data.range_min);
      $("#rangeSlices").attr("max", data.range_min + data.slices_len - 1);
      $("#rangeSlices").val(data.halflen);
      $("#rangeSlices").attr("data_id", data_id);
      $("#rangeSlices").attr("page", page);

      $("#minSlice").html(0);
      $("#maxSlice").html(data.slices_len - 1);

      cz0 = data_json.cz0;
      cy0 = data_json.cy0;
      cx0 = data_json.cx0;

      $("#rangeSlices").data("viewed_instance_slice", data_json.Middle_Slice);
    });

    // retrieve the updated NG link
    req_ng = $.ajax({
      url: "/neuro",
      type: "POST",
      // we set mode to 'annotate' as we would like to set the focus on the particular instance
      data: { cz0: cz0, cy0: cy0, cx0: cx0, mode: "annotate" },
    });

    req_ng.done(function (data) {
      ng_link = data.ng_link;
      $("#ng-iframe-draw").attr("src", ng_link);
    });
  });

  // with in the modal view retrieve the instance specific data
  // to switch between the slices
  $("#rangeSlices").on("input", function () {
    // set the visibility of the canvases to hidden
    // this will trigger the deletion of the canvas
    $("canvas.curveCanvas").addClass("d-none");
    $("canvas.circleCanvasPre").addClass("d-none");
    $("canvas.circleCanvasPost").addClass("d-none");

    // reset all buttons
    $("#canvasButtonPreCRD").text("Pre-Synaptic CRD");
    $("#canvasButtonPostCRD").text("Post-Synaptic CRD");
    $("#canvasButtonPreCRD").prop("disabled", false);
    $("#canvasButtonPostCRD").prop("disabled", false);

    // reset the draw mask button
    $("#canvasButtonDrawMask").text("Draw Mask");
    $("#canvasButtonDrawMask").prop("disabled", false);

    // disable all options except the activate canvas button
    $("#canvasButtonFill").prop("disabled", true);
    $("#canvasButtonRevise").prop("disabled", true);
    $("#canvasButtonSave").prop("disabled", true);

    // get the current slice slice index
    viewed_instance_slice = $(this).val();
    // update the appropriate attribute to be used by the draw.js script
    $(this).data("viewed_instance_slice", viewed_instance_slice);

    // the instance identifiers
    var data_id = $(this).attr("data_id");
    var page = $(this).attr("page");

    // we are currently in drawing mode
    var mode = "draw";

    // we only require the path to load a single slice and the corresponding GT
    var load = "single";

    // retrieve the information from the backend
    req = $.ajax({
      url: "/get_instance",
      type: "POST",
      data: {
        mode: mode,
        load: load,
        data_id: data_id,
        page: page,
        base_mask_path: base_mask_path,
        viewed_instance_slice: viewed_instance_slice,
      },
    });

    // update the slice and GT that is depicted
    req.done(function (data) {
      data_json = JSON.parse(data.data);
      $("#imgDetails-EM").attr(
        "src",
        staticBaseUrl + data_json.EM + "/" + viewed_instance_slice + ".png",
      );

      // curve mask
      if (data.custom_mask_path_curve === null) {
        $("#imgDetails-EM-GT-curve").addClass("d-none");
      } else {
        $(new Image())
          .attr("src", data.custom_mask_path_curve + "?" + Date.now())
          .load(function () {
            $("#imgDetails-EM-GT-curve").attr("src", this.src);
          });
        $("#imgDetails-EM-GT-curve").removeClass("d-none");
      }

      // pre-synaptic coordinate mask
      if (data.custom_mask_path_pre === null) {
        $("#imgDetails-EM-GT-circlePre").addClass("d-none");
      } else {
        $(new Image())
          .attr("src", data.custom_mask_path_pre + "?" + Date.now())
          .load(function () {
            $("#imgDetails-EM-GT-circlePre").attr("src", this.src);
          });
        $("#imgDetails-EM-GT-circlePre").removeClass("d-none");
      }

      // post-synaptic coordinate mask
      if (data.custom_mask_path_post === null) {
        $("#imgDetails-EM-GT-circlePost").addClass("d-none");
      } else {
        $(new Image())
          .attr("src", data.custom_mask_path_post + "?" + Date.now())
          .load(function () {
            $("#imgDetails-EM-GT-circlePost").attr("src", this.src);
          });
        $("#imgDetails-EM-GT-circlePost").removeClass("d-none");
      }
    });
  });

  $("#add_new_instance").click(async function (e) {
    // open a new Neuroglancer view
    req_ng = $.ajax({
      url: "/neuro",
      type: "POST",
      data: { cz0: 0, cy0: 0, cx0: 0, mode: "draw" },
    });

    req_ng.done(function (data) {
      ng_link = data.ng_link;
      $("#ng-iframe-draw").attr("src", ng_link);
    });

    $("#review_bbox").show();
    $("#back_to_2d").hide();
  });

  // toggle the functionality of the NG module based on the current use-case: select slice for drawing
  $("#ng-link-draw").on("click", function () {
    $("#review_bbox").hide();
    $("#back_to_2d").show();
  });

  // ensure that the canvas is depicted when returning to the 2D view
  $("#back_to_2d").on("click", function () {
    $("canvas.curveCanvas").removeClass("d-none"); // change the visibility of the canvas
    // TODO if I check the ng before drawing any thing we will see the picture logo instead of the canvas
    // Have to also check this logic for the circle canvas
  });

  $("#review_bbox").click(async function (e) {
    // retrieve the bb information from the backend
    $.ajax({
      url: "/ng_bbox_fn",
      type: "POST",
      data: { z1: 0, z2: 0, my: 0, mx: 0 },
    }).done(function (data) {
      $("#m_x").val(data.mx);
      $("#m_y").val(data.my);

      $("#d_z1").val(data.z1);
      $("#d_z2").val(data.z2);
    });
  });

  $("#save_bbox").click(function () {
    // update the bb information with the manuel corrections and pass them to the backend
    // trigger the processing/save to the pandas df in the backend
    $.ajax({
      url: "/ng_bbox_fn_save",
      type: "POST",
      data: {
        z1: $("#d_z1").val(),
        z2: $("#d_z2").val(),
        my: $("#m_y").val(),
        mx: $("#m_x").val(),
      },
    }).done(function () {
      // hide modules
      $("#drawModalFNSave, #drawModalFN").modal("hide");

      // refresh page
      location.reload();
    });
  });
});
