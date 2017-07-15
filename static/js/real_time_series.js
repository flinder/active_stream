// Adapted from Simen Brekken
// http://bl.ocks.org/simenbrekken/6634070
var monitor_data = null;
$(document).ready(function() {

    var limit = 60 * 3,
        duration = 1000,
        now = new Date(Date.now() - duration)

    var bb = document.querySelector ('#rate_graph_panel')
                        .getBoundingClientRect(),
        width = bb.width*0.9,
        height = bb.height*0.7,
        margins = {'top': 0.05*bb.height,
                   'left': 0.05*bb.width}

    var max_rate = 1;

    var groups = {
        rate: {
            value: 0,
            color: 'orange',
            data: d3.range(limit).map(function() {
                return 0
            })
        }
    }

    var x = d3.time.scale()
        .domain([now - (limit - 2), now - duration])
        .range([0, width])

    var y = d3.scale.linear()
        .domain([0, max_rate*1.1])
        .range([height, 0])

    var line = d3.svg.line()
        .interpolate('basis')
        .x(function(d, i) {
            return x(now - (limit - 1 - i) * duration)
        })
        .y(function(d) {
            return y(d)
        })

    var svg = d3.select('.graph').append('svg')
        .attr('class', 'chart')
        .attr('width', width)
        .attr('height', height + 50);

    svg = svg.append('g')
        .attr("transform", "translate(" + margins.left + "," + margins.top + ")");

    var x_axis = svg.append('g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0,' + height + ')')
        .call(x.axis = d3.svg.axis().scale(x).orient('bottom'));
    
    y.axis = d3.svg.axis()
        .scale(y)
        .orient('left')
        .ticks(5);

    var y_axis = svg.append('g')
        .attr('class', 'y axis')
        //.attr('transform', 'translate(' + 0.03*width + ',0)')
        .call(y.axis);

    var paths = svg.append('g');

    for (var name in groups) {
        var group = groups[name]
        group.path = paths.append('path')
            .data([group.data])
            .attr('class', name + ' group')
            .style('stroke', group.color);
    }

    function tick() {
        now = new Date()

        // Add new values
        //for (var name in groups) {
        //    var group = groups[name]
        //    //group.data.push(group.value) // Real values arrive at irregular intervals
        //    group.data.push(20 + Math.random() * 100)
        //    group.path.attr('d', line)
        //}
        var group = groups['rate'];

        if (monitor_data != null) {
            group.data.push(monitor_data['rate']);
            max_rate = Math.max.apply(Math, group.data);
            y.domain([0, max_rate]);
            y_axis.transition()
                .duration(duration)
                .ease('linear')
                .call(y.axis)


        } else {
            group.data.push(0);
        }
        group.path.attr('d', line);
               

        // Shift domain
        x.domain([now - (limit - 2) * duration, now - duration]);

        // Slide x-axis left
        x_axis.transition()
            .duration(duration)
            .ease('linear')
            .call(x.axis)

        // Slide paths left
        paths.attr('transform', null)
            .transition()
            .duration(duration)
            .ease('linear')
            .attr('transform', 'translate(' + x(now - (limit - 1) * duration) + ')')
            .each('end', tick)

        // Remove oldest data point from each group
        for (var name in groups) {
            var group = groups[name]
            group.data.shift()
        }
    }

    tick();
});
