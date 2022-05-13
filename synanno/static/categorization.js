$(document).ready(function(){

    $('#submit_button').click(function(){
        $('[id^="id_error_"]').each(function() {
            if ($("#falsePositive", this).is(":checked")) {
                console.log("falsePositive")
              }
            else if ($("#badFit", this).is(":checked")) {
                console.log("badFit")
            }
            else if ($("#polaritySwitch", this).is(":checked")) {
                console.log("polaritySwitch")
            }
            else if ($('[id^="customFlagButton_"]', this).is(":checked")) {
                console.log($('[id^="customFlagInput_"]', this).val())
            }
        });
    });

    $('[id^="customFlagButton_"]').change(function() {
        var nr = $(this).attr('id').replace(/customFlagButton_/, '');
        var customFlagId = '#customFlagInput_'+nr
        $(customFlagId).removeAttr('disabled');
     });

     $('[id^="falsePositive_"]').change(function() {
        var nr = $(this).attr('id').replace(/falsePositive_/, '');
        var customFlagId = '#customFlagInput_'+nr
        $(customFlagId).attr('disabled','disabled');
     });

     $('[id^="badFit_"]').change(function() {
        var nr = $(this).attr('id').replace(/badFit_/, '');
        var customFlagId = '#customFlagInput_'+nr
        $(customFlagId).attr('disabled','disabled');
     });

     $('[id^="polaritySwitch_"]').change(function() {
        var nr = $(this).attr('id').replace(/polaritySwitch_/, '');
        var customFlagId = '#customFlagInput_'+nr
        $(customFlagId).attr('disabled','disabled');
     });
})