$(document).ready(function(){

    if ($('#resetButton').hasClass('d-block')){
        $('.form-control').each(function(){
            $(this).attr('disabled', 'disabled')
        });
    }
    else
    {
        $('.form-control').each(function(){
            $(this).removeAttr('disabled')
        });
    };
});