import { fetchImageExistence, updateImages } from "./utils/image_loader.js";
import { updateLabelClasses } from "./utils/label_utils.js";

$(document).ready(() => {
  const neuronReady = $("script[src*='categorize.js']").data("neuron-ready") === true;

  initializeFormControls();
  setupFormControlEvents();
  setupSubmitHandlers();
  updateEmptyStateMessage();

  // Delegated event binding for image card updates
  $(document).on("click", ".image-card-btn", async function () {

    const dataId = $(this).attr("data_id");
    const page = $(this).attr("page");
    const label = $(this).attr("label");


    const customFLagVal = $(`#customFlagInput_${page}_${dataId}`).val()

    if (customFLagVal !== "False Negative") {

      try {
        const data = await $.post("/update-card", { data_id: dataId, page, label});
        updateLabelClasses(dataId, label);

        const newLabel = $(this).attr("label");

        if (newLabel === "correct") {
          lockInstanceFields(page, dataId);
        } else {
          enableInstanceFields(page, dataId);
        }
      } catch (error) {
        console.error("Error updating label:", error);
      }
  }
  });

  let isScrollingLocked = false;
  let scrollDelta = 0;
  const SCROLL_THRESHOLD = 50;

  $(".card-body-proof-read").on("wheel", async function (event) {

    const $this = $(this);

    // Prevent the main page from scrolling
    event.preventDefault();

    if (isScrollingLocked) return;

    scrollDelta += event.originalEvent.deltaY;
    if (Math.abs(scrollDelta) < SCROLL_THRESHOLD) return;

    scrollDelta = 0;
    isScrollingLocked = true;

    const $card = $this.find(".image-card-btn");
    const page = $card.attr("page");
    const dataId = $card.attr("data_id");
    const $imgSource = $(`#imgSource-${dataId}`);
    const $imgTarget = $(`#imgTarget-${dataId}`);
    const currentSlice = parseInt($imgSource.attr("data-current-slice"), 10);
    const newSlice = currentSlice + (event.originalEvent.deltaY > 0 ? 1 : -1);

    try {
      const customFlagText = $(`#customFlagInput_${page}_${dataId}`).val();
      const response = await fetchImageExistence(dataId, newSlice, customFlagText==="False Negative");
      if (response) await updateImages(dataId, newSlice, customFlagText==="False Negative", $imgSource, $imgTarget);
    } catch (error) {
      console.error("Error loading images:", error);
    } finally {
      isScrollingLocked = false;
    }
  });
});


// deselect and disable all instance fields for a given instance
function lockInstanceFields(page, imgId) {
  $(`#customFlagButton_${page}_${imgId}`).prop('disabled', true);
  $(`#customFlagInput_${page}_${imgId}`).prop('disabled', true);
  ['falsePositive', 'badFit', 'polaritySwitch'].forEach(flag => {
    $(`#${flag}_${page}_${imgId}`).prop('disabled', true).closest('.form-check').addClass('text-muted');
  });
}

// enable all instance fields for a given instance
function enableInstanceFields(page, imgId) {
  $(`#customFlagButton_${page}_${imgId}`).prop('disabled', false);
  ['falsePositive', 'badFit', 'polaritySwitch'].forEach(flag => {
    $(`#${flag}_${page}_${imgId}`).prop('disabled', false).closest('.form-check').removeClass('text-muted');
  });
}

function initializeFormControls() {
  $('[id^="customFlag_"]').each(function () {
    const id = $(this).attr('id');
    if ($(this).hasClass('checked')) {
      const parts = id.split('_');
      const page = parts[1];
      const imgId = parts[2];
      const customFlagText = $(`#customFlagInput_${page}_${imgId}`).val();
      $(`#customFlagButton_${page}_${imgId}`).prop('checked', true);
      $(`#customFlagInput_${page}_${imgId}`).prop('disabled', false);

      if (customFlagText === "False Negative") {
        lockInstanceFields(page, imgId);
      }
    }
  });

  ['badFit', 'polaritySwitch', 'falsePositive'].forEach(flag => {
    $(`[id^="${flag}_"]`).each(function () {
      if ($(this).hasClass('checked')) {
        $(this).prop('checked', true);
      }
    });
  });
}

function setupFormControlEvents() {
  $('[id^="customFlagButton_"]').change(function () {
    const idParts = $(this).attr('id').split('_');
    const page = idParts[1];
    const imgId = idParts[2];
    $(`#customFlagInput_${page}_${imgId}`).prop('disabled', !$(this).is(':checked'));
  });

  ['falsePositive', 'badFit', 'polaritySwitch'].forEach(flag => {
    $(`[id^="${flag}_"]`).change(function () {
      const [_, page, imgId] = $(this).attr('id').split('_');
      $(`#customFlagInput_${page}_${imgId}`).prop('disabled', true);
    });
  });
}

function setupSubmitHandlers() {
  $('#submit_button').click(() => {
    let fpSet = $('[id^="falsePositive_"]').is(':checked');
    if (fpSet) {
      $('#categorizeModalFPSave').modal('show');
    } else {
      $('#loading-bar').css('display', 'flex');
      submitData(false);
    }
  });

  ['dl_fn_yes', 'dl_fn_no'].forEach(id => {
    $(`#${id}`).click(async function () {
      $('#categorizeModalFPSave').modal('hide');
      $('#loading-bar').css('display', 'flex');
      await submitData(id === 'dl_fn_yes');
    });
  });
}

function updateEmptyStateMessage() {
  $('.bg-secondary').toggleClass('d-none', $('.card').length > 0);
}

async function submitData(deleteFps) {
  try {
    const flags = await collectFlagsFromNonCorrectCards();
    await $.ajax({
      url: '/pass_flags',
      type: 'POST',
      contentType: 'application/json',
      dataType: 'json',
      data: JSON.stringify({ flags, delete_fps: deleteFps }),
    });
    window.location.href = '/export_annotate';
  } catch (error) {
    alert(error.responseText ? JSON.parse(error.responseText).Message : 'An unknown error occurred');
    console.error('Error submitting data:', error);
  }
}

async function collectFlagsFromNonCorrectCards() {
  return new Promise(resolve => {
    const flagsArray = [];
    const nonCorrectCards = $('[id^="id_error_"]').filter((_, card) => !$(card).find('.card-block.image-card-btn').hasClass('correct'));

    if (!nonCorrectCards.length) return resolve(flagsArray);

    nonCorrectCards.each((_, card) => {
      const [page, imgId] = $(card).attr('id').replace(/id_error_/, '').split('_');
      const flag = ['falsePositive', 'badFit', 'polaritySwitch', 'customFlagButton'].find(f => $(card).find(`[id^="${f}_"]`).is(':checked'));
      const flagValue = flag === 'customFlagButton' ? $(card).find('[id^="customFlagInput_"]').val() : flag;
      flagsArray.push({ page, idx: imgId, flag: flagValue || 'None' });
    });

    resolve(flagsArray);
  });
}
