import {enableNeuropilLayer, disableNeuropilLayer} from "./utils/ng_util.js";

$(document).ready(function () {

  // Show progressbar when submitting the data
  $("form").on("submit", function (event) {
    $("#loading-bar").css('display', 'flex');
  });

  // If data is already stored in the backend enable 'reset' button
  if ($("#resetButton").hasClass("d-inline")) {
    $(".form-control").each(function () {
      $(this).prop("disabled", true);
    });
  } else {
    $(".form-control").each(function () {
      $(this).prop("disabled", false);
    });
  }

  // If data is already stored in the backend enable 'continue' button
  if ($("#continueButton").hasClass("d-inline")) {
    $(".form-control").each(function () {
      $(this).prop("disabled", true);
    });
  } else {
    $(".form-control").each(function () {
      $(this).prop("disabled", false);
    });
  }

  function isFieldEmpty(field) {
    return !field.val() || !field.val().trim();
  }

  function areAllFieldsValid() {
    let allValid = true;
    $("[data-required='true']").each(function () {
      if (isFieldEmpty($(this))) {
        allValid = false;
        return false;
      }
    });
    return allValid;
  }

  function updateSubmitButtonState() {
    $("#processData").prop("disabled", !areAllFieldsValid())
      .toggleClass("disabled", !areAllFieldsValid());
  }

  function updateFieldColors(accordionItem, userInteraction = false) {
    accordionItem.find("[data-required='true']").each(function () {
      const field = $(this);
      field.css("background-color", userInteraction && isFieldEmpty(field) ? "#fff3cd" : "");
    });
    updateSubmitButtonState();
  }

  function updateHeaderColor(accordionItem) {
    const accordionHeader = accordionItem.find(".accordion-header .accordion-button");
    const anyFieldEmpty = accordionItem.find("[data-required='true']").toArray()
      .some(field => isFieldEmpty($(field)));
    if (accordionItem.hasClass("was-interacted")) {
      accordionHeader.css("background-color", anyFieldEmpty ? "#fff3cd" : "");
    }
  }

  // Function to run validation on page load
  function validateFormOnLoad() {
    $(".accordion-item").each(function () {
      const accordionItem = $(this);
      updateFieldColors(accordionItem, false);
      updateHeaderColor(accordionItem);
    });

    // Make sure the submit button state is updated
    updateSubmitButtonState();
  }

  $(".accordion-item").each(function () {
    const accordionItem = $(this);

    accordionItem.on("shown.bs.collapse", function () {
      accordionItem.addClass("was-interacted");
      updateFieldColors(accordionItem, true);
      accordionItem.find(".accordion-header .accordion-button").css("background-color", "");
    });

    accordionItem.on("hidden.bs.collapse", function () {
      accordionItem.addClass("was-interacted");
      updateHeaderColor(accordionItem);
    });

    accordionItem.find("[data-required='true']").on("input change", function () {
      updateFieldColors(accordionItem, true);
    });
  });

  // Ensure all required fields trigger validation
  $("[data-required='true']").on("input change", function() {
    updateSubmitButtonState();
  });

  // Ensure volume form fields trigger validation
  $("#volume-form input").on("input change", function() {
    updateSubmitButtonState();
  });

  // Ensure neuron form fields trigger validation
  $("#neuron-form input").on("input change", function() {
    updateSubmitButtonState();
  });

  // Toggle between volume and neuron centric view
  $('#toggleSynapseSelection').change(function() {
    if ($(this).is(':checked')) {
      $("#volume-form").hide();
      $("#neuron-form").show();
      $("#view_style").val("neuron");

      // Enable neuron selection
      if ($("#materialization_url").val().trim()) {
        $("#openNeuronModalBtn").removeAttr("disabled");
      }
    } else {
      $("#volume-form").show();
      $("#neuron-form").hide();
      $("#view_style").val("volume");
    }

    // Make sure validation runs after toggling
    updateSubmitButtonState();
  });

  // Make modal accessible and interactive
  $("#neuroglancerModal").on("shown.bs.modal", function () {
    $(this).removeAttr("aria-hidden");
    $(this).removeAttr('inert');
    $("#neuroglancerIframe").focus();
  });

  // Restore modal attributes when closed
  $("#neuroglancerModal").on("hidden.bs.modal", function () {
    $(this).attr("aria-hidden", "true");
    $(this).attr("inert", "true");
    $("#openNeuronModalBtn").focus();
  });

  // Run validation on page load
  validateFormOnLoad();

  // Enable the neuropil layer when the modal opens
  $("#neuroglancerModal").on("show.bs.modal", async function () {
    try {
      const response = await fetch('/launch_neuroglancer', { method: 'POST' });
      const data = await response.json();
      $("#neuroglancerIframe").attr("src", data.ng_url);
      await fetch('/enable_neuropil_layer', { method: 'POST' });
    } catch (error) {
      console.error('Error launching Neuroglancer:', error);
    }
  });

  // Disable the neuropil layer when the modal closes
  $("#neuroglancerModal").on("hidden.bs.modal", async function () {
    try {
      await fetch('/disable_neuropil_layer', { method: 'POST' });
    } catch (error) {
      console.error('Error disabling neuropil layer:', error);
    }
  });

  let debounceTimer;
  const debounceDelay = 500;

  document.getElementById('materialization_url').addEventListener('input', function() {
    clearTimeout(debounceTimer);
    const self = this;

    debounceTimer = setTimeout(async function() {
      const materializationUrl = self.value.trim();
      console.log("Materialization URL:", materializationUrl);

      const openNeuronModalBtn = document.getElementById('openNeuronModalBtn');
      openNeuronModalBtn.setAttribute('disabled', 'disabled');

      if (materializationUrl) {
        try {
          // Load materialization table
          const materializationResponse = await fetch('/load_materialization', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ materialization_url: materializationUrl })
          });

          const materializationData = await materializationResponse.json();

          if (materializationData.status === "success") {
            console.log("Materialization table loaded.");

            // Get form values
            const source_url = document.getElementById('source_url').value.trim();
            const target_url = document.getElementById('target_url').value.trim();
            const neuropil_url = document.getElementById('neuropil_url').value.trim();

            // Build query string with proper URL encoding
            const queryString = '?source_url=' + encodeURIComponent(source_url) +
                              '&target_url=' + encodeURIComponent(target_url) +
                              '&neuropil_url=' + encodeURIComponent(neuropil_url);

            // Launch Neuroglancer
            const ngResponse = await fetch('/launch_neuroglancer' + queryString, { method: 'GET' });
            const ngData = await ngResponse.json();

            if (ngData.ng_url) {
              document.getElementById('neuroglancerIframe').src = ngData.ng_url;
              console.log("Neuroglancer URL set to:", ngData.ng_url);
              openNeuronModalBtn.removeAttribute('disabled');
            } else {
              console.error("No Neuroglancer URL received:", ngData.error);
            }
          } else {
            console.error("Error loading materialization table:", materializationData.error);
          }
        } catch (error) {
          console.error("Error during fetch:", error);
        }
      }

      // Update submit button state after all this processing
      updateSubmitButtonState();
    }, debounceDelay);
  });

  let checkSelectedNeuronIDHandle;
  let initialID = null;

  // Start checking the neuron ID when the ng modal is shown
  $("#neuroglancerModal").on("shown.bs.modal", function () {
    // Pull initial coordinates
    $.ajax({
      type: 'GET',
      url: '/get_neuron_id',
      success: function (response) {
        // Start pulling the neuron ID every 500ms
        checkSelectedNeuronIDHandle = setInterval(checkNeuronID, 500);
      },
      error: function (error) {
        console.error('Error fetching initial the neuron ID:', error);
      }
    });
  });

  // Stop checking the neuron ID when the modal is hidden
  $("#neuroglancerModal").on("hidden.bs.modal", function () {
    clearInterval(checkSelectedNeuronIDHandle);
  });

  // Function to check for changes in app.cz, app.cy, app.cx
  function checkNeuronID() {
    $.ajax({
      type: 'GET',
      url: '/get_neuron_id',
      success: function (response) {
        const selected_neuron_id = response.selected_neuron_id;
        console.log('Selected Neuron ID:', selected_neuron_id);
        if (selected_neuron_id !== initialID) {
          console.log('Neuron ID changed:', selected_neuron_id);
          $("#neuron-id-open").text(parseInt(selected_neuron_id));
          initialID = selected_neuron_id;
        }
      },
      error: function (error) {
        console.error('Error fetching the neuron ID:', error);
      }
    });
  }
});
