/*! jQuery v1.11.3 | (c) 2005, 2015 jQuery Foundation, Inc. | jquery.org/license */
$( document ).ready(function() {
  if ( $( ".uninett-whole-row").hasClass("progressbar") ){
    console.log("Denne siden har progressbar");
    $(".section").css({"border-top": "none", "padding": "0", "margin": "0", "padding-top": "1.5em"});
    $(".summary-link").css({"left": "0", "top": "-2.3em"});
    var source = "";
    var element = "";
    $( ".progressbar ul li span" ).each(function() {
      element = $(this,"span");
      source = element.find("a").attr('href');
      var setlink = "<a href='"+ source +"'></a>";
      $(this,"span").wrap( setlink );
    });
  }
  var actiondd = "<div class='actiondd'></div>"
  $(".dmptable tbody tr td:last-child").wrap(actiondd);
});

$(window).bind('mousewheel', function(event) {
    if ( (event.originalEvent.wheelDelta >= 0) && ($(document).scrollTop() < 100) ) {
        $( ".progressbar").addClass("withfadeout");
        $( ".progressbar" ).removeClass("progressbar-small");
    }
    else {
        $( ".progressbar li span").addClass("withfadein");
        $( ".progressbar").removeClass("withfadeout");
        $( ".progressbar" ).addClass("progressbar-small");
    }
});
