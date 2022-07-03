$(document).ready(function(){

    // if data is already stored in the backend enable 'reset' button
    if ($('#resetButton').hasClass('d-inline')){
        $('.form-control').each(function(){
            $(this).prop("disabled", true)
        });
    }
    else
    {
        $('.form-control').each(function(){
            $(this).prop("disabled", false)
        });
    };


    // if data is already stored in the backend enable 'continue' button
    if ($('#continueButton').hasClass('d-inline')){
        $('.form-control').each(function(){
            $(this).prop("disabled", true)
        });
    }
    else
    {
        $('.form-control').each(function(){
            $(this).prop("disabled", false)
        });
    };


    var source = false;
    var target = false;
    var json = true;

    // when drawing we also require the JSON
    if ($('#formFile').hasClass('draw')){
        var json = false;
    }

    $('#formFile').on("change", function(){
        json = true;

        if (source && target && json){
            $('#processData').removeClass('disabled')
        }
    });

    $('#originalFile').on("change", function(){
        source = true;

        if (source && target && json){
            $('#processData').removeClass('disabled')
        }
    });

    $('#gtFile').on("change", function(){
        target = true;

        if (source && target && json){
            $('#processData').removeClass('disabled')
        }
    });



});