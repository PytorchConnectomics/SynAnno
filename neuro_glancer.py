import neuroglancer
import numpy as np
import imageio
import h5py
import argparse
import tifffile

# EM data
#seg_paths="/n/pfister_lab2/Lab/leander/em2exm/img_toolbox/em_seg_dorsal_crop_volume_infer_dense.h5"

## Real EM data
#img_paths="/n/pfister_lab2/Lab/leander/em2exm/img_toolbox/em_img_dorsal_crop_volume_infer_dense.h5"

## Syn. EM data
##img_paths="/n/pfister_lab2/Lab/leander/em2exm/img_toolbox/exm_img_merged_dorsal_ccgan__dorsal_crop_dense__vanilla__20E_15DE.h5"
##img_paths="/n/pfister_lab2/Lab/leander/em2exm/img_toolbox/exm_img_merged_dorsal_ccgan__dorsal_crop_dense__vanilla__25E_20DE.h5"
##img_paths="/n/pfister_lab2/Lab/leander/em2exm/img_toolbox/exm_img_merged_dorsal_crop_volume_infer.h5"

# ExM data 
img_paths='/n/pfister_lab2/Lab/leander/em2exm/pytorch_connectomics/datasets/inference/merged_256_not_filtered_dorsal_b.h5'

## Seg ccgan_dorsal_crop_volume_small__train__segmodel
#seg_paths='/n/pfister_lab2/Lab/leander/em2exm/slurm_jobs/ccgan_dorsal_crop_volume_small__train__segmodel/segment/dorsal_b/bcd_watershed_result.h5'
seg_paths='/n/pfister_lab2/Lab/leander/em2exm/slurm_jobs/seg___volume_small__from__dens_van_20E_15DE__train_segmodel/segment/dorsal_b/bcd_watershed_result.h5'


if __name__=='__main__':
    parser = argparse.ArgumentParser(description='H5 file settings')

    parser.add_argument('--port', type=str, default='main', help='segmentation masks')
    parser.add_argument('--imgs', type=str, default='main', help='images')
    parser.add_argument('--segs', type=str, default='main', help='segmentation masks')
    parser.add_argument('--version', type=str, help='version identifier')
    parser.add_argument('--ox', type=float, default=0.0, help='start postion origin x')
    parser.add_argument('--oy', type=float, default=0.0, help='start postion origin y')
    parser.add_argument('--oz', type=float, default=0.0, help='start postion origin z')

    # retrive the args
    args = parser.parse_args()

    ip = 'localhost' #or public IP of the machine for sharable display
    port = args.port #change to an unused port number
    neuroglancer.set_server_bind_address(bind_address=ip,bind_port=port)
    viewer=neuroglancer.Viewer(token=args.version)

    res = neuroglancer.CoordinateSpace(
        names=['z', 'y', 'x'],
        units=['nm', 'nm', 'nm'],
        scales=[1000, 333, 333])

    def load_data(filename, dtype):
        if filename.split(".")[-1] == "h5":
            f = h5py.File(filename, 'r')
            data = np.array(f['main']).astype(dtype)
            f.close()
            print(filename, data.shape, data.shape)
        elif filename.split(".")[-1] == "tif":
            f = tifffile.TiffFile(filename)
            data = np.asarray([img.asarray() for img in f.pages[:]])
        else:
            raise TypeError("The file ending must either be h5 or tif")
        return data

    print('load im and gt segmentation')
    im = load_data(args.imgs, np.uint8)
    gt = load_data(args.segs, np.uint32)

    # show half of the segmentation indices
    indices = np.unique(gt)[1:]

    def ngLayer(data,res,oo=[0,0,0],tt='segmentation'):
        return neuroglancer.LocalVolume(data,dimensions=res,volume_type=tt,voxel_offset=oo)

    with viewer.txn() as s:
        s.layers.append(name='im',layer=ngLayer(im,res,tt='image'))
        s.layers.append(name='gt',layer=ngLayer(gt,res,tt='segmentation'))
        s.position = [args.oz,args.oy,args.ox]

    print(viewer)