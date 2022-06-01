$(document).ready(function () {

    // check and complete the custom error fields based on the provided json
    $('[id^="customFlag_"]').each(function () {
        if ($(this).hasClass("checked")) {
            var [page, img_id] = $($(this)).attr('id').replace(/customFlag_/, '').split('_')
            var customFlagButton = '#customFlagButton_' + page + '_' + img_id
            var customFlagInput = '#customFlagInput_' + page + '_' + img_id
            $(customFlagButton).prop('checked', true);
            $(customFlagInput).prop("disabled", false);
            $(customFlagInput).prop('placeholder', "RANDOM");

            // ajax call to retrieve the text of the custom flag button
            req = $.ajax({
                url: '/custom_flag',
                type: 'POST',
                contentType: 'application/json',
                dataType : 'json',
                data: JSON.stringify({page:page , img_id: img_id})
            });

            req.done(function (data){
                $(customFlagInput).prop('placeholder', data.message);
            });

        }
    });

    // check "bad fit" fields based on the provided json
    $('[id^="badFit_"]').each(function () {
        if ($(this).hasClass("checked")) {
            $(this).removeClass("checked");
            $(this).prop('checked', true);
        }
    });

    // check "polarity" switch fields based on the provided json
    $('[id^="polaritySwitch_"]').each(function () {
        if ($(this).hasClass("checked")) {
            $(this).removeClass("checked");
            $(this).prop('checked', true);
        }
    });

    // ensure that the text field is only enabled if the button is selected
    $('[id^="customFlagButton_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/customFlagButton_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop("disabled", false);
    });

    $('[id^="falsePositive_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/falsePositive_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop("disabled", true);
    });

    $('[id^="badFit_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/badFit_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop("disabled", true);
    });

    $('[id^="polaritySwitch_"]').change(function () {
        var [page, img_id] = $($(this)).attr('id').replace(/polaritySwitch_/, '').split('_')
        var customFlagId = '#customFlagInput_' + page + '_' + img_id
        $(customFlagId).prop("disabled", true);
    });

    // process the flags: [[pager number, image number, flag], ..., [pager number, image number, flag]]
    $('#submit_button').click(async function () {
        
        // show loading screen 
        $('#progressModal').modal("show");

        // process flags
        var flags = []
        await $('[id^="id_error_"]').each(function () {
            var [page, img_id] = $($(this)).attr('id').replace(/id_error_/, '').split('_')
            if ($('[id^="falsePositive_"]', $(this)).is(":checked")) {
                flags.push({ page: page, idx: img_id, flag: "falsePositive" })
            }
            else if ($('[id^="badFit_"]', $(this)).is(":checked")) {
                flags.push({ page: page, idx: img_id, flag: "badFit" })
            }
            else if ($('[id^="polaritySwitch_"]', $(this)).is(":checked")) {
                flags.push({ page: page, idx: img_id, flag: "polaritySwitch" })
            }
            else if ($('[id^="customFlagButton_"]', $(this)).is(":checked")) {
                flags.push({ page: page, idx: img_id, flag: $('[id^="customFlagInput_"]', $(this)).val() })
            }
            else {
                flags.push({ page: page, idx: img_id, flag: "None" })
            }
        });
        // update the backend
        req = $.ajax({
            url: '/pass_flags',
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            data: JSON.stringify({ flags: flags })
        });

        req.success(function(){
            window.location.href = "final_page"
        })

        req.error(function(xhr, status, error) {
            var err = eval("(" + xhr.responseText + ")");
            alert(err.Message);
          })
    });

    // show message in case no faulty instances where selected/marked
    if ($('.card')[1]) {
        $('.bg-secondary').addClass('d-none')
    } else {
        $('.bg-secondary').removeClass('d-none')
    }
})