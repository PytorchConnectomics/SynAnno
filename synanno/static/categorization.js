$(document).ready(function(){

    // ensure that the text field is only enabled if the button is selected
    $('[id^="customFlagButton_"]').change(function() {
        var [page, img_id] = $(this).attr('id').replace(/customFlagButton_/, '').split('_')
        var customFlagId = '#customFlagInput_'+page+'_'+img_id
        $(customFlagId).removeAttr('disabled');
     });

     $('[id^="falsePositive_"]').change(function() {
        var [page, img_id] = $(this).attr('id').replace(/falsePositive_/, '').split('_')
        var customFlagId = '#customFlagInput_'+page+'_'+img_id
        $(customFlagId).attr('disabled','disabled');
     });

     $('[id^="badFit_"]').change(function() {
        var [page, img_id] = $(this).attr('id').replace(/badFit_/, '').split('_')
        var customFlagId = '#customFlagInput_'+page+'_'+img_id
        $(customFlagId).attr('disabled','disabled');
     });

     $('[id^="polaritySwitch_"]').change(function() {
        var [page, img_id] = $(this).attr('id').replace(/polaritySwitch_/, '').split('_')
        var customFlagId = '#customFlagInput_'+page+'_'+img_id
        $(customFlagId).attr('disabled','disabled');
     });

    // process the flags: [[pager number, image number, flag], ..., [pager number, image number, flag]]
    $('#submit_button').click(async function(){
        await $('[id^="id_error_"]').each(function() {
            var flag = []
            var [page, img_id] = $(this).attr('id').replace(/id_error_/, '').split('_')
            flag.push(page)
            flag.push(img_id)
            if ($('[id^="falsePositive_"]', this).is(":checked")) {
                flag.push("falsePositive")
              }
            else if ($('[id^="badFit_"]', this).is(":checked")) {
                flag.push("badFit")
            }
            else if ($('[id^="polaritySwitch_"]', this).is(":checked")) {
                flag.push("polaritySwitch")
            }
            else if ($('[id^="customFlagButton_"]', this).is(":checked")) {
                flag.push($('[id^="customFlagInput_"]', this).val())
            }
            else{
                flag.push("None")
            }
            req = $.ajax({
                url: '/pass_flags',
                type: 'POST',
                data: {flag: flag}

        });
        });
    });
    
})