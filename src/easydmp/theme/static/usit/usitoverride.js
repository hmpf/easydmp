/*! jQuery v1.11.3 | (c) 2005, 2015 jQuery Foundation, Inc. | jquery.org/license */
$( document ).ready(function() {

  if ( $( ".uninett-whole-row").hasClass("progressbar") ){
    console.log("Denne siden har progressbar");
    $(".section").css({"border-top": "none", "padding": "0", "margin": "0", "padding-top": "1.5em"});
    $(".summary-link").css({"left": "0", "top": "-2.3em"});

    /*var link = "";
    $( ".progressbar ul li" ).each(function() {
      link =  $( this ).find("a").attr("href");
        console.log(link);
        setlink = "<a href="+ link +"></a>";
        $( ".progressbar ul li span" ).wrap( setlink );
    });*/
  }
});
