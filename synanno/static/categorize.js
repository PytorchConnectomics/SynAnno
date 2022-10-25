$(document).ready(function () {

    // check and complete the custom error fields based on the provided json
    $('[id^="customFlag_"]').each(function () {
        if ($(this).hasClass('checked')) {
            var [page, img_id] = $($(this)).attr('id').replace(/customFlag_/, '').split('_')
            var customFlagButton = '#customFlagButton_' + page + '_' + img_id
            var customFlagInput = '#customFlagInput_' + page + '_' + img_id
            $(customFlagButton).prop('checked', true);
            $(customFlagInput).prop('disabled', false);
            $(customFlagInput).prop('placeholder', 'RANDOM');

            // ajax call to retrieve the text of the custom flag button
            req = $.ajax({
                url: '/custom_flag',
                type: 'POST',
                contentType: 'application/json',
                dataType : 'json',
                data: JSON.stringify({page:page , img_id: img_id})
            });

            req.done(function (data){
                $(customFlagInput).val(data.message);
            });

        }
    });

    // check "bad fit" fields based on the provided json
    $('[id^="badFit_"]').each(function () {
        if ($(this).hasClass('checked')) {
            $(this).removeClass('checked');
            $(this).prop('checked', true);
        }
    });

    // check "polarity" switch fields based on the provided json
    $('[id^="polaritySwitch_"]').each(function () {
        if ($(this).hasClass('checked')) {
            $(this).removeClass('checked');
            $(this).prop('checked', true);
        }
    });

    // check "polarity" switch fields based on the provided json
    $('[id^="falsePositive_"]').each(function () {
        if ($(this).hasClass('checked')) {
            $(this).removeClass('checked');
            $(this).prop('checked', true);
        }
    });

    // ensure that the text field is only enabled if the button is selected
    $('[id^="customFlagButton_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/customFlagButton_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop('disabled', false);
    });

    $('[id^="falsePositive_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/falsePositive_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop('disabled', true);
    });

    $('[id^="badFit_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/badFit_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop('disabled', true);
    });

    $('[id^="polaritySwitch_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/polaritySwitch_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop('disabled', true);
    });


    // process the flags: [[pager number, image number, flag], ..., [pager number, image number, flag]]

    // delete the false positives from the JSON
    $('#dl_fp_yes').click(async function(){
        // show loading screen 
        $('#categorizeModalFPSave').modal('hide');
        $('#progressModal').modal('show');

        submit_data(true)
    });

    // keep the false positives in the JSON
    $('#dl_fp_no').click(async function(){
        // show loading screen 
        $('#categorizeModalFPSave').modal('hide');
        $('#progressModal').modal('show');

        submit_data(false)
    });



    // show message in case no faulty instances where selected/marked
    if ($('.card')[1]) {
        $('.bg-secondary').addClass('d-none')
    } else {
        $('.bg-secondary').removeClass('d-none')
    }
    
})

// process the flags: [[pager number, image number, flag], ..., [pager number, image number, flag]]
function submit_data(delete_fps) {

    var promise_error = new Promise ((resolve,reject) =>{
        var flags = []
        var nr_elements = $('[id^="id_error_"]').length

        
        // resolve in case that no samples where marked as wrong or unsure
        if (nr_elements==0){
            resolve(flags) 
        }

        // update the error ids of the faulty instances
        $('[id^="id_error_"]').each(function (index) {
            var [page, img_id] = $($(this)).attr('id').replace(/id_error_/, '').split('_')
            if ($('[id^="falsePositive_"]', $(this)).is(':checked')) {
                flags.push({ page: page, idx: img_id, flag: 'falsePositive' })
            }
            else if ($('[id^="badFit_"]', $(this)).is(':checked')) {
                flags.push({ page: page, idx: img_id, flag: 'badFit' })
            }
            else if ($('[id^="polaritySwitch_"]', $(this)).is(':checked')) {
                flags.push({ page: page, idx: img_id, flag: 'polaritySwitch' })
            }
            else if ($('[id^="customFlagButton_"]', $(this)).is(':checked')) {
                flags.push({ page: page, idx: img_id, flag: $('[id^="customFlagInput_"]', $(this)).val() })
            }
            else {
                flags.push({ page: page, idx: img_id, flag: 'None' })
            }
            if (index==nr_elements-1){
                resolve(flags)
            }
        });
    })

    promise_error.then( (data) => {
        
        // update the backend
        req = $.ajax({
            url: '/pass_flags',
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({ flags: data, delete_fps: delete_fps })
        });

        req.success(function(){
            window.location.href = 'export_annotate'
        })

        req.error(function(xhr, status, error) {
            var err = eval('(' + xhr.responseText + ')');
            alert(err.Message);
        })
    });
};