let checkCoordinatesInterval = null;
let initialCoordinates = { cz: null, cy: null, cx: null };

$(document).on("shown.bs.modal", "#drawModalFN", async function () {
    if (checkCoordinatesInterval) {
        clearInterval(checkCoordinatesInterval);
        checkCoordinatesInterval = null;
    }

    try {
        await $.get('/get_coordinates');
        checkCoordinatesInterval = setInterval(checkCoordinates, 500);
    } catch (error) {
        console.error('Error fetching initial coordinates:', error);
    }
});

function checkCoordinates() {
    const $modal = $("#drawModalFN");
    if (!$modal.length || !$modal.is(":visible")) {
        console.log("Modal is closed or removed, stopping coordinate check.");
        clearInterval(checkCoordinatesInterval);
        checkCoordinatesInterval = null;
        return;
    }

    $.get('/get_coordinates')
        .done(response => {
            const { cz, cy, cx } = response;
            if (cz !== initialCoordinates.cz || cy !== initialCoordinates.cy || cx !== initialCoordinates.cx) {
                console.log("Old:", initialCoordinates, "New:", { cz, cy, cx });
                console.log($("#neuron-id-draw").length); // Should be 1

                $('#neuron-id-draw').text(`cx: ${parseInt(cx)} - cy: ${parseInt(cy)} - cz: ${parseInt(cz)}`);
                initialCoordinates = { cz, cy, cx };
            }
        })
        .fail(error => console.error('Error fetching coordinates:', error));
}
