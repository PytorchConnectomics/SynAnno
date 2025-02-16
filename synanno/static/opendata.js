import {enableNeuropilLayer, disableNeuropilLayer} from "./utils/ng_util.js";

$(document).ready(function () {

  // show progressbar when submitting the data
  $("form").on("submit", function (event) {
      $("#loading-bar").css('display', 'flex');
  });

  // if data is already stored in the backend enable 'reset' button
  if ($("#resetButton").hasClass("d-inline")) {
    $(".form-control").each(function () {
      $(this).prop("disabled", true);
    });
  } else {
    $(".form-control").each(function () {
      $(this).prop("disabled", false);
    });
  }

  // if data is already stored in the backend enable 'continue' button
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
    $("#processData").prop("disabled", !areAllFieldsValid()).toggleClass("disabled", !areAllFieldsValid());
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
    const anyFieldEmpty = accordionItem.find("[data-required='true']").toArray().some(field => isFieldEmpty($(field)));
    if (accordionItem.hasClass("was-interacted")) {
      accordionHeader.css("background-color", anyFieldEmpty ? "#fff3cd" : "");
    }
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

  $(".accordion-item").each(function () {
    const accordionItem = $(this);
    updateFieldColors(accordionItem, false);
    updateHeaderColor(accordionItem);
  });

  // toggle between view and neuron centric view
  $('#toggleSynapseSelection').change(function () {
    if ($(this).is(':checked')) {
      $("#synapse-id-form").hide();
      $("#neuron-form").show();
      $("#view_style").val("neuron");
    } else {
      $("#synapse-id-form").show();
      $("#neuron-form").hide();
      $("#view_style").val("synapse");
    }
  });

  $("#neuroglancerModal").on("shown.bs.modal", function () {
    $(this).removeAttr("aria-hidden"); // Make modal accessible
    $(this).removeAttr('inert'); // Make modal interactive
    $("#neuroglancerIframe").focus(); // Move focus inside the modal
  });

  $("#neuroglancerModal").on("hidden.bs.modal", function () {
    $(this).attr("aria-hidden", "true"); // Restore aria-hidden when closed
    $(this).attr("inert", "true"); // Prevent interactions
    $("#openNeuronModalBtn").focus();
  });

  updateSubmitButtonState();

  // enable the neuropil layer when the modal opens
  $("#neuroglancerModal").on("show.bs.modal", function () {
    fetch('/launch_neuroglancer', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            $("#neuroglancerIframe").attr("src", data.ng_url);
            fetch('/enable_neuropil_layer', { method: 'POST' });
        })
        .catch(error => console.error('Error launching Neuroglancer:', error));
  });

  // disable the neuropil layer when the modal closes
  $("#neuroglancerModal").on("hidden.bs.modal", function () {
    fetch('/disable_neuropil_layer', { method: 'POST' });
  });

  let debounceTimer;
  const debounceDelay = 500;

  document.getElementById('materialization_url').addEventListener('input', function() {
    clearTimeout(debounceTimer);
    const self = this;
    debounceTimer = setTimeout(function() {
      var materializationUrl = self.value.trim();
      console.log("Materialization URL:", materializationUrl);
      var openNeuronModalBtn = document.getElementById('openNeuronModalBtn');
      openNeuronModalBtn.setAttribute('disabled', 'disabled');
      if (materializationUrl) {
        fetch('/load_materialization', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ materialization_url: materializationUrl })
        })
        .then(response => response.json())
        .then(data => {
          if (data.status === "success") {
            console.log("Materialization table loaded.");
            // Grab the form values
            var source_url = document.getElementById('source_url').value.trim();
            var target_url = document.getElementById('target_url').value.trim();
            var neuropil_url = document.getElementById('neuropil_url').value.trim();

            // Build the query string with proper URL encoding
            var queryString = '?source_url=' + encodeURIComponent(source_url) +
                              '&target_url=' + encodeURIComponent(target_url) +
                              '&neuropil_url=' + encodeURIComponent(neuropil_url);

            // Use a GET request to fetch the Neuroglancer URL with our form data in tow!
            fetch('/launch_neuroglancer' + queryString, { method: 'GET' })
              .then(response => response.json())
              .then(ngData => {
                if (ngData.ng_url) {
                  document.getElementById('neuroglancerIframe').src = ngData.ng_url;
                  console.log("Neuroglancer URL set to:", ngData.ng_url);
                  // Only enable the button upon successful processing without any alerts
                  openNeuronModalBtn.removeAttribute('disabled');
                } else {
                  console.error("No Neuroglancer URL received:", ngData.error);
                }
              })
              .catch(error => {
                console.error("Error launching Neuroglancer:", error);
              });
          } else {
            console.error("Error loading materialization table:", data.error);
          }
        })
        .catch(error => {
          console.error("Error during fetch:", error);
        });
      }
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
        // start puling the neuron ID every 250ms
        checkSelectedNeuronIDHandle = setInterval(checkNeuronID, 250);
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
          $("#neuron-id-open").text(selected_neuron_id);
          initialID = selected_neuron_id
        }
      },
      error: function (error) {
        console.error('Error fetching the neuron ID:', error);
      }
    });
  }

});
