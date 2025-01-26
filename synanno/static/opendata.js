$(document).ready(function () {
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
  $('input[type="radio"]').change(function () {
    if ($(this).val() === "view") {
      $("#view-form").show();
      $("#neuron-form").hide();
    } else if ($(this).val() === "neuron") {
      $("#view-form").hide();
      $("#neuron-form").show();
    }
  });

  updateSubmitButtonState();

  // Enable the c3 neuron segmentation layer
  function enableC3Layer() {
    fetch('/enable_c3_layer', { method: 'POST' })
        .then(response => response.json())
        .then(data => console.log(data.status))
        .catch(error => console.error('Error enabling c3 layer:', error));
  }

  // Disable the c3 neuron segmentation layer
  function disableC3Layer() {
    fetch('/disable_c3_layer', { method: 'POST' })
        .then(response => response.json())
        .then(data => console.log(data.status))
        .catch(error => console.error('Error disabling c3 layer:', error));
  }

  // Enable the c3 layer when the modal opens
  $("#neuroglancerModal").on("show.bs.modal", function () {
    fetch('/launch_neuroglancer')
        .then(response => response.json())
        .then(data => {
            $("#neuroglancerIframe").attr("src", data.ng_url);
            fetch('/enable_c3_layer', { method: 'POST' });
        })
        .catch(error => console.error('Error launching Neuroglancer:', error));
  });

  // Disable the c3 layer when the modal closes
  $("#neuroglancerModal").on("hidden.bs.modal", function () {
    fetch('/disable_c3_layer', { method: 'POST' });
  });
});
