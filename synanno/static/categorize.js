import { fetchImageExistence, updateImages } from "./utils/image_loader.js";

$(document).ready(() => {
  initializeFormControls();
  setupFormControlEvents();
  setupSubmitHandlers();
  updateEmptyStateMessage();
  setupCardClickHandlers();

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

function lockInstanceFields(page, imgId) {
  $(`#customFlagButton_${page}_${imgId}`).prop('disabled', true);
  $(`#customFlagInput_${page}_${imgId}`).prop('disabled', true);
  ['falsePositive', 'badFit', 'polaritySwitch'].forEach(flag => {
    $(`#${flag}_${page}_${imgId}`).prop('disabled', true).closest('.form-check').addClass('text-muted');
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

function setupCardClickHandlers() {
  $('.card-block.image-card-btn').on('click', async function () {
    try {
      const card = $(this).closest('.card');
      const cardId = card.attr('id');
    if (!cardId) return;
    const parts = cardId.split('_');
const page = parts[2];
const dataId = parts[3];
      const currentLabel = $(this).hasClass('correct') ? 'Correct' : $(this).hasClass('incorrect') ? 'Incorrect' : 'Unsure';

      const response = await $.post('/update-status', { page, data_id: dataId, label: currentLabel });

      if (response.result === 'success') {
        $(this).removeClass('correct incorrect unsure').addClass(response.label.toLowerCase());
        card.toggleClass('compact', response.label === 'Correct');

        const formContainer = card.find('.card-block.form-container');
        if (response.label === 'Correct') {
          formContainer.html('<div class="text-success text-center py-2"><i class="fas fa-check-circle"></i> Instance Marked as Correct!</div>');
        } else {
          formContainer.html(generateFormHtml(page, dataId));
          setupFormControlEvents();
        }
      }
    } catch (error) {
      console.error('Error updating status:', error);
    }
  });

  $('.card .card-block.form-container').on('click', e => e.stopPropagation());
}

function generateFormHtml(page, imgId) {
  return `
    <div class="form">
      ${['falsePositive', 'badFit', 'polaritySwitch'].map(flag => `
        <div class="form-check m-2">
          <input class="form-check-input" type="radio" name="select_${page}_${imgId}" id="${flag}_${page}_${imgId}" />
          <label class="form-check-label" for="${flag}_${page}_${imgId}">${flag.replace(/([A-Z])/g, ' $1')}</label>
        </div>
      `).join('')}
      <div class="input-group" id="customFlag_${page}_${imgId}">
        <div class="input-group-text">
          <input type="radio" name="select_${page}_${imgId}" id="customFlagButton_${page}_${imgId}" />
        </div>
        <input type="text" class="form-control" id="customFlagInput_${page}_${imgId}" placeholder="Custom Flag" disabled />
      </div>
    </div>`;
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
