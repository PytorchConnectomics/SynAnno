$(document).ready(function () {

    // retrieve canvas and set 2D context
    var canvas_curve = $('canvas.curveCanvas')[0];
    var ctx_curve = canvas_curve.getContext('2d');

    // retrieve canvas and set 2D context
    var canvas_circle_pre = $('canvas.circleCanvasPre')[0];
    var ctx_circle_pre = canvas_circle_pre.getContext('2d');

    // retrieve canvas and set 2D context
    var canvas_circle_post = $('canvas.circleCanvasPost')[0];
    var ctx_circle_post = canvas_circle_post.getContext('2d');

    // set red as default color; used for the control points
    ctx_curve.fillStyle = '#FF0000';

    // initialize mouse position to zero
    var mousePosition = {
        x: 0,
        y: 0
    };


    // initialize global rectangle variable
    var rect_curve;
    var rect_circle;

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
    const turquoise = 'rgba(255, 0, 255, 0.7)';

    // set polarity default
    var color_turquoise = turquoise

    // variable for toggling the polarity

    // init image identifiers to null
    var page;
    var data_id;
    var label;

    // path where to save the custom masks - carful, this variable is also set in draw_module.js
    const base_mask_path = '/static/custom_masks/'


    // init pre and post synaptic coordinates
    var pre_CRD = false;
    var post_CRD = false;

    // make the last set coordinates globally available
    var x_syn_crd = null;
    var y_syn_crd = null;

    // last slice for which a mask got drawn
    var last_slice = null;

    // make sure that the modal is reset every time it get closed
    $('.modal').on('hidden.bs.modal', function () {
        // we only want to add the class d-none in case the module was actually closed and not just hidden
        // behind an other module
        if (! $('.modal:visible').length) {
            $('canvas.curveCanvas').addClass('d-none')   
            $('canvas.circleCanvasPre').addClass('d-none')
            $('canvas.circleCanvasPost').addClass('d-none')       
        }
    });

    // setup/reset the canvas when ever a draw button is clicked
    $('[id^="drawButton-"]').click(async function () {

        // retrieve the instance identifiers for later ajax calls
        [page, data_id, label] = $($(this)).attr('id').replace(/drawButton-/, '').split('-')

        // reset activation button
        $('#canvasButtonDrawMask').text('Draw Mask');
        $('#canvasButtonDrawMask').prop('disabled', false);

        // reset pre and post synaptic coordinates
        $('#canvasButtonPreCRD').text('Pre-Synaptic CRD');
        $('#canvasButtonPostCRD').text('Post-Synaptic CRD');
        $('#canvasButtonPreCRD').prop('disabled', false);
        $('#canvasButtonPostCRD').prop('disabled', false);

        // ensure that all options except the activate canvas button are disabled at start
        $('#canvasButtonFill').prop('disabled', true);
        $('#canvasButtonSplit').prop('disabled', true);
        $('#canvasButtonSave').prop('disabled', true);
        
        ctx_curve.restore() // restore default settings

        // reset red as default color; used for the control points
        ctx_curve.fillStyle = '#FF0000';
        
        clear_canvas(ctx_curve, canvas_curve) // clear previous output
        clear_canvas(ctx_circle_pre, canvas_circle_pre) // clear previous output
        clear_canvas(ctx_circle_post, canvas_circle_post) // clear previous output

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
    $('#canvasButtonPreCRD').on('click', function () {

        ctx_circle_pre.restore() // restore default settings

        // activate canvas for the first time after clicking a 'Mask' button
        if ($('canvas.circleCanvasPre').hasClass('d-none')) {
            // clear the canvas from previous drawn points
            clear_canvas(ctx_circle_pre, canvas_circle_pre)
            $('#imgDetails-EM-GT-circlePre').addClass('d-none'); // hide the previously drawn mask
            $('#canvasButtonPreCRD').text('Save'); // switch the button label to 'Reset'
            $('canvas.circleCanvasPre').removeClass('d-none') // change the visibility of the canvas
            $('#canvasButtonDrawMask').prop('disabled', true);
            $('#canvasButtonPostCRD').prop('disabled', true);
            
            // configure the canvas
            rect_circle = $('#imgDetails-EM')[0].getBoundingClientRect() // get absolute rect. of canvas
            $('canvas.circleCanvasPre')[0].width = rect_circle.width;
            $('canvas.circleCanvasPre')[0].height = rect_circle.height;
            // set the z-index of the canvas to 3 such that it is on top circleCanvasPre
            $('canvas.circleCanvasPre').css('z-index', 3);
            // set the z-index of the canvas to 2 such that it is on top curvcircleCanvasPosteCanvas
            $('canvas.circleCanvasPost').css('z-index', 2);
            // set the z-index of the curveCanvas to 1 such that it is behind the circleCanvasPre
            $('canvas.curveCanvas').css('z-index', 1);

            pre_CRD = true // activate pre-synaptic coordinates recording
            post_CRD = false // deactivate pre-synaptic coordinates recording
            split_mask = false // deactivate mask splitting
            draw_mask = false // activate mask drawing
            // reset canvas
        } else if ($('#canvasButtonPreCRD').text() == 'Save') {
            // clear canvas
            save_canvas(canvas_circle_pre, 'circlePre')
            $('#canvasButtonPreCRD').text('Pre-Synaptic CRD');
            // activate the postCRD button
            $('#canvasButtonPostCRD').prop('disabled', false);
            // enable the draw button
            $('#canvasButtonDrawMask').prop('disabled', false);

            pre_CRD = false;
        } else {
            // clear the canvas from previous drawn points
            clear_canvas(ctx_circle_pre, canvas_circle_pre)
            // set the z-index of the canvas to 3 such that it is on top circleCanvasPre
            $('canvas.circleCanvasPre').css('z-index', 3);
            // set the z-index of the canvas to 2 such that it is on top curvcircleCanvasPosteCanvas
            $('canvas.circleCanvasPost').css('z-index', 2);
            // set the z-index of the curveCanvas to 1 such that it is behind the circleCanvasPre
            $('canvas.curveCanvas').css('z-index', 1);


            // switch the button label to 'Save'
            $('#canvasButtonPreCRD').text('Save'); 
            
            // disable all options except the PreCRD button
            $('#canvasButtonDrawMask').prop('disabled', true);
            $('#canvasButtonPostCRD').prop('disabled', true);
            $('#canvasButtonFill').prop('disabled', true);
            $('#canvasButtonSplit').prop('disabled', true);
            $('#canvasButtonSave').prop('disabled', true);

            pre_CRD = true // activate pre-synaptic coordinates recording
            post_CRD = false // deactivate pre-synaptic coordinates recording
            split_mask = false // deactivate mask splitting
            draw_mask = false // activate mask drawing
        }
    });

    // on click activate canvas
    $('#canvasButtonPostCRD').on('click', function () {

        ctx_circle_post.restore() // restore default settings

        // activate canvas for the first time after clicking a 'Mask' button
        if ($('canvas.circleCanvasPost').hasClass('d-none')) {
            // clear the canvas from previous drawn points
            clear_canvas(ctx_circle_post, canvas_circle_post)
            $('#imgDetails-EM-GT-circlePost').addClass('d-none'); // hide the previously drawn mask
            $('#canvasButtonPostCRD').text('Save'); // switch the button label to 'Reset'
            $('canvas.circleCanvasPost').removeClass('d-none') // change the visibility of the canvas
            $('#canvasButtonDrawMask').prop('disabled', true);
            $('#canvasButtonPreCRD').prop('disabled', true);
            
            // configure the canvas
            rect_circle = $('#imgDetails-EM')[0].getBoundingClientRect() // get absolute rect. of canvas
            $('canvas.circleCanvasPost')[0].width = rect_circle.width;
            $('canvas.circleCanvasPost')[0].height = rect_circle.height;
            // set the z-index of the canvas to 3 such that it is on top curvcircleCanvasPosteCanvas
            $('canvas.circleCanvasPost').css('z-index', 3);
            // set the z-index of the canvas to 2 such that it is on top circleCanvasPre
            $('canvas.circleCanvasPre').css('z-index', 2);
            // set the z-index of the curveCanvas to 1 such that it is behind the circleCanvasPost
            $('canvas.curveCanvas').css('z-index', 1);


            pre_CRD = false // activate pre-synaptic coordinates recording
            post_CRD = true // deactivate pre-synaptic coordinates recording
            split_mask = false // deactivate mask splitting
            draw_mask = false // activate mask drawing
            // reset canvas

        } else if ($('#canvasButtonPostCRD').text() == 'Save') {
            // clear canvas
            save_canvas(canvas_circle_post, 'circlePost')
            // update button label
            $('#canvasButtonPostCRD').text('Post-Synaptic CRD');
            // activate the preCRD button
            $('#canvasButtonPreCRD').prop('disabled', false);
            // enable the draw button
            $('#canvasButtonDrawMask').prop('disabled', false);

            post_CRD = false;
        } else {
            // clear the canvas from previous drawn points
            clear_canvas(ctx_circle_post, canvas_circle_post)
            // set the z-index of the canvas to 3 such that it is on top curvcircleCanvasPosteCanvas
            $('canvas.circleCanvasPost').css('z-index', 3);
            // set the z-index of the canvas to 2 such that it is on top circleCanvasPre
            $('canvas.circleCanvasPre').css('z-index', 2);
            // set the z-index of the curveCanvas to 1 such that it is behind the circleCanvasPost
            $('canvas.curveCanvas').css('z-index', 1);


            // switch the button label to 'Reset'
            $('#canvasButtonPostCRD').text('Save'); 
            
            // disable all options except the PreCRD button
            $('#canvasButtonDrawMask').prop('disabled', true);
            $('#canvasButtonPreCRD').prop('disabled', true);
            $('#canvasButtonFill').prop('disabled', true);
            $('#canvasButtonSplit').prop('disabled', true);
            $('#canvasButtonSave').prop('disabled', true);

            pre_CRD = false // activate pre-synaptic coordinates recording
            post_CRD = true // deactivate pre-synaptic coordinates recording
            split_mask = false // deactivate mask splitting
            draw_mask = false // activate mask drawing
        }
    });
        

    // on click activate canvas
    $('#canvasButtonDrawMask').on('click', function () {

        clear_canvas(ctx_curve, canvas_curve) // clear previous output

        // clear buffer
        points = [] // reset the point list
        pointsQBez = [] // reset the pointsQBez list

        ctx_curve.restore() // restore default settings

        // activate canvas for the first time after clicking a 'Mask' button
        if ($('canvas.curveCanvas').hasClass('d-none')) {
            // clear the canvas from previous drawn points
            $('#imgDetails-EM-GT-curve').addClass('d-none'); // hide the previously drawn mask
            $('#canvasButtonDrawMask').text('Reset'); // switch the button label to 'Reset'
            $('canvas.curveCanvas').removeClass('d-none') // change the visibility of the canvas
            
            rect_curve = $('#imgDetails-EM')[0].getBoundingClientRect() // get absolute rect. of canvas
            $('canvas.curveCanvas')[0].width = rect_curve.width;
            $('canvas.curveCanvas')[0].height = rect_curve.height;
            // set the z-index of the canvas to 3 such that it is on top circleCanvasCanvas
            $('canvas.curveCanvas').css('z-index', 3);
            // set the z-index of the canvas to 2 such that it is on top curvcircleCanvasPosteCanvas
            $('canvas.circleCanvasPost').css('z-index', 2);
            // set the z-index of the canvas to 1 such that it is on top circleCanvasPre
            $('canvas.circleCanvasPre').css('z-index', 1);


            width_curve = canvas_curve.width // retrieve the width of the canvas_curve
            height = canvas_curve.height // retrieve the width of the canvas_curve

            split_mask = false // deactivate mask splitting
            draw_mask = true // activate mask drawing

            $('#canvasButtonPreCRD').prop('disabled', true);
            $('#canvasButtonPostCRD').prop('disabled', true);

            // reset canvas
        } else {
            // set the z-index of the canvas to 3 such that it is on top circleCanvasCanvas
            $('canvas.curveCanvas').css('z-index', 3);
            // set the z-index of the canvas to 2 such that it is on top curvcircleCanvasPosteCanvas
            $('canvas.circleCanvasPost').css('z-index', 2);
            // set the z-index of the canvas to 1 such that it is on top circleCanvasPre
            $('canvas.circleCanvasPre').css('z-index', 1);

            // disable all options except the activate canvas button
            $('#canvasButtonFill').prop('disabled', true);
            $('#canvasButtonSplit').prop('disabled', true);
            $('#canvasButtonSave').prop('disabled', true);
            $('#canvasButtonPreCRD').prop('disabled', true);
            $('#canvasButtonPostCRD').prop('disabled', true);

            points = [] // reset the point list
            pointsQBez = [] // reset the pointsQBez list
            split_mask = false // deactivate mask splitting
            draw_mask = true // activate mask drawing

        }
    });

    // activate event for splitting/erasing the curve
    $('#canvasButtonSplit').on('click', function () {
        ctx_curve.save() // save the canvas settings
        ctx_curve.globalCompositeOperation = 'destination-out'; // change the settings such that new input overwrites existing one
        split_mask = true;
    });

    // create the mask based on the drawn spline
    $('#canvasButtonFill').on('click', function () {
        ctx_curve.restore() // restore default settings
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
        $('#canvasButtonSplit').prop('disabled', false);
        $('#canvasButtonSave').prop('disabled', false);
    });

    // save the current mask
    $('#canvasButtonSave').on('click', async function () {
        save_canvas(canvas_curve, 'curve')
    });

    async function save_canvas(canvas, canvas_type) {
        var dataURL = canvas.toDataURL(); // retrieve the image from the canvas as a base64 encoding

        // the viewed instance slice value is set when scrolling through the individual slices of an instance
        var viewed_instance_slice = $('#rangeSlices').data('viewed_instance_slice');

        // send the base64 encoded image to the backend
        await $.ajax({
            type: 'POST',
            url: '/save_canvas',
            type: 'POST',
            data: { imageBase64: dataURL, data_id: data_id, page: page, viewed_instance_slice: viewed_instance_slice, canvas_type: canvas_type }
            // update the depicted mask with the newly drawn mask
        }).done(function (data) {

            data_json = JSON.parse(data.data); 

            // only update the circle_pre and circle_post slice number matches that of the latest drawn curve
            if (canvas_type == 'curve' || ((canvas_type == 'circlePre' || canvas_type == 'circlePost') && last_slice == viewed_instance_slice) || last_slice == null) {

                // handle to source image of the instance module            
                var em_source_image = '#img-source-' + page + '-' + data_id

                // handle to ground truth image of the instance module
                var em_target_image = '#img-target-' + canvas_type + '-' + page + '-' + data_id

                // create path to image
                var coordinates = data_json.Adjusted_Bbox.join('_')
                var img_index = data_json.Image_Index
                img_name = canvas_type + '_' + 'idx_' + img_index + '_slice_' + viewed_instance_slice + '_cor_' + coordinates + '.png'
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

                last_slice = viewed_instance_slice // update the last slice for which a mask was drawn
                
                // save the coordinates of the pre and post synaptic CRD
                if (canvas_type == 'circlePre' || canvas_type == 'circlePost') {
                    // send the coordinates to the backend
                    id = canvas_type == 'circlePre' ? 'pre' : 'post'
                    $.ajax({
                        type: 'POST',
                        url: '/save_pre_post_coordinates',
                        type: 'POST',
                        data: { x: x_syn_crd, y: y_syn_crd, z: viewed_instance_slice, data_id: data_id, page: page, id: id }
                    }).done(function (data) {
                        // check success of the request
                        if (data.success) {
                            console.log('Successfully saved ' + id + ' coordinates');
                        }
                    });
                };

                if (canvas_type == 'circlePre' || canvas_type == 'circlePost'){
                    // remove d-none class from em_target_image
                    $(em_target_image).removeClass('d-none');
                }else if (canvas_type == 'curve'){
                    // remove d-none from the pre and post button
                    $('#canvasButtonPreCRD').prop('disabled', false);
                    $('#canvasButtonPostCRD').prop('disabled', false);
                }
            }
        });
    }

    $('canvas.circleCanvasPre').on('click', function (e) {
        if (pre_CRD) {
            // clear previous drawn point
            clear_canvas(ctx_circle_pre, canvas_circle_pre)
            // get click position
            var pos = getXY(canvas_circle_pre, e, rect_circle)
            x_syn_crd = pos.x
            y_syn_crd = pos.y
            ctx_circle_pre.fillStyle = 'rgb(0, 255, 0)';
            ctx_circle_pre.beginPath();
            ctx_circle_pre.arc(x_syn_crd, y_syn_crd, 10, 0, 2 * Math.PI);
            ctx_circle_pre.fill();
            
            }
        });

    $('canvas.circleCanvasPost').on('click', function (e) {
        if (post_CRD) {

            // clear previous drawn point
            clear_canvas(ctx_circle_post, canvas_circle_post)

            var pos = getXY(canvas_circle_post, e, rect_circle)
            x_syn_crd = pos.x
            y_syn_crd = pos.y

            ctx_circle_post.fillStyle = 'rgb(0, 0, 255)';
            ctx_circle_post.beginPath();
            ctx_circle_post.arc(x_syn_crd, y_syn_crd, 10, 0, 2 * Math.PI);
            ctx_circle_post.fill();
        }
        });

    // if split_mask is set to true turns the mouse pointer in to a circular eraser
    $('canvas.curveCanvas').mousemove(function (event) {
        if (split_mask) {
            // detect possible changes in mouse position
            if ((mousePosition.x != event.clientX || mousePosition.y != event.clientY) && event.buttons == 1) {
                mousePosition.x = event.clientX;
                mousePosition.y = event.clientY;

                // Set global composite operation to destination-out
                var pos = getXY(canvas_curve, event, rect_curve)
                var x = pos.x
                var y = pos.y
                ctx_curve.strokeStyle = '#000';
                ctx_curve.beginPath();
                ctx_curve.moveTo(x + thickness, y)
                ctx_curve.ellipse(x, y, thickness, Math.floor(thickness / 2), 0, 0, Math.PI * 2)
                ctx_curve.fill();
            }
        }
    })

    // set start, end, and control points for curve that draws the mask
    $('canvas.curveCanvas').on('click', function (e) {
        if (draw_mask) {
            clear_canvas(ctx_curve, canvas_curve) // clear canvas
            ctx_curve.beginPath() // init path

            // get click position
            var pos = getXY(canvas_curve, e, rect_curve)
            var x = pos.x
            var y = pos.y

            // add new point to points list
            points.push({ x, y })

            // draw the line segments in case that the points list contains more then two points
            if (points.length > 2) {
                draw_quad_line(points)
                // activate the fill button should the length of point be greater 2
                $('#canvasButtonFill').prop('disabled', false);
            }
            // if the list only contains two points draw straight light
            else if (points.length > 1) {
                ctx_curve.moveTo((points[0].x), points[0].y);
                ctx_curve.fillRect(points[0].x, points[0].y, 2, 2) // mark start point with red rectangle 
                ctx_curve.fillRect(points[1].x, points[1].y, 2, 2) // mark end point with red rectangle
                ctx_curve.lineTo(points[0].x, points[0].y);
                ctx_curve.lineTo(points[1].x, points[1].y);
                ctx_curve.stroke();
            }
        } })

    // helper function for clearing the canvas
    function clear_canvas(ctx, canvas) {
        ctx.beginPath();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.stroke();
    }

    // helper function for calculating the relative mouse click based on the canvas expansion
    function getXY(current_canvas, evt, rect) {
        // using the absolute rect. of canvas
        return {
            x: (evt.clientX - rect.left) / (rect.right - rect.left) * current_canvas.width,
            y: (evt.clientY - rect.top) / (rect.bottom - rect.top) * current_canvas.height
        };
    }

    
    function fill_clip(color_turquoise, thickness, sample = false) {

        clear_canvas(ctx_curve, canvas_curve); // clear the canvas
        ctx_curve.beginPath(); // init new path
    
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
    
            ctx_curve.save(); // save the current settings
    
            let region_1 = new Path2D(); // define new region
    
            // for every point that was sampled draw a an ellipse with the point at its center
            for (let j = 0; j < pointsQBez.length; j++) {
                // the normal aspect ratio of a html5 canvas is 2/1 
                // since we have equal width and height, y is distorted by factor 2
                region_1.moveTo(pointsQBez[j].x + thickness, pointsQBez[j].y); // move to next sampled point
                region_1.ellipse(pointsQBez[j].x, pointsQBez[j].y, thickness, Math.floor(thickness / 2), 0, 0, Math.PI * 2); // draw the ellipse
            }
    
            // create the region as clipping region
            ctx_curve.clip(region_1);
    
            // set the color
            ctx_curve.fillStyle = color_turquoise;
            ctx_curve.strokeStyle = color_turquoise;
    
            // draw a rectangle over the whole canvas and fill with the color - will only fill the clipping region
            ctx_curve.rect(0, 0, canvas_curve.width, canvas_curve.height);
            ctx_curve.fill();
    
            ctx_curve.restore();
        } else {
            console.log('A mask needs at least 3 points');
        }
    };
    

    // create a closed path between the mask path and the wall 
    function draw_quad_line(points, lineWidth = 1, draw_points = true) {
        ctx_curve.beginPath()
        ctx_curve.lineWidth = lineWidth;
        ctx_curve.moveTo((points[0].x), points[0].y);

        if (draw_points) {
            ctx_curve.fillRect(points[0].x, points[0].y, 2, 2)
            if (points.length < 4) {
                ctx_curve.fillRect(points[0].x, points[0].y, 2, 2)
                ctx_curve.fillRect(points[1].x, points[1].y, 2, 2)
            }
            else {
                ctx_curve.fillRect(points[0].x, points[0].y, 2, 2)
            }
        }

        for (i = 1; i < points.length - 2; i++) {
            var xend = (points[i].x + points[i + 1].x) / 2;
            var yend = (points[i].y + points[i + 1].y) / 2;
            ctx_curve.quadraticCurveTo(points[i].x, points[i].y, xend, yend);
            if (draw_points) {
                ctx_curve.fillRect(points[i].x, points[i].y, 2, 2)
                ctx_curve.fillRect(points[i + 1].x, points[i + 1].y, 2, 2)
            }

        }
        // curve through the last two points
        ctx_curve.quadraticCurveTo(points[i].x, points[i].y, points[i + 1].x, points[i + 1].y);
        if (draw_points) {
            ctx_curve.fillRect(points[i + 1].x, points[i + 1].y, 2, 2)
        }

        ctx_curve.stroke();

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