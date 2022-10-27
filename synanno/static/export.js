$(document).ready(function () {

    // draw export
    // enable the "start new process" button after mask download
    $('#dl_draw_masks').click(function () {
        if ($('#draw_new_process').hasClass('disabled')) {
            $('#draw_new_process').removeClass('disabled')
        };
    });

    // enable the "start new process" button after json download
    $('#dl_draw_JSON').click(function () {
        if ($('#draw_new_process').hasClass('disabled')) {
            $('#draw_new_process').removeClass('disabled')
        };
    });

    // annotation export
    // enable the "start new process" button after json download
    $('#dl_annotate_json').click(function () {
        if ($('#annotate_new_process').hasClass('disabled')) {
            $('#annotate_new_process').removeClass('disabled')
        };
    });

});