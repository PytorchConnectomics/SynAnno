$(document).ready(() => {
  // Initialize form controls based on existing data
  initializeFormControls();

  // Set up form control interactions
  setupFormControlEvents();

  // Set up submit button handlers
  setupSubmitHandlers();

  // Show message in case no faulty instances were selected/marked
  updateEmptyStateMessage();

  // Add click event handler to image cards to toggle correct/incorrect status
  $('.card').on('click', async function() {
    try {
      const id = $(this).attr('id');
      const parts = id.split('_');
      const page = parts[2];
      const dataId = parts[3];
      const cardBlock = $(this).find('.card-block.image-card-btn');
      const currentLabel = cardBlock.hasClass('correct') ? 'Correct' :
                           cardBlock.hasClass('incorrect') ? 'Incorrect' : 'Unsure';

      // Send AJAX request to update status
      const response = await $.ajax({
        url: '/update-status',
        type: 'POST',
        data: {
          page,
          data_id: dataId,
          label: currentLabel
        }
      });

      // Update the UI based on the response
      if (response.result === 'success') {
        cardBlock.removeClass('correct incorrect unsure');

        if (response.label === 'Correct') {
          cardBlock.addClass('correct');
          $(this).addClass('compact');
          // Force form container to be hidden
          $(this).find('.card-block.form-container').css({
            display: 'none',
            height: 0,
            margin: 0,
            padding: 0,
            overflow: 'hidden'
          });
        } else {
          cardBlock.addClass(response.label.toLowerCase());
          $(this).removeClass('compact');
          // Show the form container
          $(this).find('.card-block.form-container').css({
            display: 'block',
            height: '',
            margin: '',
            padding: '',
            overflow: ''
          });
        }
      }
    } catch (error) {
      console.error('Error updating status:', error);
    }
  });
});

/**
 * Initialize form controls based on existing data
 */
function initializeFormControls() {
  // Check and complete the custom error fields based on the provided json
  $('[id^="customFlag_"]').each(function() {
    const id = $(this).attr('id');
    if ($(this).hasClass('checked')) {
      const parts = id.split('_');
      const customFlagId = `#customFlagButton_${parts[1]}_${parts[2]}`;
      const customFlagInputId = `#customFlagInput_${parts[1]}_${parts[2]}`;
      $(customFlagId).prop('checked', true);
      $(customFlagInputId).prop('disabled', false);
    }
  });

  // Check "bad fit" fields based on the provided json
  $('[id^="badFit_"]').each(function() {
    if ($(this).hasClass('checked')) {
      $(this).prop('checked', true);
    }
  });

  // Check "polarity switch" fields based on the provided json
  $('[id^="polaritySwitch_"]').each(function() {
    if ($(this).hasClass('checked')) {
      $(this).prop('checked', true);
    }
  });

  // Check "false positive" fields based on the provided json
  $('[id^="falsePositive_"]').each(function() {
    if ($(this).hasClass('checked')) {
      $(this).prop('checked', true);
    }
  });

  // Hide form containers for correct cards on page load
  $('.card-block.image-card-btn.correct').each(function() {
    const card = $(this).closest('.card');
    card.addClass('compact');
    card.find('.card-block.form-container').css({
      display: 'none',
      height: 0,
      margin: 0,
      padding: 0,
      overflow: 'hidden'
    });
  });
}

/**
 * Setup event handlers for form controls
 */
function setupFormControlEvents() {
  // Ensure that the text field is only enabled if the button is selected
  $('[id^="customFlagButton_"]').change(function() {
    const [_, page, imgId] = $(this).attr('id').split('_');
    const customFlagId = `#customFlagInput_${page}_${imgId}`;
    $(customFlagId).prop('disabled', !$(this).is(':checked'));
  });

  $('[id^="falsePositive_"]').change(function() {
    const [_, page, imgId] = $(this).attr('id').split('_');
    const customFlagId = `#customFlagInput_${page}_${imgId}`;
    $(customFlagId).prop('disabled', true);
  });

  $('[id^="badFit_"]').change(function() {
    const [_, page, imgId] = $(this).attr('id').split('_');
    const customFlagId = `#customFlagInput_${page}_${imgId}`;
    $(customFlagId).prop('disabled', true);
  });

  $('[id^="polaritySwitch_"]').change(function() {
    const [_, page, imgId] = $(this).attr('id').split('_');
    const customFlagId = `#customFlagInput_${page}_${imgId}`;
    $(customFlagId).prop('disabled', true);
  });
}

/**
 * Setup handlers for submit buttons
 */
function setupSubmitHandlers() {
  // Check if one of the flags was set to false positive on click of the submit button
  $('#submit_button').click(function() {
    let fpSet = false;
    $('[id^="id_error_"]').each(function() {
      if ($('[id^="falsePositive_"]', $(this)).is(':checked')) {
        fpSet = true;
        $('#categorizeModalFPSave').modal('show');
        return false; // Break the each loop
      }
    });

    if (!fpSet) {
      // Show loading screen and process the data
      $('#loading-bar').css('display', 'flex');
      submitData(false);
    }
  });

  // Delete the false positives from the JSON
  $('#dl_fn_yes').click(async function() {
    try {
      // Hide modal and show loading screen
      $('#categorizeModalFPSave').modal('hide');
      $('#loading-bar').css('display', 'flex');
      await submitData(true);
    } catch (error) {
      console.error('Error processing with delete FPs:', error);
    }
  });

  // Keep the false positives in the JSON
  $('#dl_fn_no').click(async function() {
    try {
      // Hide modal and show loading screen
      $('#categorizeModalFPSave').modal('hide');
      $('#loading-bar').css('display', 'flex');
      await submitData(false);
    } catch (error) {
      console.error('Error processing without delete FPs:', error);
    }
  });
}

/**
 * Update the visibility of the empty state message
 */
function updateEmptyStateMessage() {
  if ($('.card').length > 0) {
    $('.bg-secondary').addClass('d-none');
  } else {
    $('.bg-secondary').removeClass('d-none');
  }
}

/**
 * Process error flags and submit to the backend
 * @param {boolean} deleteFps - Whether to delete false positives
 * @returns {Promise} Promise object representing the completion of the submission
 */
async function submitData(deleteFps) {
  try {
    const flags = await collectFlagsFromNonCorrectCards();

    // Update the backend
    await $.ajax({
      url: '/pass_flags',
      type: 'POST',
      contentType: 'application/json',
      dataType: 'json',
      data: JSON.stringify({ flags, delete_fps: deleteFps }),
    });

    window.location.href = '/export_annotate';
  } catch (error) {
    let errorMessage;
    try {
      errorMessage = JSON.parse(error.responseText).Message;
    } catch (e) {
      errorMessage = 'An unknown error occurred';
    }
    alert(errorMessage);
    console.error('Error submitting data:', error);
  }
}

/**
 * Collect flags from cards that are not marked as correct
 * @returns {Promise<Array>} Promise that resolves to an array of flag objects
 */
async function collectFlagsFromNonCorrectCards() {
  return new Promise((resolve) => {
    const flagsArray = [];

    // Only process cards that don't have correct status
    const nonCorrectCards = $('[id^="id_error_"]').filter(function() {
      return !$(this).find('.card-block.image-card-btn').hasClass('correct');
    });

    const nrElements = nonCorrectCards.length;

    // Resolve in case no samples were marked as wrong or unsure
    if (nrElements === 0) {
      resolve(flagsArray);
      return;
    }

    // Update the error ids of the faulty instances
    nonCorrectCards.each(function(index) {
      const [page, imgId] = $(this)
        .attr('id')
        .replace(/id_error_/, '')
        .split('_');

      if ($('[id^="falsePositive_"]', $(this)).is(':checked')) {
        flagsArray.push({ page, idx: imgId, flag: 'falsePositive' });
      } else if ($('[id^="badFit_"]', $(this)).is(':checked')) {
        flagsArray.push({ page, idx: imgId, flag: 'badFit' });
      } else if ($('[id^="polaritySwitch_"]', $(this)).is(':checked')) {
        flagsArray.push({ page, idx: imgId, flag: 'polaritySwitch' });
      } else if ($('[id^="customFlagButton_"]', $(this)).is(':checked')) {
        flagsArray.push({
          page,
          idx: imgId,
          flag: $('[id^="customFlagInput_"]', $(this)).val(),
        });
      } else {
        flagsArray.push({ page, idx: imgId, flag: 'None' });
      }

      if (index === nrElements - 1) {
        resolve(flagsArray);
      }
    });

    // If there are no non-correct cards to process
    if (nonCorrectCards.length === 0) {
      resolve(flagsArray);
    }
  });
}
