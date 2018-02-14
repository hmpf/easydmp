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
});

// Hide Header on on scroll down
var didScroll;
var lastScrollTop = 0;
var delta = 5;
var navbarHeight = $('.navbar').outerHeight();

$(window).scroll(function(event){
    didScroll = true;
});

setInterval(function() {
    if (didScroll) {
        hasScrolled();
        didScroll = false;
    }
}, 250);

function hasScrolled() {
    var st = $(this).scrollTop();

    // Make sure they scroll more than delta
    if(Math.abs(lastScrollTop - st) <= delta)
        return;

    // If they scrolled down and are past the navbar, add class .nav-up.
    // This is necessary so you never see what is "behind" the navbar.
    if (st > lastScrollTop && st > navbarHeight){
        // Scroll Down
        $( ".navbar-fixed-top" ).addClass("slider");
        $( ".navbar-fixed-top" ).addClass("closed");
        $( ".jumbotron" ).addClass("jumbotron-small");
        $( ".progressbar").addClass("withfadein");
        $( ".progressbar li span").addClass("withfadein");
        $( ".progressbar").addClass("progressbar-small");
      //  $( ".navbar-fixed-top" ).slideUp( "fast", function() {
  // Animation complete.
        //});
      //  $('.navbar').removeClass('nav-down').addClass('nav-up');
    } else {
        // Scroll Up
        if(st + $(window).height() < $(document).height()) {
          $( ".navbar-fixed-top" ).removeClass("closed");
          $( ".progressbar").addClass("withfadeout");
          $( ".progressbar" ).removeClass("progressbar-small");
          $( ".jumbotron" ).removeClass("jumbotron-small");
          //$( ".navbar-fixed-top" ).slideDown( "fast", function() {
    // Animation complete.
          //});
            //$('.navbar').removeClass('nav-up').addClass('nav-down');
        }
    }

    lastScrollTop = st;
}


/*var iScrollPos = 0;
$(window).scroll(function () {
    var iCurScrollPos = $(this).scrollTop();
    if (iCurScrollPos > iScrollPos) {
        console.log("//Scrolling Down");
        $(".navbar").css("display", "none");
        $("body").css("padding-top", "0");
        $(".progressbar").css("display", "none");
    } else {
       console.log("//Scrolling Up");
       $(".navbar").css("display", "block");
       $("body").css("padding-top", "70px");
       $(".progressbar").css("display", "block");
    }
iScrollPos = iCurScrollPos;
}); */
