import math
import os
import re
from datetime import (
    datetime,
    timezone,
)

import pytest
from e2e.conftest import extract_pages
from e2e.data import (
    FILE_SERIES_PATHS,
    FILE_SERIES_STEPS,
    FLOAT_SERIES_PATHS,
    HISTOGRAM_SERIES_PATHS,
    NUMBER_OF_STEPS,
    PATH,
    STRING_SERIES_PATHS,
    TEST_DATA,
)

from neptune_fetcher.exceptions import NeptuneProjectInaccessible
from neptune_fetcher.internal.filters import (
    _AttributeFilter,
    _AttributeNameFilter,
)
from neptune_fetcher.internal.identifiers import (
    AttributeDefinition,
    ProjectIdentifier,
    RunIdentifier,
    SysId,
)
from neptune_fetcher.internal.retrieval.attribute_definitions import fetch_attribute_definitions_single_filter
from neptune_fetcher.internal.retrieval.attribute_types import (
    FloatSeriesAggregations,
    HistogramSeriesAggregations,
    StringSeriesAggregations,
)
from neptune_fetcher.internal.retrieval.attribute_values import (
    AttributeValue,
    fetch_attribute_values,
)

NEPTUNE_PROJECT = os.getenv("NEPTUNE_E2E_PROJECT")


def test_fetch_attribute_definitions_project_does_not_exist(client, project):
    workspace, project = project.project_identifier.split("/")
    project_identifier = ProjectIdentifier(f"{workspace}/does-not-exist")

    attribute_filter = _AttributeFilter(name_eq="sys/name", type_in=["string"])
    with pytest.raises(NeptuneProjectInaccessible):
        extract_pages(
            fetch_attribute_definitions_single_filter(
                client,
                [project_identifier],
                attribute_filter=attribute_filter,
                run_identifiers=None,
            )
        )


def test_fetch_attribute_definitions_workspace_does_not_exist(client, project):
    project_identifier = ProjectIdentifier("this-workspace/does-not-exist")

    attribute_filter = _AttributeFilter(name_eq="sys/name", type_in=["string"])
    with pytest.raises(NeptuneProjectInaccessible):
        extract_pages(
            fetch_attribute_definitions_single_filter(
                client,
                [project_identifier],
                attribute_filter=attribute_filter,
                run_identifiers=None,
            )
        )


def test_fetch_attribute_definitions_single_string(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(name_eq="sys/name", type_in=["string"])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client, [project_identifier], [experiment_identifier], attribute_filter=attribute_filter
        )
    )

    # then
    assert attributes == [AttributeDefinition("sys/name", "string")]


def test_fetch_attribute_definitions_does_not_exist(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(name_eq="does-not-exist", type_in=["string"])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert attributes == []


def test_fetch_attribute_definitions_two_strings(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(name_eq=["sys/name", "sys/owner"], type_in=["string"])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert_items_equal(
        attributes,
        [
            AttributeDefinition("sys/name", "string"),
            AttributeDefinition("sys/owner", "string"),
        ],
    )


@pytest.mark.parametrize(
    "path, type_in",
    [
        (FLOAT_SERIES_PATHS[0], "float_series"),
        (STRING_SERIES_PATHS[0], "string_series"),
        (FILE_SERIES_PATHS[0], "file_series"),
        (HISTOGRAM_SERIES_PATHS[0], "histogram_series"),
    ],
)
def test_fetch_attribute_definitions_single_series(client, project, experiment_identifier, path, type_in):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(name_eq=path, type_in=[type_in])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert attributes == [AttributeDefinition(path, type_in)]


def test_fetch_attribute_definitions_all_types(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier
    all_attrs = [
        (f"{PATH}/int-value", "int"),
        (f"{PATH}/float-value", "float"),
        (f"{PATH}/str-value", "string"),
        (f"{PATH}/bool-value", "bool"),
        (f"{PATH}/datetime-value", "datetime"),
        (FLOAT_SERIES_PATHS[0], "float_series"),
        (STRING_SERIES_PATHS[0], "string_series"),
        (FILE_SERIES_PATHS[0], "file_series"),
        (HISTOGRAM_SERIES_PATHS[0], "histogram_series"),
        (f"{PATH}/files/file-value.txt", "file"),
        ("sys/tags", "string_set"),
    ]

    #  when
    attribute_filter = _AttributeFilter(name_eq=[name for name, _ in all_attrs])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    expected_definitions = [AttributeDefinition(name, type) for name, type in all_attrs]
    assert_items_equal(attributes, expected_definitions)


def test_fetch_attribute_definitions_no_type_in(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(name_eq="sys/name")
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert attributes == [AttributeDefinition("sys/name", "string")]


def test_fetch_attribute_definitions_regex_matches_all(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(
        must_match_any=[_AttributeNameFilter(must_match_regexes=["sys/.*_time"])],
        type_in=["datetime"],
    )
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert_items_equal(
        attributes,
        [
            AttributeDefinition("sys/creation_time", "datetime"),
            AttributeDefinition("sys/modification_time", "datetime"),
            AttributeDefinition("sys/ping_time", "datetime"),
        ],
    )


def test_fetch_attribute_definitions_regex_matches_none(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(
        must_match_any=[
            _AttributeNameFilter(
                must_match_regexes=["sys/.*_time"],
                must_not_match_regexes=["modification"],
            ),
        ],
        type_in=["datetime"],
    )
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert_items_equal(
        attributes,
        [
            AttributeDefinition("sys/creation_time", "datetime"),
            AttributeDefinition("sys/ping_time", "datetime"),
        ],
    )


def test_fetch_attribute_definitions_regex_must_match_any_empty(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(type_in=["datetime"], must_match_any=[])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert_items_equal(
        attributes,
        [],
    )


def test_fetch_attribute_definitions_regex_must_match_any_single(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(
        type_in=["datetime"],
        must_match_any=[
            _AttributeNameFilter(
                must_match_regexes=["sys/.*_time"],
            ),
            _AttributeNameFilter(),
        ],
    )
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert_items_equal(
        attributes,
        [
            AttributeDefinition("sys/creation_time", "datetime"),
            AttributeDefinition("sys/modification_time", "datetime"),
            AttributeDefinition("sys/ping_time", "datetime"),
        ],
    )


def test_fetch_attribute_definitions_regex_must_match_any_multiple(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(
        type_in=["string", "datetime"],
        must_match_any=[
            _AttributeNameFilter(must_match_regexes=["sys/.*_time"], must_not_match_regexes=["modification"]),
            _AttributeNameFilter(
                must_match_regexes=["sys/name"],
            ),
        ],
    )
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert_items_equal(
        attributes,
        [
            AttributeDefinition("sys/name", "string"),
            AttributeDefinition("sys/creation_time", "datetime"),
            AttributeDefinition("sys/ping_time", "datetime"),
        ],
    )


def test_fetch_attribute_definitions_multiple_projects(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier
    project_identifier_2 = f"{project_identifier}-does-not-exist"

    #  when
    attribute_filter = _AttributeFilter(name_eq="sys/name", type_in=["string"])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier, project_identifier, project_identifier_2],
            [experiment_identifier],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert attributes == [AttributeDefinition("sys/name", "string")]


def test_fetch_attribute_definitions_paging(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(
        must_match_any=[_AttributeNameFilter(must_match_regexes=["sys/.*_time"])],
        type_in=["datetime"],
    )
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [experiment_identifier],
            attribute_filter=attribute_filter,
            batch_size=1,
        )
    )

    # then
    assert_items_equal(
        attributes,
        [
            AttributeDefinition("sys/creation_time", "datetime"),
            AttributeDefinition("sys/modification_time", "datetime"),
            AttributeDefinition("sys/ping_time", "datetime"),
        ],
    )


def test_fetch_attribute_definitions_experiment_identifier_none(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(name_eq="sys/name", type_in=["string"])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            None,
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert attributes == [AttributeDefinition("sys/name", "string")]


def test_fetch_attribute_definitions_experiment_identifier_empty(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    attribute_filter = _AttributeFilter(name_eq="sys/name", type_in=["string"])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            [],
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert attributes == []


def test_fetch_attribute_values_single_string(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [AttributeDefinition("sys/name", "string")],
        )
    )

    # then
    assert values == [
        AttributeValue(AttributeDefinition("sys/name", "string"), TEST_DATA.experiment_names[0], experiment_identifier)
    ]


def test_fetch_attribute_values_two_strings(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    values: list[AttributeValue] = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [
                AttributeDefinition("sys/name", "string"),
                AttributeDefinition("sys/owner", "string"),
            ],
        )
    )

    # then
    assert set(value.attribute_definition for value in values) == {
        AttributeDefinition("sys/name", "string"),
        AttributeDefinition("sys/owner", "string"),
    }


def test_fetch_attribute_values_single_float_series_all_aggregations(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier
    path = FLOAT_SERIES_PATHS[0]

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [AttributeDefinition(path, "float_series")],
        )
    )

    # then
    data = TEST_DATA.experiments[0].float_series[path]
    average = sum(data) / len(data)
    aggregates = FloatSeriesAggregations(
        last=data[-1],
        min=min(data),
        max=max(data),
        average=average,
        variance=sum((value - average) ** 2 for value in data) / len(data),
    )
    assert len(values) == 1
    assert values[0].attribute_definition == AttributeDefinition(path, "float_series")
    assert values[0].run_identifier == experiment_identifier
    assert values[0].value.last == aggregates.last
    assert values[0].value.min == aggregates.min
    assert values[0].value.max == aggregates.max
    assert values[0].value.average == aggregates.average
    assert math.isclose(values[0].value.variance, aggregates.variance, rel_tol=1e-6)


def test_fetch_attribute_values_single_string_series_all_aggregations(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier
    path = STRING_SERIES_PATHS[0]

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [AttributeDefinition(path, "string_series")],
        )
    )

    # then
    data = TEST_DATA.experiments[0].string_series[path]
    aggregates = StringSeriesAggregations(
        last=data[-1],
        last_step=NUMBER_OF_STEPS - 1,
    )
    assert values == [AttributeValue(AttributeDefinition(path, "string_series"), aggregates, experiment_identifier)]


def test_fetch_attribute_values_single_file_series_all_aggregations(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier
    path = FILE_SERIES_PATHS[0]
    attribute_definition = AttributeDefinition(path, "file_series")

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [attribute_definition],
        )
    )

    # then
    assert len(values) == 1
    value = values[0]
    assert value.attribute_definition == attribute_definition
    aggregate = value.value
    assert aggregate.last_step == FILE_SERIES_STEPS - 1
    last = aggregate.last
    assert re.search(rf".*{PATH.replace('/', '_')}_files_file-series-value_0.*", last.path)
    assert last.size_bytes == 8
    assert last.mime_type == "application/octet-stream"


def test_fetch_attribute_values_single_histogram_series_all_aggregations(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier
    path = HISTOGRAM_SERIES_PATHS[0]

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [AttributeDefinition(path, "histogram_series")],
        )
    )

    # then
    aggregates = HistogramSeriesAggregations(
        last=TEST_DATA.experiments[0].fetcher_histogram_series()[path][-1],
        last_step=NUMBER_OF_STEPS - 1,
    )
    assert values == [AttributeValue(AttributeDefinition(path, "histogram_series"), aggregates, experiment_identifier)]


def test_fetch_attribute_values_all_types(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    all_values = [
        AttributeValue(AttributeDefinition(f"{PATH}/int-value", "int"), 0, experiment_identifier),
        AttributeValue(AttributeDefinition(f"{PATH}/float-value", "float"), 0.0, experiment_identifier),
        AttributeValue(AttributeDefinition(f"{PATH}/str-value", "string"), "hello_0", experiment_identifier),
        AttributeValue(AttributeDefinition(f"{PATH}/bool-value", "bool"), True, experiment_identifier),
        AttributeValue(
            AttributeDefinition(f"{PATH}/datetime-value", "datetime"),
            datetime(2025, 1, 1, 0, 0, 0, 0, timezone.utc),
            experiment_identifier,
        ),
        AttributeValue(
            AttributeDefinition(f"{PATH}/string_set-value", "string_set"),
            {f"string-0-{j}" for j in range(5)},
            experiment_identifier,
        ),
    ]

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [value.attribute_definition for value in all_values],
        )
    )

    # then
    assert len(values) == len(all_values)
    for expected in all_values:
        value = next(value for value in values if value.attribute_definition == expected.attribute_definition)
        assert value == expected


def test_fetch_attribute_values_file(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier
    attribute_definition = AttributeDefinition(f"{PATH}/files/file-value.txt", "file")

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [attribute_definition],
        )
    )

    # then
    assert len(values) == 1
    value = values[0]
    assert value.attribute_definition == attribute_definition
    assert re.search(rf".*{PATH.replace('/', '_')}_files_file-value_txt.*", value.value.path)
    assert value.value.size_bytes == 12
    assert value.value.mime_type == "text/plain"


def test_fetch_attribute_values_paging(client, project, experiment_identifier):
    # given
    project_identifier = project.project_identifier

    #  when
    values = extract_pages(
        fetch_attribute_values(
            client,
            project_identifier,
            [experiment_identifier],
            [
                AttributeDefinition("sys/creation_time", "datetime"),
                AttributeDefinition("sys/modification_time", "datetime"),
                AttributeDefinition("sys/ping_time", "datetime"),
            ],
            batch_size=1,
        )
    )

    # then
    assert set(value.attribute_definition for value in values) == {
        AttributeDefinition("sys/creation_time", "datetime"),
        AttributeDefinition("sys/modification_time", "datetime"),
        AttributeDefinition("sys/ping_time", "datetime"),
    }


def assert_items_equal(a: list[AttributeDefinition], b: list[AttributeDefinition]):
    assert sorted(a, key=lambda d: (d.name, d.type)) == sorted(b, key=lambda d: (d.name, d.type))


def test_fetch_attribute_definitions_experiment_large_number_experiment_identifiers(
    client, project, experiment_identifier
):
    # given
    project_identifier = project.project_identifier

    experiment_identifiers = [experiment_identifier] + _generate_experiment_identifiers(project_identifier, 240 * 1024)

    #  when
    attribute_filter = _AttributeFilter(name_eq="sys/name", type_in=["string"])
    attributes = extract_pages(
        fetch_attribute_definitions_single_filter(
            client,
            [project_identifier],
            experiment_identifiers,
            attribute_filter=attribute_filter,
        )
    )

    # then
    assert attributes == [AttributeDefinition("sys/name", "string")]


def _generate_experiment_identifiers(project_identifier, size_bytes: int):
    per_uuid_size = 50

    identifiers_count = (size_bytes + per_uuid_size) // per_uuid_size

    experiment_identifiers = [RunIdentifier(project_identifier, SysId(f"TEST-{i}")) for i in range(identifiers_count)]

    return experiment_identifiers
