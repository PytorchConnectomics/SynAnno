$(document).ready(function () {

  const neuronReady = $("script[src*='minimap.js']").data("neuron-ready") === true;
  const fnPage = $("script[src*='annotation.js']").data("fn-page") === true;
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

    let isScrollingLocked = false;  // Prevents rapid scrolling
    let scrollDelta = 0;            // Accumulate scroll movement
    const SCROLL_THRESHOLD = 50;    // Adjust this value for sensitivity (higher = less sensitive)
    $(".annotate-item").on("wheel",async function (event) {
    event.preventDefault(); // Prevent page scrolling

      if (isScrollingLocked) return; // Stop execution if another scroll event is already in progress

      // Accumulate the scroll movement
      scrollDelta += event.originalEvent.deltaY;

      // Only trigger a slice change when scroll exceeds the threshold
      if (Math.abs(scrollDelta) < SCROLL_THRESHOLD) {
          return; // Do nothing until enough scrolling has occurred
      }
      scrollDelta = 0; // Reset the accumulated scroll after triggering a slice change

      isScrollingLocked = true;

      let $card = $(this).find(".image-card-btn"); // The card representing the instance
      let data_id = $card.attr("data_id"); // Instance identifier

      let $imgSource = $("#imgSource-" + data_id);
      let $imgTarget = $("#imgTarget-" + data_id);

      let currentSlice = parseInt($imgSource.data("current-slice")); // Current slice

      // Determine scroll direction
      let newSlice = currentSlice + (event.originalEvent.deltaY > 0 ? 1 : -1);

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
            } else {
              newTargetImg = new Image();
              newTargetImg.src = `/get_target_image/${data_id}/${newSlice}`;

              // Wait for both images to load before updating
              await Promise.all([
                new Promise(resolve => newSourceImg.onload = resolve),
                new Promise(resolve => newTargetImg.onload = resolve)
              ]);
            }

            if (fnPage) {
              // Update the displayed images **only after both have fully loaded**
              $imgSource.attr("src", newSourceImg.src);
              $imgSource.data("current-slice", newSlice);
            }
            else {
              $imgSource.attr("src", newSourceImg.src);
              $imgSource.data("current-slice", newSlice);
              $imgTarget.attr("src", newTargetImg.src);
              $imgTarget.data("current-slice", newSlice);
            }
        }
    } catch (error) {
        console.error("Error loading images:", error);
    }

    isScrollingLocked = false;
  });

  // Trigger updateSynapseColors on page navigation for all instances on the page
  $(".nav-anno").on("click", function () {
    updateSynapseColors();
  });


// grid view: decrease the opacity of the GT masks
window.dec_opacity_grid =  function dec_opacity_grid() {
  var value = $("#value-opacity-grid").attr("value");
  var new_value = value - 0.1;
  if (new_value < 0) {
    new_value = 0;
  }
  $("#value-opacity-grid").attr("value", new_value);
  $("#value-opacity-grid").text(new_value.toFixed(1));

  $('[id^="imgTarget-"]').each(function () {
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
  $('[id^="imgTarget-"]').each(function () {
    $(this).css("opacity", new_value);
  });

  // ajax sending the new grid opacity to the backend
  let req_dasc_opacity = $.ajax({
    url: "/set_grid_opacity",
    type: "POST",
    data: { grid_opacity: new_value },
  });
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
