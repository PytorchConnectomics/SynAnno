let checkCoordinatesInterval = null;
let initialCoordinates = { cz: null, cy: null, cx: null };

// Start checking coordinates when the ng modal is shown
$(document).on("shown.bs.modal", "#drawModalFN", async function () {

    // Stop any existing intervals before starting a new one
    if (checkCoordinatesInterval) {
      clearInterval(checkCoordinatesInterval);
      checkCoordinatesInterval = null;
    }

    // Pull initial coordinates
    $.ajax({
      type: 'GET',
      url: '/get_coordinates',
      success: function (response) {
        // Start polling the coordinates every 500ms
        checkCoordinatesInterval = setInterval(checkCoordinates, 500);
      },
      error: function (error) {
        console.error('Error fetching initial coordinates:', error);
      }
    });
});

// Function to check for changes in coordinates **only if the modal is still present and visible**
function checkCoordinates() {
    if (!$("#drawModalFN").length || !$("#drawModalFN").is(":visible")) {
        console.log("Modal is closed or removed, stopping coordinate check.");
        clearInterval(checkCoordinatesInterval);
        checkCoordinatesInterval = null;
        return;
    }

    $.ajax({
        type: 'GET',
        url: '/get_coordinates',
        success: function (response) {
            const { cz, cy, cx } = response;
            if (cz !== initialCoordinates.cz || cy !== initialCoordinates.cy || cx !== initialCoordinates.cx) {
                $('#neuron-id-draw').text(`cx: ${parseInt(cx)}, cy: ${parseInt(cy)}, cz: ${parseInt(cz)}`);
                initialCoordinates = { cz, cy, cx };
            }
        },
        error: function (error) {
            console.error('Error fetching coordinates:', error);
        }
    });
}
