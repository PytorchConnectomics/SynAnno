$(document).ready(function () {

    // if data is already stored in the backend enable 'reset' button
    if ($('#resetButton').hasClass('d-inline')) {
        $('.form-control').each(function () {
            $(this).prop('disabled', true)
        });
    }
    else {
        $('.form-control').each(function () {
            $(this).prop('disabled', false)
        });
    };


    // if data is already stored in the backend enable 'continue' button
    if ($('#continueButton').hasClass('d-inline')) {
        $('.form-control').each(function () {
            $(this).prop('disabled', true)
        });
    }
    else {
        $('.form-control').each(function () {
            $(this).prop('disabled', false)
        });
    };


    var source = false;
    var target = false;
    var json = true;
    
    // when drawing we also require the JSON
    if ($('#formFile').hasClass('draw')) {
        var json = false;
    }
    
    
    
    // enable the 'submit' button if all required files got provided
    $('#formFile').on('change', function () {
        json = true;
        
        if (source && target && json) {
            $('#processData').removeClass('disabled')
        }
    });
    
    // enable the 'submit' button if all required files got provided
    $('#source_file').on('change', function () {
        source = true;
        
        if (source && target && json) {
            $('#processData').removeClass('disabled')
        }
    });
    
    // enable the 'submit' button if all required files got provided
    $('#target_file').on('change', function () {
        target = true;
        
        if (source && target && json) {
            $('#processData').removeClass('disabled')
        }
    });
    
    // remove disabled from processData button if the default values are not empty
    if ($('#source_url').val() != '' && $('#target_url').val() != '') {
        source = true;
        target = true;
        $('#processData').removeClass('disabled')
    }


    // enable the 'submit' button if all required files got provided
    $('#source_url').on('input', function () {
        
        source = true;          
        
            if (source && target) {
                $('#processData').removeClass('disabled')
            }
    
    });

    // enable the 'submit' button if all required files got provided
    $('#target_url').on('input', function () {

            target = true;

            if (source && target) {
                $('#processData').removeClass('disabled')
            }

    });

    // toggle between view and neuron centric view
    $('input[type="radio"]').change(function() {
        if ($(this).val() === 'view') {
            $('#view-form').show();
            $('#neuron-form').hide();
        } else if ($(this).val() === 'neuron') {
            $('#view-form').hide();
            $('#neuron-form').show();
        }
    });
});