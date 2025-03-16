$(document).ready(function () {
  // Enable "start new process" button after mask or JSON download
  $("#dl_draw_masks, #dl_draw_JSON").click(function () {
      $("#resetButton").removeClass("disabled");
  });

  // Show loading bar and enable button after JSON download
  $("#dl_annotate_json").click(function () {
      $("#loading-bar").css('display', 'flex');
      $("#resetButton").removeClass("disabled");
      $("#loading-bar").css('display', 'none'); // TODO: Fix loading-bar timing issue
  });

  // Download required slices when entering drawing mode
  $("#redraw_masks").click(function(event) {
      event.preventDefault(); // Wait for AJAX response before redirect
      $("#loading-bar").css('display', 'flex');
      $(".text-white").text("Downloading missing slices...");
      $.post("/load_missing_slices")
          .done(function () {
              $("#loading-bar").css('display', 'none');
              window.location.href = event.target.getAttribute('href');
          })
          .fail(function () {
              console.error('Error loading missing slices');
              $("#loading-bar").css('display', 'none');
          });
  });
});
