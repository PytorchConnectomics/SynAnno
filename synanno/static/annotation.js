$(document).ready(function() {

    $('.image-card-btn').on('click', function() {
        var data_id = $(this).attr('data_id')
        var page = $(this).attr('page')
        var label = $(this).attr('label')

        req = $.ajax({
            url: '/update-card',
            type: 'POST',
            data: {data_id: data_id, page: page, label: label}
        });

        req.done(function (data){
            if(label==='Unsure'){
                $('#id'+data_id).removeClass('unsure').addClass('correct');
                $('#id-a-'+data_id).attr('label', 'Correct');
            }else if(label==='Incorrect'){
                $('#id'+data_id).removeClass('incorrect').addClass('unsure');
                $('#id-a-'+data_id).attr('label', 'Unsure');
            }else if(label==='Correct'){
                $('#id' + data_id).removeClass('correct').addClass('incorrect');
                $('#id-a-' + data_id).attr('label', 'Incorrect');
            }
        });
    });

    var ng_link; // link to the neuroglancer, edited when ever right clicking an middleslice
    var cz0;
    var cy0;
    var cx0;

    $('.image-card-btn').bind('contextmenu', async function(e){
        e.preventDefault();
        var data_id = $(this).attr('data_id')
        var page = $(this).attr('page')
        var label = $(this).attr('label')
        var strSlice = 0;

        req_data = $.ajax({
            url: '/save_slices',
            type: 'POST',
            data: {data_id: data_id, page: page, slice: strSlice}
        });

        await req_data.done(function (data) {
            $('#rangeSlices').attr('min', data.range_min);
            $('#rangeSlices').attr('max', data.range_min + data.slices_len-1);
            $('#rangeSlices').val(data.halflen);
            $('#rangeSlices').attr('data_id', data_id);
            $('#rangeSlices').attr('page', page);

            $('#minSlice').html(0);
            $('#maxSlice').html(data.slices_len-1);

            $('#imgDetails-EM').addClass(label.toLowerCase());
            $('#imgDetails-EM').attr('src', data.data.EM +'/'+ data.data.Middle_Slice + '.png');
            $('#imgDetails-GT').attr('src', data.data.GT +'/'+ data.data.Middle_Slice + '.png');
            $('#detailsModal').modal('show');

            cz0 = data.data.cz0
            cy0 = data.data.cy0
            cx0 = data.data.cx0

        });

        req_ng = $.ajax({
            url: '/neuro',
            type: 'POST',
            data: {cz0: cz0, cy0: cy0, cx0: cx0}
        });

        req_ng.done(function (data){
            ng_link = data.ng_link;
        });

    });

    $('#ng-link').on('click', function (){
        $('#ng-iframe').attr('src', ng_link)
    });


    $('#rangeSlices').on('input', function() {
        var rangeValue = $(this).val();

        var data_id = $(this).attr('data_id')
        var page = $(this).attr('page')

        req = $.ajax({
            url: '/get_slice',
            type: 'POST',
            data: {data_id: data_id, page: page, slice: rangeValue}
        });

        req.done(function (data){
            $('#imgDetails-EM').attr('src',  data.data.EM +'/'+ rangeValue + '.png');
            $('#imgDetails-GT').attr('src',  data.data.GT +'/'+ rangeValue + '.png');
        });

    })
});


function dec_opacity() {
    var value = $('#value-opacity').attr('value');
    var new_value = value - 0.1;
    if(new_value<0){
        new_value = 0;
    }
    $('#value-opacity').attr('value', new_value);
    $('#value-opacity').text(new_value.toFixed(1));
    $('#imgDetails-GT').css('opacity', new_value);

}

function add_opacity() {
    var value = $('#value-opacity').attr('value');
    var new_value = parseFloat(value) + 0.1;
    if(new_value>=1){
        new_value = 1;
    }
    $('#value-opacity').attr('value', new_value);
    $('#value-opacity').text(new_value.toFixed(1));
    $('#imgDetails-GT').css('opacity', new_value);
}

function check_gt(){
    var checkbox = document.getElementById('check-gt');
    if(checkbox.checked==false){
        $('#imgDetails-GT').css('display', 'none');
        $('#check-em').prop("disabled", true);
    } else {
        $('#imgDetails-GT').css('display', 'block');
        $('#check-em').prop("disabled", false);
    }
}

function check_em(){
    var checkbox = document.getElementById('check-em');
    if(checkbox.checked==false){
        $('#imgDetails-GT').css('background-color', 'black');
        $('#imgDetails-GT').css('opacity', '1');
        $('#check-gt').prop("disabled", true);
    } else {
        $('#imgDetails-GT').css('background-color', 'transparent');
        $('#imgDetails-GT').css('opacity', '1');
        $('#check-gt').prop("disabled", false);
    }
}