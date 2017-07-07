function user_message(text) {
    $("#messages").prepend('<li class="list-group-item">' +
                           text + "</li>");
}


$(document).ready(function() {
    
    // Connect to the Socket.IO server.
    // The connection URL has the following format:
    //     http[s]://<domain>:<port>[/<namespace>]
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + 
                            location.port);
    var messages = []; 

    socket.emit('refresh');
    // Display active keywords
    socket.on('keywords', function(msg) {
        console.log('Received active keywords');
        var kw = msg['keywords'];
        var deleteButton = 
            "<button class='delete btn btn-danger'>Remove</button>";
        for (var i = 0; i < kw.length; i++) {
            $(".list_of_items").append("<li class='list-group-item clearfix'>"+ 
                    "<div id='word' class='pull-left'>" + 
                    kw[i] + "</div>" + 
                    "<div class='pull-right'>" + deleteButton + "</div>" + 
                    "</li>");
        }
    });

    // Event handler for new tweet to display
    socket.on('display_tweet', function(msg) {
        console.log("Got tweet display request: " + msg['tweet_id'])
        // Get the tweet container
        var tweet_container = document.getElementById("tweet_container");
       // Remove all old content
        while (tweet_container.firstChild) {
            tweet_container.removeChild(tweet_container.firstChild);
        }
        // Add new content
        tweet = document.createElement('div');
        tweet.setAttribute('id', 'tweet');
        tweet_container.appendChild(tweet);
        var id = msg['tweet_id'];
        var guess = msg['guess'];
        
        if(id == 'waiting') {
            tweet.textContent = "Waiting for tweets...";
        } else {
            twttr.widgets.createTweet(id, tweet, {
                conversation : 'none',    // or all
                cards        : 'visible',  // or hidden
                linkColor    : '#cc0000', // default is blue
                theme        : 'light'    // or dark
            })
            .then (function (el) {
                console.log("Tweet Displayed");
            });
        }
    });


    // Keyword management code
    $("form#main_input_box").submit(function(event){
        user_message("Adding keyword. Changes might take up to 10s");
        event.preventDefault();
        var deleteButton = 
            "<button class='delete btn btn-danger'>Remove</button>";
        $(".list_of_items").append("<li class='list-group-item clearfix'>" + 
                "<div id='word' class='pull-left'>" + 
                $("#custom_textbox").val() + "</div>" + 
                "<div class='pull-right'>" + deleteButton + "</div>"  + 
                "</li>");
        socket.emit('add_keyword', {data: $('#custom_textbox').val()});
        $("#custom_textbox").val('');
        return(false);
    });

    $(".list_of_items").on("click", "button.delete", function(){
        user_message("Removing keyword. Changes might take up to 10s");
        var item = $(this).closest("li")
        var word = item.find('#word').text();
        socket.emit('remove_keyword', {data: word});
        item.remove();
        return(false);
    });

    socket.on("db_report", function(msg) {
        monitor_data = msg["data"];
        var data = monitor_data;
        $("#rate").html(data["rate"] + "/s");
        $("#total").html(data["total_count"]);
        $("#missed").html(data["missed"]);
        $("#annotated").html(data["annotated"]);
        $("#classified").html(data["classified"] + "%");
        var suggestions = data["suggested_features"];
        if (suggestions != null) {
            $("#suggestions").empty();
            for (var i = 0; i < suggestions.length; i++) {
                $("#suggestions").append('<li class="list-group-item">' +
                                         suggestions[i] + "</li>");
            }
        }
        var messages = data["messages"];
        if (messages != null) {
            for (var i = 0; i < messages.length; i++) {
                user_message(messages[i]);
            }
        }
        $("#performance").html(data['precision'] + '/' + data['recall'] + '/' +
                               data['f1']);

    });

    // Handlers for the different forms in the page.
    // These accept data from the user and send it to the server in a
    // variety of ways
    $("button#relevant").on('click', function() {
        socket.emit("tweet_relevant");
    });
    $("button#irrelevant").on('click', function() {
        socket.emit("tweet_irrelevant");
    });
    $("button#skip").on('click', function() {
        socket.emit("skip");
    });
    $("button#refresh").on('click', function() {
        socket.emit("refresh");
    });
});
