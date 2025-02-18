// Enable the neuropil neuron segmentation layer
export function enableNeuropilLayer() {
    fetch('/enable_neuropil_layer', { method: 'POST' })
        .then(response => response.json())
        .then(data => console.log(data.status))
        .catch(error => console.error('Error enabling neuropil layer:', error));
  }

// Disable the neuropil neuron segmentation layer
export function disableNeuropilLayer() {
fetch('/disable_neuropil_layer', { method: 'POST' })
    .then(response => response.json())
    .then(data => console.log(data.status))
    .catch(error => console.error('Error disabling neuropil layer:', error));
}
