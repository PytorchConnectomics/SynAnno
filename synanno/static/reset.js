$(document).ready(function() {
    $("#resetButton").on("click", function(event) {
        event.preventDefault();  // Prevent default link navigation initially

        $.get("/is_metadata_locked", function(data) {
            if (data.locked) {
                alert("Reset is currently blocked. Please wait for processing to finish.");
            } else {
                window.location.href = $("#resetButton").attr("href");  // Proceed to reset
            }
        }).fail(function() {
            alert("Error checking metadata lock.");
        });
    });
});
