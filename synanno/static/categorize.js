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
        var flags = []
        await $('[id^="id_error_"]').each(function() {
            var [page, img_id] = $(this).attr('id').replace(/id_error_/, '').split('_')
            if ($('[id^="falsePositive_"]', this).is(":checked")) {
                flags.push({page:page, idx:img_id, flag:"falsePositive"})
              }
            else if ($('[id^="badFit_"]', this).is(":checked")) {
                flags.push({page:page, idx:img_id, flag:"badFit"})
            }
            else if ($('[id^="polaritySwitch_"]', this).is(":checked")) {
                flags.push({page:page, idx:img_id, flag:"polaritySwitch"})
            }
            else if ($('[id^="customFlagButton_"]', this).is(":checked")) {
                flags.push({page:page, idx:img_id, flag:$('[id^="customFlagInput_"]', this).val()})
            }
            else{
                flags.push({page:page, idx:img_id, flag:"None"})
            }
        });
        await $.ajax({
            url: '/pass_flags',
            type: 'POST',
            contentType: 'application/json',
            dataType : 'json',
            data: JSON.stringify({flags: flags})
        });
    });
    
})