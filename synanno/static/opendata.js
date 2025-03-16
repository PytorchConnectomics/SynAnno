document.addEventListener("DOMContentLoaded", function () {
  const loadingBar = document.getElementById("loading-bar");
  const resetButton = document.getElementById("resetButton");
  const continueButton = document.getElementById("continueButton");
  const processDataBtn = document.getElementById("processData");
  const materializationUrlInput = document.getElementById("materialization_url");
  const openNeuronModalBtn = document.getElementById("openNeuronModalBtn");
  const neuroglancerModal = document.getElementById("neuroglancerModal");
  let checkSelectedNeuronIDHandle, initialID = null;

  // Show progress bar when form is submitted
  document.querySelector("form")?.addEventListener("submit", () => loadingBar.style.display = "flex");

  // Toggle form controls based on backend state
  function toggleFormControls(condition) {
    document.querySelectorAll(".form-control").forEach(el => el.disabled = condition);
  }

  toggleFormControls(resetButton?.classList.contains("d-inline") || continueButton?.classList.contains("d-inline"));

  function isFieldEmpty(field) {
    return !field.value.trim();
  }

  function areAllFieldsValid() {
    return ![...document.querySelectorAll("[data-required='true']")].some(isFieldEmpty);
  }

  function updateSubmitButtonState() {
    const isValid = areAllFieldsValid();
    processDataBtn.disabled = !isValid;
    processDataBtn.classList.toggle("disabled", !isValid);
  }

  function updateFieldColors(accordionItem, userInteraction = false) {
    accordionItem.querySelectorAll("[data-required='true']").forEach(field => {
      field.style.backgroundColor = userInteraction && isFieldEmpty(field) ? "#fff3cd" : "";
    });
    updateSubmitButtonState();
  }

  function updateHeaderColor(accordionItem) {
    const header = accordionItem.querySelector(".accordion-header .accordion-button");
    const anyFieldEmpty = [...accordionItem.querySelectorAll("[data-required='true']")].some(isFieldEmpty);
    if (accordionItem.classList.contains("was-interacted")) {
      header.style.backgroundColor = anyFieldEmpty ? "#fff3cd" : "";
    }
  }

  function validateFormOnLoad() {
    document.querySelectorAll(".accordion-item").forEach(item => {
      updateFieldColors(item, false);
      updateHeaderColor(item);
    });
    updateSubmitButtonState();
  }

  document.querySelectorAll(".accordion-item").forEach(accordionItem => {
    accordionItem.addEventListener("shown.bs.collapse", () => {
      accordionItem.classList.add("was-interacted");
      updateFieldColors(accordionItem, true);
    });

    accordionItem.addEventListener("hidden.bs.collapse", () => {
      accordionItem.classList.add("was-interacted");
      updateHeaderColor(accordionItem);
    });

    accordionItem.querySelectorAll("[data-required='true']").forEach(field => {
      field.addEventListener("input", () => updateFieldColors(accordionItem, true));
    });
  });

  document.querySelectorAll("[data-required='true'], #volume-form input, #neuron-form input").forEach(el => {
    el.addEventListener("input", updateSubmitButtonState);
  });

  document.getElementById("toggleSynapseSelection")?.addEventListener("change", function () {
    const isNeuronView = this.checked;
    document.getElementById("volume-form").style.display = isNeuronView ? "none" : "block";
    document.getElementById("neuron-form").style.display = isNeuronView ? "block" : "none";
    document.getElementById("view_style").value = isNeuronView ? "neuron" : "volume";
    updateSubmitButtonState();
  });

  neuroglancerModal?.addEventListener("shown.bs.modal", async () => {
    try {
      const response = await fetch('/launch_neuroglancer', { method: 'POST' });
      const data = await response.json();
      document.getElementById("neuroglancerIframe").src = data.ng_url;
      await fetch('/enable_neuropil_layer', { method: 'POST' });
    } catch (error) {
      console.error('Error launching Neuroglancer:', error);
    }
  });

  neuroglancerModal?.addEventListener("hidden.bs.modal", async () => {
    try {
      await fetch('/disable_neuropil_layer', { method: 'POST' });
    } catch (error) {
      console.error('Error disabling neuropil layer:', error);
    }
    clearInterval(checkSelectedNeuronIDHandle);
  });

  let debounceTimer;
  materializationUrlInput?.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      const materializationUrl = materializationUrlInput.value.trim();
      openNeuronModalBtn.setAttribute("disabled", "disabled");
      if (!materializationUrl) return;
      try {
        const materializationResponse = await fetch('/load_materialization', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ materialization_url: materializationUrl })
        });
        const materializationData = await materializationResponse.json();
        if (materializationData.status === "success") {
          const queryString = new URLSearchParams({
            source_url: document.getElementById("source_url").value.trim(),
            target_url: document.getElementById("target_url").value.trim(),
            neuropil_url: document.getElementById("neuropil_url").value.trim()
          }).toString();
          const ngResponse = await fetch(`/launch_neuroglancer?${queryString}`);
          const ngData = await ngResponse.json();
          if (ngData.ng_url) {
            document.getElementById("neuroglancerIframe").src = ngData.ng_url;
            openNeuronModalBtn.removeAttribute("disabled");
          }
        }
      } catch (error) {
        console.error("Error loading materialization or launching Neuroglancer:", error);
      }
      updateSubmitButtonState();
    }, 500);
  });

  // FOR USER STUDY: initial check for materialization URL on page load
  if (materializationUrlInput?.value.trim()) {
    const event = new Event('input');
    materializationUrlInput.dispatchEvent(event);
  }

  validateFormOnLoad();
});
