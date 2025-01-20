$(document).ready(function () {
  // draw export
  // enable the "start new process" button after mask download
  $("#dl_draw_masks").click(function () {
    if ($("#draw_new_process").hasClass("disabled")) {
      $("#draw_new_process").removeClass("disabled");
    }
  });

  // enable the "start new process" button after json download
  $("#dl_draw_JSON").click(function () {
    if ($("#draw_new_process").hasClass("disabled")) {
      $("#draw_new_process").removeClass("disabled");
    }
  });

  // annotation export
  // show loading bar when loading json
  // enable the "start new process" button after json download
  $("#dl_annotate_json").click(function () {
    // TODO: The loading bar does not consider the computation time
    // for the json creation
    $("#loading-bar").css('display', 'flex');
    if ($("#annotate_new_process").hasClass("disabled")) {
      $("#annotate_new_process").removeClass("disabled");
    }
    $("#loading-bar").css('display', 'none');
  });

  // download the required slices when entering drawing mode
  $("#redraw_masks").click(function(event){

    // waite with the redirect until the ajax request returned successfully
    event.preventDefault();

    $('#loading-bar').css('display', 'flex');
    $.ajax({
      url:"/load_missing_slices",
      type:"POST",
      success: function() {
        // Redirect to the URL after the AJAX call completes
        $('#loading-bar').css('display', 'none');

        // trigger the initial redirect
        const href = event.target.getAttribute('href');
        window.location.href = href;
      },
      error: function() {
          // Handle error if needed
          console.error('Error loading missing slices');
          $('#loading-bar').css('display', 'none');
      }
    });
  });

});
