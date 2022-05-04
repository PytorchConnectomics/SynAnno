var start = 0;
const fc = 2.6;
var totaltime = 0;
var percent = 0;


$('#originalFile').bind('change', function() {
  totaltime = Math.round((this.files[0].size/1000000)*fc)
});

$(document).ready(function (){
   $('form').on('submit', function(event){
       var formData = new FormData($('form')[0]);
       if (start == 0){
           $('#progressModal').modal("show");
           start = moment();
       }
        progress = setInterval(function (){
          var delta = moment().diff(start, 'seconds');
          percent = Math.round((delta/totaltime)*100);
          if (percent>= 98){
              percent = 98;
          }
          $('.progress-bar').css("width", percent+"%");
        }, 500);
   });
});