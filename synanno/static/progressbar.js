var percent = 0;

$(document).ready(function () {

  $('form').on('submit', function (event) {
    $('#progressModal').modal("show");
    ping_backend()
  });
});

function ping_backend() {
  setTimeout(function () {
    $.ajax({
      url: "/progress",
      type: "POST",
      data: { progress: percent }
    }).done(function (data) {
      if (data.status.includes("Loading")) {
        $('.spinner').removeClass('d-none')
        $('.progress').addClass('d-none')
        $('#spinnerText').find('strong').text(data.status);
      } else {
        $('.spinner').addClass('d-none')
        $('.progress').removeClass('d-none')
        $('#progressBarProcess').css("width", data.progress + "%");
        $('#progressBarText').text(data.status);
      }
    });
    if (percent <= 100) {
      ping_backend()
    }
  }, 500)
};