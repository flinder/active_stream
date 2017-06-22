$(document).ready(function() {
    // Connect to the Socket.IO server.
    // The connection URL has the following format:
    //     http[s]://<domain>:<port>[/<namespace>]
    var socket = io.connect(location.protocol + '//' + document.domain + ':' + 
            location.port);

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
        var item = $(this).closest("li")
        var word = item.find('#word').text();
        socket.emit('remove_keyword', {data: word});
        item.remove();
        return(false);
    });

    socket.on('db_report', function(msg) {
        console.log('Received db report');
        // Get report container
        var stats_list = document.getElementById("stats");
        var suggestions_list = document.getElementById("suggestions");

        // Remove all old content
        while (stats_list.firstChild) {
            stats_list.removeChild(stats_list.firstChild);
        }
        while (suggestions_list.firstChild) {
            suggestions_list.removeChild(suggestions_list.firstChild);
        }
        // Add new content
        var stats = msg['data']

        for (var key in stats) {
            if(key == "mif") {
                continue
            }
            if (stats.hasOwnProperty(key)) {
                var node = document.createElement('li');
                node.className += 'list-group-item';
                var textnode = document.createTextNode(key + ": " + stats[key]);
                node.appendChild(textnode);
                stats_list.appendChild(node);
            }
        }
        var suggestions = msg['data']['mif'];
        if(suggestions != null) {
            for(var i = 0; i < suggestions.length; i++) {
                var suggestion = suggestions[i];
                var node = document.createElement('li');
                node.className += 'list-group-item';
                var textnode = document.createTextNode(suggestion);
                node.appendChild(textnode);
                suggestions_list.appendChild(node);
            }
        }
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
