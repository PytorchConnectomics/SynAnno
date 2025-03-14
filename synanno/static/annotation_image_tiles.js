$(document).ready(() => {
  const neuronReady = $("script[src*='annotation_image_tiles.js']").data("neuron-ready") === true;
  const fnPage = $("script[src*='annotation_image_tiles.js']").data("fn-page") === true;
  const $sharkContainerAnnotate = $("#shark_container_minimap");

  // Trigger updateSynapseColors on page navigation for all instances on the page
  $(".nav-anno").on("click", () => {
    updateSynapseColors();
  });

  // Update the instance specific values
  $(".image-card-btn").on("click", function () {
    const dataId = $(this).attr("data_id");
    const page = $(this).attr("page");
    const label = $(this).attr("label");

    // Update the label in the backend
    const reqLabel = $.ajax({
      url: "/update-card",
      type: "POST",
      data: { data_id: dataId, page: page, label: label },
    });

    // Update the label in the frontend
    reqLabel.done((data) => {
      updateLabelClasses(dataId, label);

      if (neuronReady) {
        const newLabel = $("#id-a-" + dataId).attr("label");
        updateSynapseColor(dataId, newLabel);
        window.setupWindowResizeHandler($sharkContainerAnnotate[0]);
      }
    });
  });

  let isScrollingLocked = false; // Prevents rapid scrolling
  let scrollDelta = 0; // Accumulate scroll movement
  const SCROLL_THRESHOLD = 50; // Adjust this value for sensitivity (higher = less sensitive)

  $(".annotate-item").on("wheel", async function (event) {
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

    const $card = $(this).find(".image-card-btn"); // The card representing the instance
    const dataId = $card.attr("data_id"); // Instance identifier

    const $imgSource = $("#imgSource-" + dataId);
    const $imgTarget = $("#imgTarget-" + dataId);

    const currentSlice = parseInt($imgSource.data("current-slice")); // Current slice

    // Determine scroll direction
    const newSlice = currentSlice + (event.originalEvent.deltaY > 0 ? 1 : -1);

    try {
      const response = await fetchImageExistence(dataId, newSlice, fnPage);

      if (response) { // Only execute if the slice exists
        await updateImages(dataId, newSlice, fnPage, $imgSource, $imgTarget);
      }
    } catch (error) {
      console.error("Error loading images:", error);
    }

    isScrollingLocked = false;
  });

  // Grid view: decrease the opacity of the GT masks
  window.dec_opacity_grid = function () {
    updateGridOpacity(-0.1);
  };

  // Grid view: increase the opacity of the GT masks
  window.add_opacity_grid = function () {
    updateGridOpacity(0.1);
  };
});

function updateSynapseColors() {
  if ($("script[src*='viewer.js']").data("neuron-ready") === true) {
    $(".image-card-btn").each(function () {
      const dataId = $(this).attr("data_id");
      const label = $(this).attr("label");
      updateSynapseColor(dataId, label);
    });
    // Save to colors to storage
    sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));
  }
}

function updateLabelClasses(dataId, label) {
  if (label === "Unsure") {
    $("#id" + dataId).removeClass("unsure").addClass("correct");
    $("#id-a-" + dataId).attr("label", "Correct");
  } else if (label === "Incorrect") {
    $("#id" + dataId).removeClass("incorrect").addClass("unsure");
    $("#id-a-" + dataId).attr("label", "Unsure");
  } else if (label === "Correct") {
    $("#id" + dataId).removeClass("correct").addClass("incorrect");
    $("#id-a-" + dataId).attr("label", "Incorrect");
  }
}

function updateSynapseColor(dataId, label) {
  if (label === "Correct") {
    window.updateSynapse(dataId, null, new THREE.Color(0x00ff00), null, true);
    window.synapseColors[dataId] = "green";
  } else if (label === "Unsure") {
    window.updateSynapse(dataId, null, new THREE.Color(0xffff00), null, true);
    window.synapseColors[dataId] = "yellow";
  } else if (label === "Incorrect") {
    window.updateSynapse(dataId, null, new THREE.Color(0xff0000), null, true);
    window.synapseColors[dataId] = "red";
  }
}

async function fetchImageExistence(dataId, newSlice, fnPage) {
  if (fnPage) {
    return await $.ajax({
      url: `/source_img_exists/${dataId}/${newSlice}`,
      type: "GET",
    });
  } else {
    return await $.ajax({
      url: `/source_and_target_exist/${dataId}/${newSlice}`,
      type: "GET",
    });
  }
}

async function updateImages(dataId, newSlice, fnPage, $imgSource, $imgTarget) {
  const newSourceImg = new Image();
  newSourceImg.src = `/get_source_image/${dataId}/${newSlice}`;

  if (fnPage) {
    await new Promise((resolve) => (newSourceImg.onload = resolve));
    $imgSource.attr("src", newSourceImg.src);
    $imgSource.data("current-slice", newSlice);
  } else {
    const newTargetImg = new Image();
    newTargetImg.src = `/get_target_image/${dataId}/${newSlice}`;

    await Promise.all([
      new Promise((resolve) => (newSourceImg.onload = resolve)),
      new Promise((resolve) => (newTargetImg.onload = resolve)),
    ]);

    $imgSource.attr("src", newSourceImg.src);
    $imgSource.data("current-slice", newSlice);
    $imgTarget.attr("src", newTargetImg.src);
    $imgTarget.data("current-slice", newSlice);
  }
}

function updateGridOpacity(delta) {
  const $valueOpacityGrid = $("#value-opacity-grid");
  let value = parseFloat($valueOpacityGrid.attr("value"));
  let newValue = value + delta;
  newValue = Math.max(0, Math.min(newValue, 1));
  $valueOpacityGrid.attr("value", newValue);
  $valueOpacityGrid.text(newValue.toFixed(1));

  $('[id^="imgTarget-"]').each(function () {
    $(this).css("opacity", newValue);
  });

  // Ajax sending the new grid opacity to the backend
  $.ajax({
    url: "/set_grid_opacity",
    type: "POST",
    data: { grid_opacity: newValue },
  });
}
