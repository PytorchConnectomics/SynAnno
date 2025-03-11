$(document).ready(function () {

  const neuronID = $("script[src*='annotation.js']").data("neuron-id");
  const fnPage = $("script[src*='annotation.js']").data("fn-page") === true;

  // link to the NG, edited when ever right clicking an instance in the grid view
  var ng_link;

  // variables for the coordinates of the focus of the view with in the NG
  var cz0;
  var cy0;
  var cx0;

  let data_id;
  let page;
  let currentSlice;

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

// Retrieve and set the information for the modal instance view
$(".image-card-btn").bind("contextmenu", async function (e) {
    e.preventDefault();

    // Instance identifiers
    data_id = $(this).attr("data_id");
    page = $(this).attr("page");

    $("#neuron-id").text(neuronID);

    // Retrieve instance data from backend
    let req_data = $.ajax({
        url: "/get_instance",
        type: "POST",
        data: { mode: "annotate", load: "full", data_id: data_id, page: page },
    });

    await req_data.done(function (data) {
        let data_json = JSON.parse(data.data);

        // set the initial slice to the center slice
        currentSlice = data_json.Middle_Slice;


        // Load the initial middle slice
        if (fnPage) {
           $("#imgDetails-EM")
              .attr("src", `/get_source_image/${data_id}/${currentSlice}`)
        }else{
            $("#imgDetails-EM")
                .attr("src", `/get_source_image/${data_id}/${currentSlice}`)
            $("#imgDetails-GT")
              .attr("src", `/get_target_image/${data_id}/${currentSlice}`)
        }

        // Show modal
        $("#detailsModal").modal("show").removeAttr("inert");

        cz0 = data_json.cz0;
        cy0 = data_json.cy0;
        cx0 = data_json.cx0;
    });

    // Retrieve the updated NG link
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

let isModalScrollingLocked = false; // Prevents multiple rapid scrolls
let modalScrollDelta = 0;           // Accumulate scroll movement
const MODAL_SCROLL_THRESHOLD = 65;  // Adjust for sensitivity

// Handle mouse wheel scrolling inside the modal
$("#detailsModal").on("wheel", async function (event) {

    event.preventDefault(); // Prevent page scrolling

    if (isModalScrollingLocked) return; // Stop execution if another scroll event is already in progress

    // Accumulate the scroll movement
    modalScrollDelta += event.originalEvent.deltaY;
    // Only trigger a slice change when scroll exceeds the threshold
    if (Math.abs(modalScrollDelta) < MODAL_SCROLL_THRESHOLD) {
        return; // Do nothing until enough scrolling has occurred
    }
    modalScrollDelta = 0; // Reset the accumulated scroll after triggering a slice change

    isModalScrollingLocked = true;

    let $imgTarget = $("#imgDetails-GT");
    let $imgSource = $("#imgDetails-EM");

    // Determine scroll direction
    let newSlice = currentSlice + (event.originalEvent.deltaY > 0 ? 1 : -1);

    console.log("Current slice:", currentSlice, "New slice:", newSlice);
    console.log("$imgTarget, $imgSource", $imgTarget, $imgSource);

    try {
        let response;
        if (fnPage) {
          response = await $.ajax({
            url: `/source_img_exists/${data_id}/${newSlice}`,
            type: "GET",
          });
        } else {
          response = await $.ajax({
              url: `/source_and_target_exist/${data_id}/${newSlice}`,
              type: "GET"
          });
        }

        if (response) {  // Only execute if the slice exists
            let newTargetImg;
            let newSourceImg = new Image();

            newSourceImg.src = `/get_source_image/${data_id}/${newSlice}`;

            if (fnPage) {
              await new Promise(resolve => newSourceImg.onload = resolve);
            }
            else {
              newTargetImg = new Image();

              newSourceImg.src = `/get_source_image/${data_id}/${newSlice}`;
              newTargetImg.src = `/get_target_image/${data_id}/${newSlice}`;

              // Wait for both images to load before updating
              await Promise.all([
                new Promise(resolve => newSourceImg.onload = resolve),
                new Promise(resolve => newTargetImg.onload = resolve)
              ]);
            }


            // Update the displayed images **only after both have fully loaded**
            if (fnPage) {
              $imgSource.attr("src", newSourceImg.src);
            }else{
              $imgSource.attr("src", newSourceImg.src);
              $imgTarget.attr("src", newTargetImg.src);
            }

            currentSlice = newSlice;

        }
    } catch (error) {
        console.error("Error loading images:", error);
    }

    isModalScrollingLocked = false;
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

});
