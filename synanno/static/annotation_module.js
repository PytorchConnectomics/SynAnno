$(document).ready(function () {
  const neuronID = $("script[src*='annotation_module.js']").data("neuron-id");

  let ngLink, cz0, cy0, cx0, dataId, page, currentSlice, dataJson; // Define dataJson in the outer scope

  // Cache frequently used elements
  const $detailsModal = $('#detailsModal');
  const $neuroModel = $('#neuroModel');
  const $imageCardBtns = $('.image-card-btn');
  const $ngIframe = $('#ng-iframe');
  const $imgSource = $('#imgDetails-EM');
  const $imgTarget = $('#imgDetails-GT');
  const $valueOpacity = $('#value-opacity');
  const $toggleLabel = $('#toggle-label');

  // Handle modal accessibility
  function toggleInert(modal, enable) {
    modal.attr('inert', enable ? '' : null);
  }

  function focusFirstButton() {
    $imageCardBtns.first().focus();
  }

  $detailsModal.on({
    'show.bs.modal': function () {
      toggleInert($(this), false);
      $toggleLabel.focus();
    },
    'hide.bs.modal': function () {
      toggleInert($(this), true);
    },
    'hidden.bs.modal': focusFirstButton
  });

  $neuroModel.on({
    'show.bs.modal': function () {
      toggleInert($(this), false);
      $ngIframe.focus();
    },
    'hide.bs.modal': function () {
      toggleInert($(this), true);
      toggleInert($detailsModal, false);
    },
    'hidden.bs.modal': focusFirstButton
  });

  $('[data-bs-target="#neuroModel"]').on('click', function () {
    $('#synapse-id-annotation').text(dataId);
    toggleInert($detailsModal, true);
    $neuroModel.modal('show');
  });

  $('[data-bs-target="#detailsModal"]').on('click', function () {
    toggleInert($neuroModel, true);
    $detailsModal.modal('show');
  });

  async function fetchInstanceData() {
    try {
      const response = await $.post("/get_instance", {
        mode: "annotate", load: "full", data_id: dataId, page: page
      });
      dataJson = JSON.parse(response.data); // Assign dataJson here
      currentSlice = dataJson.Middle_Slice;
      cz0 = dataJson.cz0;
      cy0 = dataJson.cy0;
      cx0 = dataJson.cx0;

      $imgSource.attr("src", `/get_source_image/${dataId}/${currentSlice}`);
      if (dataJson.Error_Description === "False Negative") {
        $imgTarget.hide();
      }else{
        $imgTarget.show();
        $imgTarget.attr("src", `/get_target_image/${dataId}/${currentSlice}`);
      }

      $detailsModal.modal("show");
    } catch (error) {
      console.error("Error fetching instance data:", error);
    }
  }

  async function fetchNeuroglancerLink() {
    try {
      const response = await $.post("/neuro", {
        cz0, cy0, cx0, mode: "annotate"
      });
      ngLink = response.ng_link;
    } catch (error) {
      console.error("Error fetching NG link:", error);
    }
  }

  $imageCardBtns.on("contextmenu", async function (e) {
    e.preventDefault();
    dataId = $(this).attr("data_id");
    page = $(this).attr("page");
    $("#neuron-id").text(neuronID);

    await fetchInstanceData();
    await fetchNeuroglancerLink();
  });

  $("#ng-link").on("click", function () {
    if (ngLink) {
      $ngIframe.attr("src", ngLink);
    }
  });

  let isModalScrollingLocked = false;
  let modalScrollDelta = 0;
  const MODAL_SCROLL_THRESHOLD = 65;

  $detailsModal.on("wheel", async function (event) {
    event.preventDefault();
    if (isModalScrollingLocked) return;
    modalScrollDelta += event.originalEvent.deltaY;
    if (Math.abs(modalScrollDelta) < MODAL_SCROLL_THRESHOLD) return;
    modalScrollDelta = 0;
    isModalScrollingLocked = true;

    const newSlice = currentSlice + (event.originalEvent.deltaY > 0 ? 1 : -1);

    // Restrict scrolling beyond available slices
    if (newSlice < dataJson.Min_Slice || newSlice > dataJson.Max_Slice) {
      isModalScrollingLocked = false;
      return;
    }

    try {
      const exists = await $.get(dataJson.Error_Description === "False Negative" ?
        `/source_img_exists/${dataId}/${newSlice}` :
        `/source_and_target_exist/${dataId}/${newSlice}`);

      if (exists) {
        const newSourceImg = new Image();
        newSourceImg.src = `/get_source_image/${dataId}/${newSlice}`;
        if (dataJson.Error_Description === "False Negative") {
          await newSourceImg.decode();
        } else {
          const newTargetImg = new Image();
          newTargetImg.src = `/get_target_image/${dataId}/${newSlice}`;
          await Promise.all([newSourceImg.decode(), newTargetImg.decode()]);
          $imgTarget.attr("src", newTargetImg.src);
        }
        $imgSource.attr("src", newSourceImg.src);
        currentSlice = newSlice;
      }
    } catch (error) {
      console.error("Error loading images:", error);
    }
    isModalScrollingLocked = false;
  });

  window.dec_opacity = function () {
    let newValue = Math.max(parseFloat($valueOpacity.attr("value")) - 0.1, 0);
    $valueOpacity.attr("value", newValue).text(newValue.toFixed(1));
    $imgTarget.css("opacity", newValue);
  };

  window.add_opacity = function () {
    let newValue = Math.min(parseFloat($valueOpacity.attr("value")) + 0.1, 1);
    $valueOpacity.attr("value", newValue).text(newValue.toFixed(1));
    $imgTarget.css("opacity", newValue);
  };

  window.check_gt = function () {
    $imgTarget.toggle();
    $toggleLabel.toggleClass("btn-secondary");
  };
});
