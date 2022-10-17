$(document).ready(function () {

    $('[id^="drawButton-"]').click(async function () {
        var [page, data_id, label] = $($(this)).attr('id').replace(/drawButton-/, '').split('-')

        req_data = $.ajax({
            url: '/save_slices',
            type: 'POST',
            data: { data_id: data_id, page: page }
        });

        await req_data.done(function (data) {
            $('#imgDetails-EM').addClass(label.toLowerCase());
            $('#imgDetails-EM').attr('src', data.data.EM + '/' + data.data.Middle_Slice + '.png');
            $('#detailsModal').modal('show');

        });
    });

    $('#add_new_instance').click(async function (e) {
        // open a new Neuroglancer view
        req_ng = $.ajax({
            url: '/neuro',
            type: 'POST',
            data: { cz0: 0, cy0: 0, cx0: 0 }
        });

        req_ng.done(function (data) {
            ng_link = data.ng_link;
            $('#ng-iframe-fp').attr('src', ng_link)

        });
    });

    $('#review_bbox').click(async function (e) {
        // retrieve the bb information from the backend
        $.ajax({
            url: '/ng_bbox_fp',
            type: 'POST',
            data: { z1: 0, z2: 0, my: 0, mx: 0 }
        }).done(function (data) {

            $('#m_x').val(data.mx)
            $('#m_y').val(data.my)

            $('#d_z1').val(data.z1)
            $('#d_z2').val(data.z2)

        });
    });


    $("#save_bbox").click(function () {
        // update the bb information with the manuel corrections and pass them to the backend
        // trigger the processing/save to Json process in the backend
        $.ajax({
            url: '/ng_bbox_fp_save',
            type: 'POST',
            data: { z1: $('#d_z1').val(), z2: $('#d_z2').val(), my: $('#m_y').val(), mx: $('#m_x').val() }
        }).done(function (data) {

            // hide modules
            $('#drawModalFPSave, #drawModalFP').modal('hide');

            // refresh page
            location.reload();
        });
    });

});