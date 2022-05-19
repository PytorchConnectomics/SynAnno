$(document).ready(function(){

    if ($('#resetButton').hasClass('d-block')){
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
});