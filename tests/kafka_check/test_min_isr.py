# -*- coding: utf-8 -*-
# Copyright 2016 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import mock
from kafka.common import PartitionMetadata

from kafka_utils.kafka_check.commands.min_isr import _get_min_isr
from kafka_utils.kafka_check.commands.min_isr import _prepare_output
from kafka_utils.kafka_check.commands.min_isr import _process_metadata_response


TOPICS_STATE = {
    'topic_0': {
        0: PartitionMetadata(
            topic='topic_0',
            partition=0,
            leader=170396635,
            replicas=(170396635, 170398981),
            isr=(170398981,),
            error=0,
        ),
    },
    'topic_1': {
        0: PartitionMetadata(
            topic='topic_1',
            partition=0,
            leader=170396635,
            replicas=(170396635, 170398981),
            isr=(170396635, 170398981),
            error=0,
        ),
    },
}

NOT_IN_SYNC_PARTITIONS = [
    {
        'isr': 1,
        'min_isr': 3,
        'topic': 'topic_0',
        'partition': 0,
    },
    {
        'isr': 2,
        'min_isr': 3,
        'topic': 'topic_1',
        'partition': 0,
    },
]


def test_get_min_isr_empty():
    TOPIC_CONFIG_WITHOUT_MIN_ISR = {'version': 1, 'config': {'retention.ms': '86400000'}}
    attrs = {'get_topic_config.return_value': TOPIC_CONFIG_WITHOUT_MIN_ISR}
    zk_mock = mock.MagicMock(**attrs)

    min_isr = _get_min_isr(zk_mock, 'topic_0')

    zk_mock.get_topic_config.assert_called_once_with('topic_0')
    assert min_isr is None


def test_get_min_isr():
    TOPIC_CONFIG_WITH_MIN_ISR = {
        'version': 1,
        'config': {'retention.ms': '86400000', 'min.insync.replicas': '3'},
    }
    attrs = {'get_topic_config.return_value': TOPIC_CONFIG_WITH_MIN_ISR}
    zk_mock = mock.MagicMock(**attrs)

    min_isr = _get_min_isr(zk_mock, 'topic_0')

    zk_mock.get_topic_config.assert_called_once_with('topic_0')
    assert min_isr == 3


def test_process_metadata_response_empty():
    result = _process_metadata_response(
        topics={},
        zk=None,
        default_min_isr=None,
    )

    assert result == []


@mock.patch(
    'kafka_utils.kafka_check.commands.min_isr._get_min_isr',
    return_value=1,
    autospec=True,
)
def test_run_command_all_ok(min_isr_mock):
    result = _process_metadata_response(
        topics=TOPICS_STATE,
        zk=None,
        default_min_isr=None,
    )

    assert result == []


@mock.patch(
    'kafka_utils.kafka_check.commands.min_isr._get_min_isr',
    return_value=None,
    autospec=True,
)
def test_run_command_all_ok_without_min_isr_in_zk(min_isr_mock):
    result = _process_metadata_response(
        topics=TOPICS_STATE,
        zk=None,
        default_min_isr=None,
    )

    assert result == []


@mock.patch(
    'kafka_utils.kafka_check.commands.min_isr._get_min_isr',
    return_value=None,
    autospec=True,
)
def test_run_command_with_default_min_isr(min_isr_mock):
    result = _process_metadata_response(
        topics=TOPICS_STATE,
        zk=None,
        default_min_isr=1,
    )

    assert result == []


@mock.patch(
    'kafka_utils.kafka_check.commands.min_isr._get_min_isr',
    return_value=None,
    autospec=True,
)
def test_run_command_with_fail_with_default_min_isr(min_isr_mock):
    result = _process_metadata_response(
        topics=TOPICS_STATE,
        zk=None,
        default_min_isr=2,
    )
    p0 = {
        'isr': 1,
        'min_isr': 2,
        'topic': 'topic_0',
        'partition': 0,
    }

    assert result == [p0]


@mock.patch(
    'kafka_utils.kafka_check.commands.min_isr._get_min_isr',
    return_value=3,
    autospec=True,
)
def test_run_command_all_fail(min_isr_mock):
    result = _process_metadata_response(
        topics=TOPICS_STATE,
        zk=None,
        default_min_isr=1,
    )

    assert sorted(result) == sorted(NOT_IN_SYNC_PARTITIONS)


def test_prepare_output_ok_no_json_no_verbose():
    assert _prepare_output([], False, False) == "All replicas in sync."


def test_prepare_output_ok_json_no_verbose():
    assert _prepare_output([], True, False) == {'partitions_count': 0}


def test_prepare_output_ok_no_json_verbose():
    assert _prepare_output([], False, True) == "All replicas in sync."


def test_prepare_output_ok_json_verbose():
    origin = {
        'partitions_count': 0,
        'partitions': [],
    }
    assert _prepare_output([], True, True) == origin


def test_prepare_output_critical_no_json_no_verbose():
    origin = (
        "2 partition(s) have the number of replicas in "
        "sync that is lower than the specified min ISR."
    )
    assert _prepare_output(NOT_IN_SYNC_PARTITIONS, False, False) == origin


def test_prepare_output_critical_json_no_verbose():
    origin = {'partitions_count': 2}
    assert _prepare_output(NOT_IN_SYNC_PARTITIONS, True, False) == origin


def test_prepare_output_critical_no_json_verbose():
    origin = (
        "2 partition(s) have the number of replicas in "
        "sync that is lower than the specified min ISR.\n"
        "partitions:\n"
        "isr=1 is lower than min_isr=3 for topic_0:0\n"
        "isr=2 is lower than min_isr=3 for topic_1:0"
    )
    assert _prepare_output(NOT_IN_SYNC_PARTITIONS, False, True) == origin


def test_prepare_output_critical_json_verbose():
    origin = {
        'partitions_count': 2,
        'partitions': [
            {
                'isr': 1,
                'min_isr': 3,
                'partition': 0,
                'topic': 'topic_0'
            },
            {
                'isr': 2,
                'min_isr': 3,
                'partition': 0,
                'topic': 'topic_1'
            }
        ],
    }
    assert _prepare_output(NOT_IN_SYNC_PARTITIONS, True, True) == origin
