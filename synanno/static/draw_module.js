$(document).ready(function () {

    $('[id^="drawButton_"]').click(async function () {
        var [page, data_id, label] = $($(this)).attr('id').replace(/drawButton_/, '').split('_')

        req_data = $.ajax({
            url: '/save_slices',
            type: 'POST',
            data: {data_id: data_id, page: page}
        });

        await req_data.done(function (data) {
            $('#imgDetails-EM').addClass(label.toLowerCase());
            $('#imgDetails-EM').attr('src', data.data.EM +'/'+ data.data.Middle_Slice + '.png');
            $('#detailsModal').modal('show');

    });
});
});