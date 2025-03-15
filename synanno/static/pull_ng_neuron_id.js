let checkSelectedNeuronIDHandle = null;
let initialNeuronID = null;

$(document).on("shown.bs.modal", "#neuroglancerModal", async function () {
    try {
        const response = await fetch('/get_neuron_id');
        const data = await response.json();
        initialNeuronID = data.selected_neuron_id;
        checkSelectedNeuronIDHandle = setInterval(() => checkNeuronID("neuron-id-open"), 500);
    } catch (error) {
        console.error('Error fetching initial neuron ID:', error);
    }
});

$(document).on("hidden.bs.modal", "#neuroglancerModal", function () {
    clearInterval(checkSelectedNeuronIDHandle);
});

function checkNeuronID(neuronIdElementId) {
    fetch('/get_neuron_id')
        .then(response => response.json())
        .then(data => {
            const selectedNeuronID = data.selected_neuron_id;
            if (selectedNeuronID !== initialNeuronID) {
                document.getElementById(neuronIdElementId).textContent = parseInt(selectedNeuronID);
                initialNeuronID = selectedNeuronID;
            }
        })
        .catch(error => console.error('Error fetching the neuron ID:', error));
}
