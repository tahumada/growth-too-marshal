from unittest import mock

from astropy import time
from astropy import units as u
import gcn
import lxml.etree
import numpy as np
import pkg_resources

from .. import models
from ..flask import app
from ..gcn import handle, listen
from . import mock_download_file


@mock.patch('growth.too.tasks.skymaps.contour.run')
@mock.patch('growth.too.tasks.twilio.call_everyone')
@mock.patch('astropy.io.fits.file.download_file', mock_download_file)
def test_grb180116a_fin_pos(mock_call_everyone, mock_contour,
                            celery, database, flask, mail):
    # Read test GCN
    payload = pkg_resources.resource_string(
        __name__, 'data/GRB180116A_Fermi_GBM_Fin_Pos.xml')
    root = lxml.etree.fromstring(payload)

    # Run function under test
    handle(payload, root)

    dateobs = '2018-01-16T00:36:53'
    event = models.Event.query.get(dateobs)
    assert event is not None
    gcn_notice, = event.gcn_notices
    assert gcn_notice.content == payload
    assert gcn_notice.notice_type == gcn.NoticeType.FERMI_GBM_FIN_POS
    assert time.Time(gcn_notice.date) == time.Time('2018-01-16T00:46:05')
    assert gcn_notice.ivorn == 'ivo://nasa.gsfc.gcn/Fermi#GBM_Fin_Pos2018-01-16T00:36:52.81_537755817_0-026'  # noqa: E501
    assert gcn_notice.stream == 'Fermi'
    assert time.Time(gcn_notice.dateobs) - time.Time(dateobs) < 0.5 * u.second
    assert event.tags == ['Fermi', 'long', 'GRB']

    mock_call_everyone.assert_not_called()

    localization, = event.localizations
    assert np.isclose(localization.flat_2d.sum(), 1.0)

    telescope = 'ZTF'
    filt = ['g', 'r', 'g']
    exposuretimes = [300.0, 300.0, 300.0]
    doReferences, doDither = True, False
    filterScheduleType = 'block'
    schedule_type = 'greedy'
    probability = 0.9
    plan_name = "%s_%s_%d_%d_%s_%d_%d" % ("".join(filt), schedule_type,
                                          doDither, doReferences,
                                          filterScheduleType,
                                          exposuretimes[0],
                                          100*probability)
    plan = models.Plan.query.filter_by(plan_name=plan_name,
                                       telescope=telescope).one()

    assert time.Time(plan.dateobs) - time.Time(dateobs) < 0.5 * u.second

    exposures = models.PlannedObservation.query.filter_by(
            dateobs=event.dateobs,
            telescope=telescope,
            plan_name=plan.plan_name).all()

    for exposure in exposures:
        field_id = exposure.field_id
        assert np.all(np.array(field_id) < 907)
        assert np.all(np.array(exposure.exposure_time) > 0)
        assert np.all(np.array(exposure.weight) <= 1)


@mock.patch('growth.too.tasks.skymaps.contour.run')
@mock.patch('growth.too.tasks.tiles.tile')
@mock.patch('growth.too.tasks.skymaps.from_cone')
@mock.patch('growth.too.tasks.skymaps.download')
def test_grb180116a_multiple_gcns(mock_download, mock_from_cone, mock_tile,
                                  mock_contour, celery, database, flask, mail):
    """Test reading and ingesting all three GCNs. Make sure that there are
    no database conflicts."""
    for notice_type in ['Alert', 'Flt_Pos', 'Gnd_Pos', 'Fin_Pos']:
        filename = 'data/GRB180116A_Fermi_GBM_' + notice_type + '.xml'
        payload = pkg_resources.resource_string(__name__, filename)
        root = lxml.etree.fromstring(payload)
        handle(payload, root)


@mock.patch.dict(app.jinja_env.globals,
                 {'now': lambda: time.Time('2018-04-22T21:55:30').datetime})
@mock.patch('growth.too.tasks.twilio.text_everyone.run')
@mock.patch('growth.too.tasks.twilio.call_everyone.run')
@mock.patch('growth.too.tasks.skymaps.contour.run')
@mock.patch('growth.too.tasks.tiles.tile.run')
@mock.patch('growth.too.tasks.skymaps.from_cone.run')
@mock.patch('astropy.io.fits.file.download_file', mock_download_file)
def test_gbm_subthreshold(mock_from_cone, mock_tile, mock_contour,
                          mock_call_everyone, mock_text_everyone, celery,
                          database, flask, mail):
    """Test reading and ingesting all three GCNs. Make sure that there are
    no database conflicts."""
    filename = 'data/GRB180422.913_Subthreshold.xml'
    payload = pkg_resources.resource_string(__name__, filename)
    root = lxml.etree.fromstring(payload)
    handle(payload, root)

    event = models.Event.query.get('2018-04-22T21:54:11')
    assert event is not None
    gcn_notice, = event.gcn_notices
    assert gcn_notice.notice_type == gcn.NoticeType.FERMI_GBM_SUBTHRESH
    assert gcn_notice.stream == 'Fermi'
    assert event.tags == ['Fermi', 'short', 'transient']

    mock_text_everyone.assert_not_called()
    mock_call_everyone.assert_not_called()


@mock.patch('growth.too.tasks.skymaps.contour.run')
@mock.patch('growth.too.tasks.tiles.tile')
@mock.patch('growth.too.tasks.skymaps.from_cone')
def test_grb180116a_gnd_pos(mock_from_cone, mock_tile, mock_contour,
                            celery, database, flask, mail):
    # Read test GCN
    payload = pkg_resources.resource_string(
        __name__, 'data/GRB180116A_Fermi_GBM_Gnd_Pos.xml')
    root = lxml.etree.fromstring(payload)

    # Run function under test
    handle(payload, root)

    # Check that we didn't write the unhelpful "unknown" short/long class
    dateobs = '2018-01-16T00:36:53'
    event = models.Event.query.get(dateobs)
    assert event.tags == ['Fermi', 'GRB']


@mock.patch('growth.too.tasks.skymaps.contour.run')
@mock.patch('growth.too.tasks.tiles.tile')
@mock.patch('growth.too.tasks.skymaps.from_cone')
def test_amon_150529(mock_from_cone, mock_tile, mock_contour,
                     celery, database, flask, mail):
    # Read test GCN
    payload = pkg_resources.resource_string(
        __name__, 'data/AMON_150529.xml')
    root = lxml.etree.fromstring(payload)

    # Run function under test
    handle(payload, root)

    dateobs = '2015-05-29T02:17:28'
    event = models.Event.query.get(dateobs)
    assert event.tags == ['AMON']


@mock.patch('growth.too.tasks.skymaps.contour.run')
@mock.patch('growth.too.tasks.tiles.tile')
@mock.patch('growth.too.tasks.skymaps.from_cone')
def test_amon_151115(mock_from_cone, mock_tile, mock_contour,
                     celery, database, flask, mail):
    # Read test GCN
    payload = pkg_resources.resource_string(
        __name__, 'data/AMON_151115.xml')
    root = lxml.etree.fromstring(payload)

    # Run function under test
    handle(payload, root)

    dateobs = '2015-11-15T11:53:44'
    event = models.Event.query.get(dateobs)
    assert event.tags == ['AMON']


@mock.patch('gcn.listen')
def test_listen(mock_listen):
    # Run function under test
    listen()

    # Check that GCN listener was invoked
    assert mock_listen.called_once_with(handle=handle)
