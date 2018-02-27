/*! jQuery v1.11.3 | (c) 2005, 2015 jQuery Foundation, Inc. | jquery.org/license */
$( document ).ready(function() {

 if ( $( ".uninett-whole-row").hasClass("progressbar") ){
    console.log("Denne siden har progressbar");
    //$(".section").css({"border-top": "none", "padding": "0", "margin": "0", "padding-top": "1.5em"});
    //$(".summary-link").css({"left": "0", "top": "-2.3em"});
    var source = "";
    var element = "";
    $( ".progressbar ul li span" ).each(function() {
      element = $(this,"span");
      source = element.find("a").attr('href');
      var setlink = "<a class='linkwrap' href='"+ source +"'></a>";
      //$(this,"span").wrap( setlink );
      var parentli = $(this).closest("li");
      console.log(parentli);
      parentli.wrap( setlink );
    });
  }

  /*if ( $( ".uninett-whole-row").hasClass("progressbar") ){
     console.log("Denne siden har progressbar");
     //$(".section").css({"border-top": "none", "padding": "0", "margin": "0", "padding-top": "1.5em"});
     //$(".summary-link").css({"left": "0", "top": "-2.3em"});
     var source = "";
     var element = "";
     $( ".progressbar ul li span" ).each(function() {
       element = $(this,"span");
       source = element.find("a").attr('href');
       var setlink = "<a href='"+ source +"'></a>";
       $(this,"span").wrap( setlink );
       var parentli = $(this).closest("li");
       parentli.wrap( setlink );
     });
   } */
  var actiondd = "<div class='actiondd'></div>"
  $(".dmptable tbody tr td:last-child").wrap(actiondd);
});
/*
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
}); */
/*
$("#summary_header .btn-default").click(function() {
  if($(this).hasClass('open')){
      $(this).removeClass('open');
  }else{
    $(this).addClass('open');
  }
});*/

$(".dmpsummary .section .btn-default").click(function() {
  if($(this).hasClass('open')){
      $(this).removeClass('open');
  }else{
    $(this).addClass('open');
  }
});

$(".actions .btn-default").click(function() {
  if($(this).hasClass('open')){
      $(this).removeClass('open');
  }else{
    $(this).addClass('open');
  }
});

$( ".dropdown #actionsMenu" ).click(function() {
    var getulOpen = "nei";
    $('.dropdown').removeAttr('id');
    var getul = $(this).closest('.dropdown');
    hiddenElements = $(':hidden');
    visibleElements = $(':visible');
    //gjør en sjekk på hvilken knapp som trykkes på : eks hvis man trykker rett på en annen knapp så skal det lukkes først på det første stedet.
    //if ($(".dropdown").hasClass("open") ){
    if (getul.hasClass('open')){
       getulOpen = "ja";
        $('.dropdown').removeAttr('id');
        $(".dropdown-menu").css("display", "none");
        getul.removeAttr('id');
        $(".dynamicdiv").css("display", "none");
        $( ".dynamicdiv" ).remove();
    }else {

    if ( (getulOpen == "nei" ) || ( $(".dropdown").hasClass('open')) ){
      console.log("nå åpner du en annen mens den første er lukket");
        $('.dropdown').removeAttr('id');
        $(".dropdown-menu").css("display", "none");
        $(".dynamicdiv").css("display", "none");
        $( ".dynamicdiv" ).remove();
    }
    var getrow = $(this).closest('tr');
    //var getul = $(this).closest('.dropdown');
    $( "<div class='dynamicdiv'></div>" ).insertAfter(getrow);
    getul.attr('id', 'slider');
    $(".dynamicdiv").slideToggle();
    $('#slider .dropdown-menu').slideToggle();
  }
});

$('.dropdown-menu').click(function(event){
    event.stopPropagation();
});

$(window).click( function(){
  if ($(".dropdown").hasClass("open") ) {
      $(".dropdown-menu").css("display", "none");
      $( ".dynamicdiv" ).remove();
      $(".dynamicdiv").css("display", "none");
      $('.dropdown').removeAttr('id');
  }else{
    $(".dropdown-menu").css("display", "none");
    $(".dynamicdiv").css("display", "none");
    $( ".dynamicdiv" ).remove();
    $('.dropdown').removeAttr('id');
  }
});
