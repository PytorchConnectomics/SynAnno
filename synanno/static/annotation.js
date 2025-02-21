$(document).ready(function () {

  const neuronID = $("script[src*='annotation.js']").data("neuron-id");
  const neuronReady = $("script[src*='minimap.js']").data("neuron-ready") === true;
  const $sharkContainerAnnotate = $("#shark_container_minimap");

  // show progress bar when scrolling pages
  $(".nav-anno").click(function () {
    $("#loading-bar").css('display', 'flex');
    });

  // update the instance specific values
  $(".image-card-btn").on("click", function () {
    var data_id = $(this).attr("data_id");
    var page = $(this).attr("page");
    var label = $(this).attr("label");

    // update the label in the backend
   let req_label = $.ajax({
      url: "/update-card",
      type: "POST",
      data: { data_id: data_id, page: page, label: label },
    });

    // update the label in the frontend
    req_label.done(function (data) {
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

      if (neuronReady) {
        label = $("#id-a-" + data_id).attr("label");
        if (label === "Correct") {
            window.updateSynapse(data_id, null, new THREE.Color(0x00ff00), null, true);
            window.synapseColors[data_id] = "green";
        } else if (label === "Unsure") {
            window.updateSynapse(data_id, null, new THREE.Color(0xffff00), null, true);
            window.synapseColors[data_id] = "yellow";
        } else if (label === "Incorrect") {
            window.updateSynapse(data_id, null, new THREE.Color(0xff0000), null, true);
            window.synapseColors[data_id] = "red";
        }

        window.setupWindowResizeHandler($sharkContainerAnnotate[0]);
      }
    });
  });

  // Trigger updateSynapseColors on page navigation for all instances on the page
  $(".nav-anno").on("click", function () {
    updateSynapseColors();
  });

  // link to the NG, edited when ever right clicking an instance in the grid view
  var ng_link;

  // variables for the coordinates of the focus of the view with in the NG
  var cz0;
  var cy0;
  var cx0;

  // Ensure inert is removed when showing the modal
  $('#detailsModal').on('show.bs.modal', function () {
    $(this).removeAttr('inert'); // Make modal interactive
    $('#toggle-label').focus(); // Move focus inside the modal
  });

  // Apply inert when hiding the modal
  $('#detailsModal').on('hide.bs.modal', function () {
    $(this).attr('inert', ''); // Disable interaction
    $('.image-card-btn').first().focus(); // Return focus to trigger button
  });

  // Prevent focus issues when closing the modal via backdrop click
  $('#detailsModal').on('hidden.bs.modal', function () {
    $('.image-card-btn').first().focus(); // Move focus back to trigger button
  });

  // Ensure inert is removed when showing the Neuroglancer modal
  $('#neuroModel').on('show.bs.modal', function () {
    $(this).removeAttr('inert'); // Enable interaction
    $('#ng-iframe').focus(); // Move focus inside the modal (to the iframe)
  });

  // Apply inert when hiding the Neuroglancer modal
  $('#neuroModel').on('hide.bs.modal', function () {
    $(this).attr('inert', ''); // Disable interaction
    $('#detailsModal').removeAttr('inert'); // Ensure 2D modal regains interaction if switching
  });

  // Move focus back to the button that opened the modal
  $('#neuroModel').on('hidden.bs.modal', function () {
    $('.image-card-btn').first().focus(); // Return focus to the trigger button
  });

  // Ensure `neuroModel` modal is properly toggled from `detailsModal`
  $('[data-bs-target="#neuroModel"]').on('click', function () {
    $('#detailsModal').attr('inert', ''); // Disable the 2D modal while viewing Neuroglancer
    $('#neuroModel').modal('show').removeAttr('inert');
  });

  // Handle switching back to `detailsModal`
  $('[data-bs-target="#detailsModal"]').on('click', function () {
    $('#neuroModel').attr('inert', ''); // Disable Neuroglancer modal
    $('#detailsModal').modal('show').removeAttr('inert');
  });

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

    $("#neuron-id").text(neuronID);

    // retrieve the info from the backend
    let req_data = $.ajax({
      url: "/get_instance",
      type: "POST",
      data: { mode: mode, load: load, data_id: data_id, page: page },
    });


    await req_data.done(function (data) {
      let data_json = JSON.parse(data.data);
      // enable the range slider if more than a single slice exists per instance
      if (data.slices_len > 1){
        $("#rangeSlices").removeClass("d-none");
        $("#minSlice").removeClass("d-none");
        $("#maxSlice").removeClass("d-none");
        $("#rangeSlices").attr("min", data.range_min);
        $("#rangeSlices").attr("max", data.range_min + data.slices_len - 1);
        $("#rangeSlices").val(data.halflen);
        $("#rangeSlices").attr("data_id", data_id);
        $("#rangeSlices").attr("page", page);

        $("#minSlice").html(0);
        $("#maxSlice").html(data.slices_len - 1);
      }
      else{
        $("#rangeSlices").addClass("d-none");
        $("#minSlice").addClass("d-none");
        $("#maxSlice").addClass("d-none");
      }
      // load the current slice
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

      // Open modal properly
      $('#detailsModal').modal("show").removeAttr("inert");

      cz0 = data_json.cz0;
      cy0 = data_json.cy0;
      cx0 = data_json.cx0;

    });

    // retrieve the updated NG link
    let req_ng = $.ajax({
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
    let req_slice = $.ajax({
      url: "/get_instance",
      type: "POST",
      data: { mode: mode, load: load, data_id: data_id, page: page },
    });

    // update the slice and GT that is depicted
    req_slice.done(function (data) {
      data_json = JSON.parse(data.data);
      $("#imgDetails-EM").attr("src", staticBaseUrl + data_json.EM + "/" + rangeValue + ".png");
      $("#imgDetails-GT").attr("src", staticBaseUrl + data_json.GT + "/" + rangeValue + ".png");
    });
  });


// modal view: decrease the opacity of the GT mask
window.dec_opacity =  function dec_opacity() {
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
window.add_opacity =  function add_opacity() {
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
window.dec_opacity_grid =  function dec_opacity_grid() {
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
 let req_desc_opacity = $.ajax({
    url: "/set_grid_opacity",
    type: "POST",
    data: { grid_opacity: new_value },
  });
}

// grid view: increase the opacity of the GT masks
window.add_opacity_grid = function add_opacity_grid() {
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
  let req_dasc_opacity = $.ajax({
    url: "/set_grid_opacity",
    type: "POST",
    data: { grid_opacity: new_value },
  });
}

// toggle the GT mask in the modal view
window.check_gt = function check_gt() {
  const imgDetailsGT = document.getElementById("imgDetails-GT");
  const toggleLabelButton = document.getElementById("toggle-label");

  if (imgDetailsGT.style.display === "none") {
    imgDetailsGT.style.display = "block";
    toggleLabelButton.classList.remove("btn-secondary");
    toggleLabelButton.classList.add("btn-secondary");
  } else {
    imgDetailsGT.style.display = "none";
    toggleLabelButton.classList.remove("btn-secondary");
    toggleLabelButton.classList.add("btn-secondary");
  }
}

function updateSynapseColors() {
  if ($("script[src*='viewer.js']").data("neuron-ready") === true) {
      $(".image-card-btn").each(function () {
          const data_id = $(this).attr("data_id");
          const label = $(this).attr("label");
          if (label === "Correct"){
            window.synapseColors[data_id] = "green";
          }
          else if (label === "Unsure"){
            window.synapseColors[data_id] = "yellow";
          }
          else if (label === "Incorrect"){
            window.synapseColors[data_id] = "red";
          }
        });
      // Save to colors to storage
      sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));
  }
}
});
