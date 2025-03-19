export function updateSynapseColors() {
    if ($("script[src*='viewer.js']").attr("data-neuron-ready") === "true") {
      $(".image-card-btn").each(function () {
        updateSynapseColor($(this).attr("data_id"), $(this).attr("label"));
      });
      sessionStorage.setItem("synapseColors", JSON.stringify(window.synapseColors));
    }
  }


export function updateSynapseColor(dataId, label) {
    const labelColors = {
      correct: { color: 0x00ff00, name: "green" },
      unsure: { color: 0xffff00, name: "yellow" },
      incorrect: { color: 0xff0000, name: "red" },
    };

    if (labelColors[label]) {
      const { color, name } = labelColors[label];
      window.updateSynapse(dataId, null, new THREE.Color(color), null, true);
      window.synapseColors[dataId] = name;
    }
  }
