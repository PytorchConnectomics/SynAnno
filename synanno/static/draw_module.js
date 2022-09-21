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
        req_ng = $.ajax({
            url: '/neuro',
            type: 'POST',
            data: { cz0: 0, cy0: 0, cx0: 0 }
        });

        req_ng.done(function (data) {
            ng_link = data.ng_link;
            console.log(ng_link)
            $('#ng-iframe-fp').attr('src', ng_link)

        });
    });

    $('#review_bbox').click(async function (e) {
        $.ajax({
            url: '/ng_bbox',
            type: 'POST',
            data: { blz: 0, bly: 0, blx: 0, trz: 0, try: 0, trx: 0 }
        }).done(function (data) {
            
            $('#bl_z').val(data.blx)
            $('#bl_y').val(data.bly)
            $('#bl_x').val(data.blz)
            
            $('#tr_z').val(data.trx)
            $('#tr_y').val(data.try)
            $('#tr_x').val(data.trz)

            if(parseInt(data.blz) > parseInt(data.trz)){
                $('#d_z1').val(data.trz)
                $('#d_z2').val(data.blz)
            }else{
                $('#d_z1').val(data.blz)
                $('#d_z2').val(data.trz)
            }
            
        });
    });

    $("#save_bbox").click(function(){
        $('#drawModalFPSave, #drawModalFP').modal('hide');
    });

});