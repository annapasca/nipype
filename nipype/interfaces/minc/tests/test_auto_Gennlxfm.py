# AUTO-GENERATED by tools/checkspecs.py - DO NOT EDIT
from ....testing import assert_equal
from ..minc import Gennlxfm


def test_Gennlxfm_inputs():
    input_map = dict(args=dict(argstr='%s',
    ),
    clobber=dict(argstr='-clobber',
    usedefault=True,
    ),
    environ=dict(nohash=True,
    usedefault=True,
    ),
    ident=dict(argstr='-ident',
    ),
    ignore_exception=dict(nohash=True,
    usedefault=True,
    ),
    like=dict(argstr='-like %s',
    ),
    output_file=dict(argstr='%s',
    genfile=True,
    hash_files=False,
    name_source=[u'like'],
    name_template='%s_gennlxfm.xfm',
    position=-1,
    ),
    step=dict(argstr='-step %s',
    ),
    terminal_output=dict(nohash=True,
    ),
    verbose=dict(argstr='-verbose',
    ),
    )
    inputs = Gennlxfm.input_spec()

    for key, metadata in list(input_map.items()):
        for metakey, value in list(metadata.items()):
            yield assert_equal, getattr(inputs.traits()[key], metakey), value


def test_Gennlxfm_outputs():
    output_map = dict(output_file=dict(),
    output_grid=dict(),
    )
    outputs = Gennlxfm.output_spec()

    for key, metadata in list(output_map.items()):
        for metakey, value in list(metadata.items()):
            yield assert_equal, getattr(outputs.traits()[key], metakey), value
