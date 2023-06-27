import neuroglancer
from random import randint

# import the package app 
import synanno
from synanno import app

# for type hinting
import numpy as np

from typing import Union

def setup_ng(source: Union[np.typing.NDArray, str], target: Union[np.typing.NDArray, str]) -> None:
    ''' Setup function for the Neuroglancer (ng) that enables the recording and depiction 
        of center markers for newly identified FN instances.

        Args:
            source_img: The image volume depicted by the ng
            target_seg: The target volume depicted by the ng
    '''

    # generate a version number
    synanno.ng_version = str(randint(0, 32e+2))

    # setup a Tornado web server and create viewer instance
    neuroglancer.set_server_bind_address(
        bind_address=app.config['NG_IP'], bind_port=app.config['NG_PORT'])
    synanno.ng_viewer = neuroglancer.Viewer(token=synanno.ng_version)

    # specify the NG coordinate space
    res = neuroglancer.CoordinateSpace(
        names=['z', 'y', 'x'],
        units=['nm', 'nm', 'nm'],
        scales=[30, 8, 8])

    # config viewer: Add image layer, add segmentation mask layer, define position
    with synanno.ng_viewer.txn() as s:
        if isinstance(source, np.ndarray):
            s.layers.append(name='im', layer=neuroglancer.LocalVolume(
                data=source, dimensions=res, volume_type='image', voxel_offset=[0, 0, 0]))
        else:  # Assuming it's a string URL for the precomputed source
            s.layers.append(name='im', layer=neuroglancer.ImageLayer(
                source=source))

        if isinstance(target, np.ndarray):
            s.layers.append(name='gt', layer=neuroglancer.LocalVolume(
                data=target, dimensions=res, volume_type='segmentation', voxel_offset=[0, 0, 0]))
        else:  # Assuming it's a string URL for the precomputed source
            s.layers.append(name='gt', layer=neuroglancer.SegmentationLayer(
                source=target))
        
        # additional layer that lets the user mark the center of FPs
        s.layers.append(
            name="center_dot",
            layer=neuroglancer.LocalAnnotationLayer(
                dimensions=res,
                annotation_properties=[
                    neuroglancer.AnnotationPropertySpec(
                        id='color',
                        type='rgb',
                        default='red',
                    ),
                    neuroglancer.AnnotationPropertySpec(
                        id='size',
                        type='float32',
                        default=10,
                    ),
                    neuroglancer.AnnotationPropertySpec(
                        id='p_int8',
                        type='int8',
                        default=10,
                    ),
                    neuroglancer.AnnotationPropertySpec(
                        id='p_uint8',
                        type='uint8',
                        default=10,
                    ),
                ],
                annotations=[]
                ))

        # init the view position 
        s.position = [0, 0, 0]


    def center_annotation(s):
        ''' Ng action function that enables the recording and depiction 
            of center markers for newly identified FN instances. 
        '''

        # record the current mouse position
        center = s.mouse_voxel_coordinates

        # split the position and convert to int
        synanno.cz = int(center[0])
        synanno.cy = int(center[1])
        synanno.cx = int(center[2])

        # add a yellow dot at the recorded position with in the NG
        with synanno.ng_viewer.txn() as l:
            pt = neuroglancer.PointAnnotation(point=[int(center[0]), int(center[1]), int(center[2])], id=f'point{1}')
            l.layers['center_dot'].annotations.append(pt)


    # add the function as action
    synanno.ng_viewer.actions.add('center', center_annotation)
    with synanno.ng_viewer.config_state.txn() as s:
        # set the trigger for the action to the key 'c'
        s.input_event_bindings.viewer['keyc'] = 'center'

    print(
        f'Starting a Neuroglancer instance at {synanno.ng_viewer}, centered at x,y,x {0,0,0}')


