$(document).ready(function () {

    // retrieve canvas and set 2D context
    var canvas = $('canvas.coveringCanvas');
    var ctx = canvas.get(0).getContext('2d');

    // set red as default color; used for the control points
    ctx.fillStyle = '#FF0000';

    // initialize mouse position to zero
    var mousePosition = {
        x: 0,
        y: 0
    };

    // init default span variables for the canvas
    var width;
    var height;

    // initialize global rectangle variable
    var rect;

    // turn mask drawing and splitting of at the start
    var draw_mask = false;
    var split_mask = false;

    // global buffer for the start, end, and control points of the spline
    var points = []

    // global buffer for the point on the curve
    var pointsQBez = []

    // init thickness
    var thickness = 20

    // define colors
    const turquoise = 'rgba(51, 255, 240, 0.7)';

    // set polarity default
    var color_turquoise = turquoise

    // variable for toggling the polarity

    // init image identifiers to null
    var page;
    var data_id;
    var label;

    // path where to save the custom masks - carful, this variable is also set in draw_module.js
    const base_mask_path = '/static/custom_masks/'

    // make sure that the modal is reset every time it get closed
    $('.modal').on('hidden.bs.modal', function () {
        // we only want to add the class d-none in case the module was actually closed and not just hidden
        // behind an other module
        if (! $('.modal:visible').length) {
            $('canvas.coveringCanvas').addClass('d-none')          
        }
    });

    // setup/reset the canvas when ever a draw button is clicked
    $('[id^="drawButton-"]').click(async function () {

        // retrieve the instance identifiers for later ajax calls
        [page, data_id, label] = $($(this)).attr('id').replace(/drawButton-/, '').split('-')

        // ensure that all options except the activate canvas button are disabled at start
        $('#canvasButtonCreate').prop('disabled', true);
        $('#thickness_range').prop('disabled', true);
        $('#canvasButtonSplit').prop('disabled', true);
        $('#canvasButtonSave').prop('disabled', true);
        
        ctx.restore() // restore default settings

        width = canvas.get(0).width // retrieve the width of the canvas
        height = canvas.get(0).height // retrieve the width of the canvas

        // reset red as default color; used for the control points
        ctx.fillStyle = '#FF0000';

        // reset activation button
        $('#canvasButtonActivate').text('Activate');

        clear_canvas() // clear previous output
        points = [] // reset the point list
        pointsQBez = [] // reset the pointsQBez list
        split_mask = false // deactivate mask splitting
        draw_mask = true // activate mask drawing

        // initialize mouse position to zero
        mousePosition = {
            x: 0,
            y: 0
        };
    });


    // on click activate canvas
    $('#canvasButtonActivate').on('click', function () {

        ctx.restore() // restore default settings

        // activate canvas for the first time after clicking a 'Draw Mask' button
        if ($('canvas.coveringCanvas').hasClass('d-none')) {
            $('#imgDetails-EM-GT').addClass('d-none'); // hide the previously drawn mask
            $('#canvasButtonActivate').text('Reset'); // switch the button label to 'Reset'
            $('canvas.coveringCanvas').removeClass('d-none') // change the visibility of the canvas
            rect = $('canvas.coveringCanvas').get(0).getBoundingClientRect() // get absolute rect. of canvas
            width = canvas.get(0).width // retrieve the width of the canvas
            height = canvas.get(0).height // retrieve the width of the canvas
            split_mask = false // deactivate mask splitting
            draw_mask = true // activate mask drawing
            // reset canvas
        } else {
            // disable all options except the activate canvas button
            $('#canvasButtonCreate').prop('disabled', true);
            $('#thickness_range').prop('disabled', true);
            $('#canvasButtonSplit').prop('disabled', true);
            $('#canvasButtonSave').prop('disabled', true);

            clear_canvas() // clear previous output
            points = [] // reset the point list
            pointsQBez = [] // reset the pointsQBez list
            split_mask = false // deactivate mask splitting
            draw_mask = true // activate mask drawing

        }
    });


    // activate event for splitting/erasing the curve
    $('#canvasButtonSplit').on('click', function () {
        ctx.save() // save the canvas settings
        ctx.globalCompositeOperation = 'destination-out'; // change the settings such that new input overwrites existing one
        split_mask = true;
    });

    // if split_mask is set to true turns the mouse pointer in to a circular eraser
    $('canvas.coveringCanvas').mousemove(function (event) {
        if (split_mask) {
            // detect possible changes in mouse position
            if ((mousePosition.x != event.clientX || mousePosition.y != event.clientY) && event.buttons == 1) {
                mousePosition.x = event.clientX;
                mousePosition.y = event.clientY;

                // Set global composite operation to destination-out
                var pos = getXY(this, event)
                var x = pos.x
                var y = pos.y
                ctx.strokeStyle = '#000';
                ctx.beginPath();
                ctx.moveTo(x + thickness, y)
                ctx.ellipse(x, y, thickness, Math.floor(thickness / 2), 0, 0, Math.PI * 2)
                ctx.fill();
            }
        }
    })

    // create the mask based on the drawn spline
    $('#canvasButtonCreate').on('click', function () {
        ctx.restore() // restore default settings
        split_mask = false; // turn of eraser
        draw_mask = false; // do not let the user draw any more points

        if (!(pointsQBez.length > 0)) {
            // sample points along splines and draw the mask
            fill_clip(color_turquoise, thickness, sample = true)
        } else {
            // draw the mask, reuse sampled points
            fill_clip(color_turquoise, thickness, sample = false)
        }
        // activate all options for manipulating and saving the mask
        $('#thickness_range').prop('disabled', false);
        $('#canvasButtonSplit').prop('disabled', false);
        $('#canvasButtonSave').prop('disabled', false);
    });

    // save the current mask
    $('#canvasButtonSave').on('click', async function () {
        var dataURL = canvas.get(0).toDataURL(); // retrieve the image from the canvas as a base64 encoding

        // the viewed instance slice value is set when scrolling through the individual slices of an instance
        var viewed_instance_slice = $('#rangeSlices').data('viewed_instance_slice');

        // send the base64 encoded image to the backend
        await $.ajax({
            type: 'POST',
            url: '/save_canvas',
            type: 'POST',
            data: { imageBase64: dataURL, data_id: data_id, page: page, viewed_instance_slice: viewed_instance_slice }
            // update the depicted mask with the newly drawn mask
        }).done(function (data) {

            data_json = JSON.parse(data.data); 

            // handle to source image of the instance module            
            var em_source_image = '#imgGT-' + page + '-' + data_id

            // handle to ground truth image of the instance module
            var em_target_image = '#imgEM-GT-' + page + '-' + data_id

            // create path to image
            var coordinates = data_json.Adjusted_Bbox.join('_')
            var img_index = data_json.Image_Index
            img_name = 'idx_' + img_index + '_ms_' + viewed_instance_slice + '_cor_' + coordinates + '.png'
            image_path = base_mask_path + img_name

            // update the in the tile view depicted source image 
            var base_path = $(em_source_image).data('image_base_path')
            $(em_source_image).attr('src', base_path + '/' + viewed_instance_slice +'.png');
            
            // update the in the tile view depicted target image
            // we load the image and add cache breaker in case the mask gets drawn multiple times
            // with out the cache breaker the mask will be updated in the backend, however, the old image will be depicted
            $(new Image()).attr('src', image_path + '?' + Date.now()).load(function () {
                $(em_target_image).attr('src', this.src);
            });
            
        });
    })

    // set start, end, and control points for curve that draws the mask
    $('canvas.coveringCanvas').on('click', function (e) {
        if (draw_mask) {
            clear_canvas() // clear canvas
            ctx.beginPath() // init path

            // get click position
            var pos = getXY(this, e)
            var x = pos.x
            var y = pos.y

            // add new point to points list
            points.push({ x, y })

            // draw the line segments in case that the points list contains more then two points
            if (points.length > 2) {
                draw_quad_line(points)
                // activate the fill button should the length of point be greater 2
                $('#canvasButtonCreate').prop('disabled', false);
            }
            // if the list only contains two points draw straight light
            else if (points.length > 1) {
                ctx.moveTo((points[0].x), points[0].y);
                ctx.fillRect(points[0].x, points[0].y, 2, 2) // mark start point with red rectangle 
                ctx.fillRect(points[1].x, points[1].y, 2, 2) // mark end point with red rectangle
                ctx.lineTo(points[0].x, points[0].y);
                ctx.lineTo(points[1].x, points[1].y);
                ctx.stroke();
            }
        }
    })

    // helper function for clearing the canvas
    function clear_canvas() {
        ctx.beginPath();
        ctx.clearRect(0, 0, canvas.get(0).width, canvas.get(0).height);
        ctx.stroke();
    }

    // helper function for calculating the relative mouse click based on the canvas expansion
    function getXY(canvas, evt) {
        // using the absolute rect. of canvas
        return {
            x: (evt.clientX - rect.left) / (rect.right - rect.left) * canvas.width,
            y: (evt.clientY - rect.top) / (rect.bottom - rect.top) * canvas.height
        };
    }

    
    function fill_clip(color_turquoise, thickness, sample = false) {

        clear_canvas(); // clear the canvas
        ctx.beginPath(); // init new path
    
        let pl = points.length; // retrieve length of points list 
    
        // if the points list contains more than two points
        if (pl > 2) {
            let ax, ay, bx, by, cx, cy;
    
            // sample lines along the created quadratic curve
            if (sample) {
                ax = points[0].x; // retrieve start point x
                ay = points[0].y; // retrieve start point y
    
                // iterate over all intermediate points
                for (let i = 1; i < pl - 2; i++) {
                    cx = points[i].x;
                    cy = points[i].y;
                    bx = (points[i].x + points[i + 1].x) / 2;
                    by = (points[i].y + points[i + 1].y) / 2;
    
                    // sample the current line segment
                    // the number of samples per line segment depends on the length of the segment
                    plotQBez(pointsQBez, Math.floor(Math.abs(ax - bx) + Math.abs(ay - by)), ax, ay, cx, cy, bx, by);
    
                    ax = bx;
                    ay = by;
                }
    
                // sample the last line segment
                bx = points[pl - 1].x;
                by = points[pl - 1].y;
                cx = points[pl - 2].x;
                cy = points[pl - 2].y;
    
                // sample the last line segment
                // the number of samples per line segment depends on the length of the segment
                plotQBez(pointsQBez, Math.floor(Math.abs(ax - bx) + Math.abs(ay - by)), ax, ay, cx, cy, bx, by);
            }
    
            ctx.save(); // save the current settings
    
            let region_1 = new Path2D(); // define new region
    
            // for every point that was sampled draw a an ellipse with the point at its center
            for (let j = 0; j < pointsQBez.length; j++) {
                // the normal aspect ratio of a html5 canvas is 2/1 
                // since we have equal width and height, y is distorted by factor 2
                region_1.moveTo(pointsQBez[j].x + thickness, pointsQBez[j].y); // move to next sampled point
                region_1.ellipse(pointsQBez[j].x, pointsQBez[j].y, thickness, Math.floor(thickness / 2), 0, 0, Math.PI * 2); // draw the ellipse
            }
    
            // create the region as clipping region
            ctx.clip(region_1);
    
            // set the color
            ctx.fillStyle = color_turquoise;
            ctx.strokeStyle = color_turquoise;
    
            // draw a rectangle over the whole canvas and fill with the color - will only fill the clipping region
            ctx.rect(0, 0, canvas.get(0).width, canvas.get(0).height);
            ctx.fill();
    
            ctx.restore();
        } else {
            console.log('A mask needs at least 3 points');
        }
    };
    

    // create a closed path between the mask path and the wall 
    function draw_quad_line(points, lineWidth = 1, draw_points = true) {
        ctx.beginPath()
        ctx.lineWidth = lineWidth;
        ctx.moveTo((points[0].x), points[0].y);

        if (draw_points) {
            ctx.fillRect(points[0].x, points[0].y, 2, 2)
            if (points.length < 4) {
                ctx.fillRect(points[0].x, points[0].y, 2, 2)
                ctx.fillRect(points[1].x, points[1].y, 2, 2)
            }
            else {
                ctx.fillRect(points[0].x, points[0].y, 2, 2)
            }
        }

        for (i = 1; i < points.length - 2; i++) {
            var xend = (points[i].x + points[i + 1].x) / 2;
            var yend = (points[i].y + points[i + 1].y) / 2;
            ctx.quadraticCurveTo(points[i].x, points[i].y, xend, yend);
            if (draw_points) {
                ctx.fillRect(points[i].x, points[i].y, 2, 2)
                ctx.fillRect(points[i + 1].x, points[i + 1].y, 2, 2)
            }

        }
        // curve through the last two points
        ctx.quadraticCurveTo(points[i].x, points[i].y, points[i + 1].x, points[i + 1].y);
        if (draw_points) {
            ctx.fillRect(points[i + 1].x, points[i + 1].y, 2, 2)
        }

        ctx.stroke();

    }

    function _getQBezierValue(t, p1, p2, p3) {
        var iT = 1 - t;
        return iT * iT * p1 + 2 * iT * t * p2 + t * t * p3;
    }

    function getQuadraticCurvePoint(startX, startY, cpX, cpY, endX, endY, position) {
        return {
            x: _getQBezierValue(position, startX, cpX, endX),
            y: _getQBezierValue(position, startY, cpY, endY)
        };
    }

    function plotQBez(pointsQBez, ptCount, Ax, Ay, Cx, Cy, Bx, By) {
        pointsQBez.push({ x: Ax, y: Ay });
        for (var i = 1; i < ptCount; i++) {
            var t = i / ptCount;
            pointsQBez.push(getQuadraticCurvePoint(Ax, Ay, Cx, Cy, Bx, By, t))
        }
        pointsQBez.push({ x: Bx, y: By });
        return (pointsQBez);
    };

});