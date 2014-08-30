# coding: utf-8

import nipype.pipeline.engine as pe
import nipype.interfaces.utility as niu
import nipype.interfaces.fsl as fsl
import nipype.interfaces.ants as ants
import os

from .utils import *

def hmc_pipeline(name='motion_correct'):
    """
    HMC stands for head-motion correction.

    Creates a pipeline that corrects for head motion artifacts in dMRI sequences.
    It takes a series of diffusion weighted images and rigidly co-registers
    them to one reference image. Finally, the `b`-matrix is rotated accordingly [Leemans09]_
    making use of the rotation matrix obtained by FLIRT.

    Search angles have been limited to 3.5 degrees, based on results in [Yendiki13]_.

    A list of rigid transformation matrices is provided, so that transforms can be
    chained. This is useful to correct for artifacts with only one interpolation process (as
    previously discussed `here <https://github.com/nipy/nipype/pull/530#issuecomment-14505042>`_),
    and also to compute nuisance regressors as proposed by [Yendiki13]_.

    .. warning:: This workflow rotates the `b`-vectors, so please be advised
      that not all the dicom converters ensure the consistency between the resulting
      nifti orientation and the gradients table (e.g. dcm2nii checks it).

    .. admonition:: References

      .. [Leemans09] Leemans A, and Jones DK, `The B-matrix must be rotated when correcting
        for subject motion in DTI data <http://dx.doi.org/10.1002/mrm.21890>`_,
        Magn Reson Med. 61(6):1336-49. 2009. doi: 10.1002/mrm.21890.

      .. [Yendiki13] Yendiki A et al., `Spurious group differences due to head motion in
        a diffusion MRI study <http://dx.doi.org/10.1016/j.neuroimage.2013.11.027>`_.
        Neuroimage. 21(88C):79-90. 2013. doi: 10.1016/j.neuroimage.2013.11.027

    Example
    -------

    >>> from nipype.workflows.dmri.fsl.epi import motion_correct
    >>> hmc = motion_correct()
    >>> hmc.inputs.inputnode.in_file = 'diffusion.nii'
    >>> hmc.inputs.inputnode.in_bvec = 'diffusion.bvec'
    >>> hmc.inputs.inputnode.in_mask = 'mask.nii'
    >>> hmc.run() # doctest: +SKIP

    Inputs::

        inputnode.in_file - input dwi file
        inputnode.in_mask - weights mask of reference image (a file with data range \
in [0.0, 1.0], indicating the weight of each voxel when computing the metric.
        inputnode.in_bvec - gradients file (b-vectors)
        inputnode.ref_num (optional, default=0) index of the b0 volume that should be \
taken as reference

    Outputs::

        outputnode.out_file - corrected dwi file
        outputnode.out_bvec - rotated gradient vectors table
        outputnode.out_xfms - list of transformation matrices

    """
    inputnode = pe.Node(niu.IdentityInterface(fields=['in_file', 'ref_num', 'in_bvec',
                        'in_mask']), name='inputnode')
    split = pe.Node(fsl.Split(dimension='t'), name='SplitDWIs')
    pick_ref = pe.Node(niu.Select(), name='Pick_b0')
    flirt = pe.MapNode(fsl.FLIRT(interp='spline', cost='normmi',
                       cost_func = 'normmi', dof=6, bins=64, save_log=True,
                       searchr_x=[-4,4], searchr_y=[-4,4], searchr_z=[-4,4],
                       fine_search=1, coarse_search=10, padding_size=1),
                       name='CoRegistration', iterfield=['in_file'])
    rot_bvec = pe.Node(niu.Function(input_names=['in_bvec', 'in_matrix'],
                           output_names=['out_file'], function=rotate_bvecs),
                           name='Rotate_Bvec')
    merge = pe.Node(fsl.Merge(dimension='t'), name='MergeDWIs')
    outputnode = pe.Node(niu.IdentityInterface(fields=['out_file',
                         'out_bvec', 'out_xfms']),
                         name='outputnode')

    wf = pe.Workflow(name=name)
    wf.connect([
         (inputnode,  split,      [('in_file', 'in_file')])
        ,(split,      pick_ref,   [('out_files', 'inlist')])
        ,(inputnode,  pick_ref,   [(('ref_num', _checkrnum), 'index')])
        ,(inputnode,  flirt,      [('in_mask', 'ref_weight')])
        ,(split,      flirt,      [('out_files', 'in_file')])
        ,(inputnode,  rot_bvec,   [('in_bvec', 'in_bvec')])
        ,(flirt,      rot_bvec,   [('out_matrix_file', 'in_matrix')])
        ,(pick_ref,   flirt,      [('out', 'reference')])
        ,(flirt,      merge,      [('out_file', 'in_files')])
        ,(merge,      outputnode, [('merged_file', 'out_file')])
        ,(rot_bvec,   outputnode, [('out_file', 'out_bvec')])
        ,(flirt,      outputnode, [('out_matrix_file', 'out_xfms')])
    ])
    return wf

def ecc_pipeline(name='eddy_correct'):
    """
    ECC stands for Eddy currents correction.

    Creates a pipeline that corrects for artifacts induced by Eddy currents in dMRI
    sequences.
    It takes a series of diffusion weighted images and linearly co-registers
    them to one reference image (the average of all b0s in the dataset).

    DWIs are also modulated by the determinant of the Jacobian as indicated by [Jones10]_ and
    [Rohde04]_.

    A list of rigid transformation matrices can be provided, sourcing from a
    :func:`.motion_correct` workflow, to initialize registrations in a *motion free*
    framework.

    A list of affine transformation matrices is available as output, so that transforms
    can be chained (discussion
    `here <https://github.com/nipy/nipype/pull/530#issuecomment-14505042>`_).

    .. admonition:: References

      .. [Jones10] Jones DK, `The signal intensity must be modulated by the determinant of
        the Jacobian when correcting for eddy currents in diffusion MRI
        <http://cds.ismrm.org/protected/10MProceedings/files/1644_129.pdf>`_,
        Proc. ISMRM 18th Annual Meeting, (2010).

      .. [Rohde04] Rohde et al., `Comprehensive Approach for Correction of Motion and Distortion \
        in Diffusion-Weighted MRI \
        <http://stbb.nichd.nih.gov/pdf/com_app_cor_mri04.pdf>`_, MRM 51:103-114 (2004).

    Example
    -------

    >>> from nipype.workflows.dmri.fsl.epi import eddy_correct
    >>> ecc = eddy_correct()
    >>> ecc.inputs.inputnode.in_file = 'diffusion.nii'
    >>> ecc.inputs.inputnode.in_bval = 'diffusion.bval'
    >>> ecc.inputs.inputnode.in_mask = 'mask.nii'
    >>> ecc.run() # doctest: +SKIP

    Inputs::

        inputnode.in_file - input dwi file
        inputnode.in_mask - weights mask of reference image (a file with data range \
sin [0.0, 1.0], indicating the weight of each voxel when computing the metric.
        inputnode.in_bval - b-values table
        inputnode.in_xfms - list of matrices to initialize registration (from head-motion correction)

    Outputs::

        outputnode.out_file - corrected dwi file
        outputnode.out_xfms - list of transformation matrices
    """
    inputnode = pe.Node(niu.IdentityInterface(fields=['in_file', 'in_bval',
                        'in_mask', 'in_xfms']), name='inputnode')
    split = pe.Node(fsl.Split(dimension='t'), name='SplitDWIs')
    avg_b0 = pe.Node(niu.Function(input_names=['in_dwi', 'in_bval'],
                     output_names=['out_file'], function=b0_average), name='b0_avg')
    pick_dwi = pe.Node(niu.Select(), name='Pick_DWIs')
    flirt = pe.MapNode(fsl.FLIRT(no_search=True, interp='spline', cost='normmi',
                       cost_func = 'normmi', dof=12, bins=64, save_log=True,
                       padding_size=1), name='CoRegistration',
                       iterfield=['in_file', 'in_matrix_file'])
    initmat = pe.Node(niu.Function(input_names=['in_bval', 'in_xfms'],
                      output_names=['init_xfms'], function=_checkinitxfm),
                      name='InitXforms')

    mult = pe.MapNode(fsl.BinaryMaths(operation='mul'), name='ModulateDWIs',
                      iterfield=['in_file', 'operand_value'])
    thres = pe.MapNode(fsl.Threshold(thresh=0.0), iterfield=['in_file'],
                       name='RemoveNegative')

    get_mat = pe.Node(niu.Function(input_names=['in_bval', 'in_xfms'],
                      output_names=['out_files'], function=recompose_xfm),
                      name='GatherMatrices')
    merge = pe.Node(niu.Function(input_names=['in_dwi', 'in_bval', 'in_corrected'],
                    output_names=['out_file'], function=recompose_dwi), name='MergeDWIs')

    outputnode = pe.Node(niu.IdentityInterface(fields=['out_file', 'out_xfms']),
                         name='outputnode')

    wf = pe.Workflow(name=name)
    wf.connect([
         (inputnode,  split,      [('in_file', 'in_file')])
        ,(inputnode,  avg_b0,     [('in_file', 'in_dwi'),
                                   ('in_bval', 'in_bval')])
        ,(inputnode,  merge,      [('in_file', 'in_dwi'),
                                   ('in_bval', 'in_bval')])
        ,(inputnode,  initmat,    [('in_xfms', 'in_xfms'),
                                   ('in_bval', 'in_bval')])
        ,(inputnode,  get_mat,    [('in_bval', 'in_bval')])
        ,(split,      pick_dwi,   [('out_files', 'inlist')])
        ,(inputnode,  pick_dwi,   [(('in_bval', _nonb0), 'index')])
        ,(inputnode,  flirt,      [('in_mask', 'ref_weight')])
        ,(avg_b0,     flirt,      [('out_file', 'reference')])
        ,(pick_dwi,   flirt,      [('out', 'in_file')])
        ,(initmat,    flirt,      [('init_xfms', 'in_matrix_file')])
        ,(flirt,      get_mat,    [('out_matrix_file', 'in_xfms')])
        ,(flirt,      mult,       [(('out_matrix_file',_xfm_jacobian), 'operand_value')])
        ,(flirt,      mult,       [('out_file', 'in_file')])
        ,(mult,       thres,      [('out_file', 'in_file')])
        ,(thres,      merge,      [('out_file', 'in_corrected')])
        ,(get_mat,    outputnode, [('out_files', 'out_xfms')])
        ,(merge,      outputnode, [('out_file', 'out_file')])
    ])
    return wf

def sdc_fmb(name='fmb_correction',
            fugue_params=dict(smooth3d=2.0, despike_2dfilter=True),
            bmap_params=dict(delta_te=2.46e-3),
            epi_params=dict()):
    """
    SDC stands for susceptibility distortion correction. FMB stands for fieldmap-based.

    The fieldmap based method (FMB) implements SDC by using a mapping of the B0 field
    as proposed by [Jezzard95]_. This workflow uses the implementation of FSL
    (`FUGUE <http://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FUGUE>`_). Phase unwrapping is performed
    using `PRELUDE <http://fsl.fmrib.ox.ac.uk/fsl/fsl-4.1.9/fugue/prelude.html>`_
    [Jenkinson03]_.


    .. admonition:: References

      .. [Jezzard95] Jezzard P, and Balaban RS, `Correction for geometric distortion in echo
        planar images from B0 field variations <http://dx.doi.org/10.1002/mrm.1910340111>`_,
        MRM 34(1):65-73. (1995). doi: 10.1002/mrm.1910340111.

      .. [Jenkinson03] Jenkinson M., `Fast, automated, N-dimensional phase-unwrapping algorithm
        <http://dx.doi.org/10.1002/mrm.10354>`_, MRM 49(1):193-197, 2003, doi: 10.1002/mrm.10354.

    """
    inputnode = pe.Node(niu.IdentityInterface(fields=['in_file', 'in_bval', 'in_mask',
                        'bmap_pha', 'bmap_mag']),
                        name='inputnode')


    firstmag = pe.Node(fsl.ExtractROI(t_min=0, t_size=1), name='GetFirst')
    n4 = pe.Node(ants.N4BiasFieldCorrection(dimension=3), name='Bias')
    bet = pe.Node(fsl.BET(frac=0.4, mask=True), name='BrainExtraction')
    dilate = pe.Node(fsl.maths.MathsCommand(nan2zeros=True,
                     args='-kernel sphere 5 -dilM'), name='MskDilate')
    pha2rads = pe.Node(niu.Function(input_names=['in_file'], output_names=['out_file'],
                      function=siemens2rads), name='PreparePhase')
    prelude = pe.Node(fsl.PRELUDE(process3d=True), name='PhaseUnwrap')
    rad2rsec = pe.Node(niu.Function(input_names=['in_file', 'delta_te'],
                       output_names=['out_file'], function=rads2radsec), name='ToRadSec')
    rad2rsec.inputs.delta_te = bmap_params['delta_te']

    avg_b0 = pe.Node(niu.Function(input_names=['in_dwi', 'in_bval'],
                     output_names=['out_file'], function=b0_average), name='b0_avg')

    flirt = pe.Node(fsl.FLIRT(interp='spline', cost='normmi', cost_func='normmi',
                    dof=6, bins=64, save_log=True, padding_size=10,
                    searchr_x=[-4,4], searchr_y=[-4,4], searchr_z=[-4,4],
                    fine_search=1, coarse_search=10),
                    name='BmapMag2B0')
    applyxfm = pe.Node(fsl.ApplyXfm(interp='spline', padding_size=10, apply_xfm=True),
                       name='BmapPha2B0')

    pre_fugue = pe.Node(fsl.FUGUE(save_fmap=True), name='PreliminaryFugue')
    demean = pe.Node(niu.Function(input_names=['in_file', 'in_mask'],
                     output_names=['out_file'], function=demean_image),
                     name='DemeanFmap')

    cleanup = cleanup_edge_pipeline()

    wf = pe.Workflow(name=name)
    wf.connect([
         (inputnode,    pha2rads,  [('bmap_pha', 'in_file')])
        ,(inputnode,    firstmag,  [('bmap_mag', 'in_file')])
        ,(inputnode,    avg_b0,    [('in_file', 'in_dwi'),
                                    ('in_bval', 'in_bval')])
        ,(firstmag,     n4,        [('roi_file', 'input_image')])
        ,(n4,           bet,       [('output_image', 'in_file')])
        ,(bet,          dilate,    [('mask_file', 'in_file')])
        ,(pha2rads,     prelude,   [('out_file', 'phase_file')])
        ,(n4,           prelude,   [('output_image', 'magnitude_file')])
        ,(dilate,       prelude,   [('out_file', 'mask_file')])
        ,(prelude,      rad2rsec,  [('unwrapped_phase_file', 'in_file')])

        ,(avg_b0,       flirt,     [('out_file', 'reference')])
        ,(inputnode,    flirt,     [('in_mask', 'ref_weight')])
        ,(n4,           flirt,     [('output_image', 'in_file')])
        ,(dilate,       flirt,     [('out_file', 'in_weight')])

        ,(avg_b0,       applyxfm,  [('out_file', 'reference')])
        ,(rad2rsec,     applyxfm,  [('out_file', 'in_file')])
        ,(flirt,        applyxfm,  [('out_matrix_file', 'in_matrix_file')])

        ,(applyxfm,     pre_fugue, [('out_file', 'fmap_in_file')])
        ,(inputnode,    pre_fugue, [('in_mask', 'mask_file')])

        ,(pre_fugue,    demean,    [('fmap_out_file', 'in_file')])
        ,(inputnode,    demean,    [('in_mask', 'in_mask')])

        ,(demean,       cleanup,   [('out_file', 'inputnode.in_file')])
        ,(inputnode,    cleanup,   [('in_mask', 'inputnode.in_mask')])
    ])
    return wf


def _checkrnum(ref_num):
    from nipype.interfaces.base import isdefined
    if (ref_num is None) or not isdefined(ref_num):
        return 0
    return ref_num

def _checkinitxfm(in_bval, in_xfms=None):
    from nipype.interfaces.base import isdefined
    import numpy as np
    import os.path as op
    bvals = np.loadtxt(in_bval)
    non_b0 = np.where(bvals!=0)[0].tolist()

    init_xfms = []
    if (in_xfms is None) or (not isdefined(in_xfms)) or (len(in_xfms)!=len(bvals)):
        for i in non_b0:
            xfm_file = op.abspath('init_%04d.mat' % i)
            np.savetxt(xfm_file, np.eye(4))
            init_xfms.append(xfm_file)
    else:
        for i in non_b0:
            init_xfms.append(in_xfms[i])
    return init_xfms

def _nonb0(in_bval):
    import numpy as np
    bvals = np.loadtxt(in_bval)
    return np.where(bvals!=0)[0].tolist()

def _xfm_jacobian(in_xfm):
    import numpy as np
    from math import fabs
    return [fabs(np.linalg.det(np.loadtxt(xfm))) for xfm in in_xfm]
