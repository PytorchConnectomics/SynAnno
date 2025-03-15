$(document).ready(() => {
  const neuronReady = $("script[src*='annotation_image_tiles.js']").data("neuron-ready") === true;
  const fnPage = $("script[src*='annotation_image_tiles.js']").data("fn-page") === true;
  const $sharkContainerAnnotate = $("#shark_container_minimap");

  // Delegated event binding for page navigation
  $(document).on("click", ".nav-anno", updateSynapseColors);

  // Delegated event binding for image card updates
  $(document).on("click", ".image-card-btn", async function () {
    const dataId = $(this).attr("data_id");
    const page = $(this).attr("page");
    const label = $(this).attr("label");

    try {
      const data = await $.post("/update-card", { data_id: dataId, page, label });
      updateLabelClasses(dataId, label);

      if (neuronReady) {
        const newLabel = $(`#id-a-${dataId}`).attr("label");
        updateSynapseColor(dataId, newLabel);
        window.setupWindowResizeHandler($sharkContainerAnnotate[0]);
      }
    } catch (error) {
      console.error("Error updating label:", error);
    }
  });

  let isScrollingLocked = false;
  let scrollDelta = 0;
  const SCROLL_THRESHOLD = 50;

  $(".annotate-item").on("wheel", async function (event) {
    const $this = $(this);

    // Prevent the main page from scrolling
    event.preventDefault();

    if (isScrollingLocked) return;

    scrollDelta += event.originalEvent.deltaY;
    if (Math.abs(scrollDelta) < SCROLL_THRESHOLD) return;

    scrollDelta = 0;
    isScrollingLocked = true;

    const $card = $this.find(".image-card-btn");
    const dataId = $card.attr("data_id");
    const $imgSource = $(`#imgSource-${dataId}`);
    const $imgTarget = $(`#imgTarget-${dataId}`);
    const currentSlice = parseInt($imgSource.attr("data-current-slice"), 10);
    const newSlice = currentSlice + (event.originalEvent.deltaY > 0 ? 1 : -1);

    try {
      const response = await fetchImageExistence(dataId, newSlice, fnPage);
      if (response) await updateImages(dataId, newSlice, fnPage, $imgSource, $imgTarget);
    } catch (error) {
      console.error("Error loading images:", error);
    } finally {
      isScrollingLocked = false;
    }
  });

  // Grid opacity controls
  const gridOpacityController = {
    adjust(delta) {
      const $valueOpacityGrid = $("#value-opacity-grid");
      let value = parseFloat($valueOpacityGrid.attr("value")) + delta;
      value = Math.max(0, Math.min(value, 1));

      $valueOpacityGrid.attr("value", value).text(value.toFixed(1));
      $('[id^="imgTarget-"]').css("opacity", value);

      $.post("/set_grid_opacity", { grid_opacity: value }).fail((error) => console.error("Failed to update opacity:", error));
    },
  };

  window.dec_opacity_grid = () => gridOpacityController.adjust(-0.1);
  window.add_opacity_grid = () => gridOpacityController.adjust(0.1);
});

function updateSynapseColors() {
  if ($("script[src*='viewer.js']").attr("data-neuron-ready") === "true") {
    $(".image-card-btn").each(function () {
      updateSynapseColor($(this).attr("data_id"), $(this).attr("label"));
    });
    sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));
  }
}

function updateLabelClasses(dataId, label) {
  const labelMappings = {
    Unsure: { remove: "unsure", add: "correct", newLabel: "Correct" },
    Incorrect: { remove: "incorrect", add: "unsure", newLabel: "Unsure" },
    Correct: { remove: "correct", add: "incorrect", newLabel: "Incorrect" },
  };

  if (labelMappings[label]) {
    const { remove, add, newLabel } = labelMappings[label];
    $(`#id${dataId}`).removeClass(remove).addClass(add);
    $(`#id-a-${dataId}`).attr("label", newLabel);
  }
}

function updateSynapseColor(dataId, label) {
  const labelColors = {
    Correct: { color: 0x00ff00, name: "green" },
    Unsure: { color: 0xffff00, name: "yellow" },
    Incorrect: { color: 0xff0000, name: "red" },
  };

  if (labelColors[label]) {
    const { color, name } = labelColors[label];
    window.updateSynapse(dataId, null, new THREE.Color(color), null, true);
    window.synapseColors[dataId] = name;
  }
}

async function fetchImageExistence(dataId, newSlice, fnPage) {
  try {
    const url = fnPage ? `/source_img_exists/${dataId}/${newSlice}` : `/source_and_target_exist/${dataId}/${newSlice}`;
    return await $.get(url);
  } catch (error) {
    console.error("Image existence check failed:", error);
    return false;
  }
}

async function updateImages(dataId, newSlice, fnPage, $imgSource, $imgTarget) {
  try {
    const newSourceImg = new Image();
    newSourceImg.src = `/get_source_image/${dataId}/${newSlice}`;

    if (fnPage) {
      await new Promise((resolve) => (newSourceImg.onload = resolve));
      $imgSource.attr("src", newSourceImg.src).attr("data-current-slice", newSlice);
    } else {
      const newTargetImg = new Image();
      newTargetImg.src = `/get_target_image/${dataId}/${newSlice}`;

      await Promise.all([
        new Promise((resolve) => (newSourceImg.onload = resolve)),
        new Promise((resolve) => (newTargetImg.onload = resolve)),
      ]);

      $imgSource.attr("src", newSourceImg.src).attr("data-current-slice", newSlice);
      $imgTarget.attr("src", newTargetImg.src).attr("data-current-slice", newSlice);
    }
  } catch (error) {
    console.error("Error updating images:", error);
  }
}
