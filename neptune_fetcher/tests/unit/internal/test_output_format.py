import itertools
import pathlib
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import numpy as np
import pandas as pd
import pytest
from pandas._testing import assert_frame_equal

from neptune_fetcher.exceptions import ConflictingAttributeTypes
from neptune_fetcher.internal import identifiers
from neptune_fetcher.internal.identifiers import (
    AttributeDefinition,
    ProjectIdentifier,
    RunAttributeDefinition,
    RunIdentifier,
    SysId,
)
from neptune_fetcher.internal.output_format import (
    convert_table_to_dataframe,
    create_files_dataframe,
    create_metrics_dataframe,
    create_series_dataframe,
)
from neptune_fetcher.internal.retrieval.attribute_types import (
    File,
    FileSeriesAggregations,
    FloatSeriesAggregations,
    Histogram,
    HistogramSeriesAggregations,
    StringSeriesAggregations,
)
from neptune_fetcher.internal.retrieval.attribute_values import AttributeValue
from neptune_fetcher.internal.retrieval.metrics import FloatPointValue
from neptune_fetcher.internal.retrieval.series import SeriesValue

EXPERIMENT_IDENTIFIER = identifiers.RunIdentifier(
    identifiers.ProjectIdentifier("project/abc"), identifiers.SysId("XXX-1")
)


def test_convert_experiment_table_to_dataframe_empty():
    # given
    experiment_data = {}

    # when
    dataframe = convert_table_to_dataframe(experiment_data, selected_aggregations={}, type_suffix_in_column_names=False)

    # then
    assert dataframe.empty


def test_convert_experiment_table_to_dataframe_single_string():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr1", "int"), 42, EXPERIMENT_IDENTIFIER),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(experiment_data, selected_aggregations={}, type_suffix_in_column_names=False)

    # then
    assert dataframe.to_dict() == {
        ("attr1", ""): {"exp1": 42},
    }


def test_convert_experiment_table_to_dataframe_single_string_with_type_suffix():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr1", "int"), 42, EXPERIMENT_IDENTIFIER),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(experiment_data, selected_aggregations={}, type_suffix_in_column_names=True)

    # then
    assert dataframe.to_dict() == {
        ("attr1:int", ""): {"exp1": 42},
    }


def test_convert_experiment_table_to_dataframe_single_float_series():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "float_series"),
                FloatSeriesAggregations(last=42.0, min=0.0, max=100, average=24.0, variance=100.0),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={
            AttributeDefinition("attr1", "float_series"): {"last", "min", "variance"},
        },
        type_suffix_in_column_names=False,
    )

    # then
    assert dataframe.to_dict() == {
        ("attr1", "last"): {"exp1": 42.0},
        ("attr1", "min"): {"exp1": 0.0},
        ("attr1", "variance"): {"exp1": 100.0},
    }


def test_convert_experiment_table_to_dataframe_single_string_series():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "string_series"),
                StringSeriesAggregations(last="last log", last_step=10.0),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={
            AttributeDefinition("attr1", "string_series"): {"last"},
        },
        type_suffix_in_column_names=False,
    )

    # then
    assert dataframe.to_dict() == {
        ("attr1", "last"): {"exp1": "last log"},
    }


def test_convert_experiment_table_to_dataframe_single_histogram_series():
    # given
    last_histogram = Histogram(type="COUNTING", edges=list(range(6)), values=list(range(5)))
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "histogram_series"),
                HistogramSeriesAggregations(last=last_histogram, last_step=10.0),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={
            AttributeDefinition("attr1", "histogram_series"): {"last"},
        },
        type_suffix_in_column_names=False,
    )

    # then
    assert dataframe.to_dict() == {
        ("attr1", "last"): {"exp1": last_histogram},
    }


def test_convert_experiment_table_to_dataframe_single_file_series():
    # given
    last_file = File(path="path/to/last/file", size_bytes=1024, mime_type="text/plain")
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "file_series"),
                FileSeriesAggregations(last=last_file, last_step=10.0),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={
            AttributeDefinition("attr1", "file_series"): {"last"},
        },
        type_suffix_in_column_names=False,
    )

    # then
    assert dataframe.to_dict() == {
        ("attr1", "last"): {"exp1": last_file},
    }


def test_convert_experiment_table_to_dataframe_single_file():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "file"),
                File(path="path/to/file", size_bytes=1024, mime_type="text/plain"),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }

    # when
    dataframe_flattened = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={},
        type_suffix_in_column_names=False,
        flatten_file_properties=True,
    )
    dataframe_unflattened = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={},
        type_suffix_in_column_names=False,
    )

    # then
    assert dataframe_flattened.to_dict() == {
        ("attr1", "path"): {"exp1": "path/to/file"},
        ("attr1", "size_bytes"): {"exp1": 1024},
        ("attr1", "mime_type"): {"exp1": "text/plain"},
    }

    assert dataframe_unflattened.to_dict() == {
        ("attr1", ""): {"exp1": File(path="path/to/file", size_bytes=1024, mime_type="text/plain")},
    }


def test_convert_experiment_table_to_dataframe_disjoint_names():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr1", "int"), 42, EXPERIMENT_IDENTIFIER),
        ],
        identifiers.SysName("exp2"): [
            AttributeValue(AttributeDefinition("attr2", "int"), 43, EXPERIMENT_IDENTIFIER),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(experiment_data, selected_aggregations={}, type_suffix_in_column_names=False)

    # then
    expected_data = pd.DataFrame.from_dict(
        {
            ("attr1", ""): {"exp1": 42.0, "exp2": float("nan")},
            ("attr2", ""): {"exp1": float("nan"), "exp2": 43.0},
        }
    )
    expected_data.index.name = "experiment"
    expected_data.columns = pd.MultiIndex.from_tuples(expected_data.columns, names=["attribute", "aggregation"])
    assert_frame_equal(dataframe, expected_data)


def test_convert_experiment_table_to_dataframe_conflicting_types_with_suffix():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr1/a:b:c", "int"), 42, EXPERIMENT_IDENTIFIER),
        ],
        identifiers.SysName("exp2"): [
            AttributeValue(AttributeDefinition("attr1/a:b:c", "float"), 0.43, EXPERIMENT_IDENTIFIER),
        ],
    }

    # when
    dataframe = convert_table_to_dataframe(experiment_data, selected_aggregations={}, type_suffix_in_column_names=True)

    # then
    expected_data = pd.DataFrame.from_dict(
        {
            ("attr1/a:b:c:float", ""): {"exp1": float("nan"), "exp2": 0.43},
            ("attr1/a:b:c:int", ""): {"exp1": 42.0, "exp2": float("nan")},
        }
    )
    expected_data.index.name = "experiment"
    expected_data.columns = pd.MultiIndex.from_tuples(expected_data.columns, names=["attribute", "aggregation"])
    assert_frame_equal(dataframe, expected_data)


def test_convert_experiment_table_to_dataframe_conflicting_types_without_suffix():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr1/a:b:c", "int"), 42, EXPERIMENT_IDENTIFIER),
        ],
        identifiers.SysName("exp2"): [
            AttributeValue(AttributeDefinition("attr1/a:b:c", "float"), 0.43, EXPERIMENT_IDENTIFIER),
        ],
    }

    # when
    with pytest.raises(ConflictingAttributeTypes) as exc_info:
        convert_table_to_dataframe(experiment_data, selected_aggregations={}, type_suffix_in_column_names=False)

    # then
    assert "attr1/a:b:c" in str(exc_info.value)


def test_convert_experiment_table_to_dataframe_flatten_aggregations_only_last():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "float_series"),
                FloatSeriesAggregations(last=42.0, min=0.0, max=100, average=24.0, variance=100.0),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }
    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={
            AttributeDefinition("attr1", "float_series"): {"last"},
        },
        type_suffix_in_column_names=False,
        flatten_aggregations=True,
    )
    # then
    assert dataframe.to_dict() == {
        "attr1": {"exp1": 42.0},
    }


def test_convert_experiment_table_to_dataframe_flatten_aggregations_non_last_raises():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "float_series"),
                FloatSeriesAggregations(last=42.0, min=0.0, max=100, average=24.0, variance=100.0),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }
    # when / then
    with pytest.raises(ValueError):
        convert_table_to_dataframe(
            experiment_data,
            selected_aggregations={
                AttributeDefinition("attr1", "float_series"): {"last", "min"},
            },
            type_suffix_in_column_names=False,
            flatten_aggregations=True,
        )


def test_convert_experiment_table_to_dataframe_flatten_aggregations_and_file_properties_raises():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(
                AttributeDefinition("attr1", "float_series"),
                FloatSeriesAggregations(last=42.0, min=0.0, max=100, average=24.0, variance=100.0),
                EXPERIMENT_IDENTIFIER,
            ),
        ],
    }
    # when / then
    with pytest.raises(ValueError):
        convert_table_to_dataframe(
            experiment_data,
            selected_aggregations={
                AttributeDefinition("attr1", "float_series"): {"last"},
            },
            type_suffix_in_column_names=False,
            flatten_aggregations=True,
            flatten_file_properties=True,
        )


def test_convert_experiment_table_to_dataframe_empty_with_flatten_aggregations():
    # given
    experiment_data = {}
    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={},
        type_suffix_in_column_names=False,
        flatten_aggregations=True,
    )
    # then
    assert dataframe.empty
    assert list(dataframe.columns) == []


def test_convert_experiment_table_to_dataframe_empty_with_flatten_file_properties():
    # given
    experiment_data = {}
    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={},
        type_suffix_in_column_names=False,
        flatten_file_properties=True,
    )
    # then
    assert dataframe.empty
    assert isinstance(dataframe.columns, pd.MultiIndex)


def test_convert_experiment_table_to_dataframe_duplicate_column_name_with_type_suffix():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr", "int"), 1, EXPERIMENT_IDENTIFIER),
            AttributeValue(AttributeDefinition("attr", "float"), 2.0, EXPERIMENT_IDENTIFIER),
        ],
    }
    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={},
        type_suffix_in_column_names=True,
    )
    # then
    assert set(dataframe.columns.get_level_values(0)) == {"attr:int", "attr:float"}


def test_convert_experiment_table_to_dataframe_duplicate_column_name_without_type_suffix_raises():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr", "int"), 1, EXPERIMENT_IDENTIFIER),
            AttributeValue(AttributeDefinition("attr", "float"), 2.0, EXPERIMENT_IDENTIFIER),
        ],
    }
    # when / then
    with pytest.raises(ConflictingAttributeTypes):
        convert_table_to_dataframe(
            experiment_data,
            selected_aggregations={},
            type_suffix_in_column_names=False,
        )


def test_convert_experiment_table_to_dataframe_index_column_name_custom():
    # given
    experiment_data = {
        identifiers.SysName("exp1"): [
            AttributeValue(AttributeDefinition("attr1", "int"), 42, EXPERIMENT_IDENTIFIER),
        ],
    }
    # when
    dataframe = convert_table_to_dataframe(
        experiment_data,
        selected_aggregations={},
        type_suffix_in_column_names=False,
        index_column_name="custom_index",
    )
    # then
    assert dataframe.index.name == "custom_index"
    assert dataframe.to_dict() == {
        ("attr1", ""): {"exp1": 42},
    }


EXPERIMENTS = 5
PATHS = 5
STEPS = 10


def _generate_float_point_values(
    experiments: int, paths: int, steps: int, preview: bool
) -> dict[RunAttributeDefinition, list[FloatPointValue]]:
    result = {}

    for experiment in range(experiments):
        for path in range(paths):
            attribute_run = RunAttributeDefinition(
                RunIdentifier(ProjectIdentifier("foo/bar"), SysId(f"sysid{experiment}")),
                AttributeDefinition(f"path{path}", "float_series"),
            )
            points = result.setdefault(attribute_run, [])

            for step in range(steps):
                timestamp = datetime(2023, 1, 1, 0, 0, 0, 0, timezone.utc) + timedelta(seconds=step)
                points.append(
                    (
                        timestamp.timestamp(),
                        float(step),
                        float(step) * 100,
                        preview,
                        1.0 - (float(step) / 1000.0),
                    )
                )
    return result


def _format_path_name(path: str, type_suffix_in_column_names: bool) -> str:
    return f"{path}:float_series" if type_suffix_in_column_names else path


def _make_timestamp(year: int, month: int, day: int) -> float:
    return datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000


@pytest.mark.parametrize("include_preview", [False, True])
def test_create_metrics_dataframe_shape(include_preview):
    float_point_values = _generate_float_point_values(EXPERIMENTS, PATHS, STEPS, include_preview)
    sys_id_label_mapping = {SysId(f"sysid{experiment}"): f"exp{experiment}" for experiment in range(EXPERIMENTS)}

    """Test the creation of a flat DataFrame from float point values."""
    df = create_metrics_dataframe(
        metrics_data=float_point_values,
        sys_id_label_mapping=sys_id_label_mapping,
        include_point_previews=include_preview,
        type_suffix_in_column_names=False,
        index_column_name="experiment",
    )

    # Check if the DataFrame is not empty
    assert not df.empty, "DataFrame should not be empty"

    # Check the shape of the DataFrame
    num_expected_rows = EXPERIMENTS * STEPS
    assert df.shape[0] == num_expected_rows, f"DataFrame should have {num_expected_rows} rows"

    # Check the columns of the DataFrame
    all_paths = {key.attribute_definition.name for key in float_point_values.keys()}
    if not include_preview:
        expected_columns = all_paths
    else:
        expected_columns = set(itertools.product(all_paths, ["value", "is_preview", "preview_completion"]))

    assert set(df.columns) == expected_columns, f"DataFrame should have {len(all_paths)} columns"
    assert (
        df.index.get_level_values(0).nunique() == EXPERIMENTS
    ), f"DataFrame should have {EXPERIMENTS} experiment names"

    # Convert DataFrame to list of tuples
    tuples_list = list(df.to_records(index=False))
    assert (
        len(tuples_list) == num_expected_rows
    ), "The list of tuples should have the same number of rows as the DataFrame"


@pytest.mark.parametrize("type_suffix_in_column_names", [True, False])
@pytest.mark.parametrize("include_preview", [True, False])
def test_create_metrics_dataframe_with_absolute_timestamp(type_suffix_in_column_names: bool, include_preview: bool):
    # Given
    data = {
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")), AttributeDefinition("path1", "float_series")
        ): [
            (_make_timestamp(2023, 1, 1), 1, 10.0, False, 1.0),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")), AttributeDefinition("path2", "float_series")
        ): [
            (_make_timestamp(2023, 1, 3), 2, 20.0, False, 1.0),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid2")), AttributeDefinition("path1", "float_series")
        ): [
            (_make_timestamp(2023, 1, 2), 1, 30.0, True, 0.5),
        ],
    }
    sys_id_label_mapping = {
        SysId("sysid1"): "exp1",
        SysId("sysid2"): "exp2",
    }

    df = create_metrics_dataframe(
        metrics_data=data,
        sys_id_label_mapping=sys_id_label_mapping,
        timestamp_column_name="absolute_time",
        type_suffix_in_column_names=type_suffix_in_column_names,
        include_point_previews=include_preview,
        index_column_name="experiment",
    )

    # Then
    expected = {
        (_format_path_name("path1", type_suffix_in_column_names), "absolute_time"): [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            np.nan,
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        ],
        (_format_path_name("path1", type_suffix_in_column_names), "value"): [10.0, np.nan, 30.0],
        (_format_path_name("path2", type_suffix_in_column_names), "absolute_time"): [
            np.nan,
            datetime(2023, 1, 3, tzinfo=timezone.utc),
            np.nan,
        ],
        (_format_path_name("path2", type_suffix_in_column_names), "value"): [np.nan, 20.0, np.nan],
    }
    if include_preview:
        expected.update(
            {
                (_format_path_name("path1", type_suffix_in_column_names), "is_preview"): [False, np.nan, True],
                (_format_path_name("path1", type_suffix_in_column_names), "preview_completion"): [1.0, np.nan, 0.5],
                (_format_path_name("path2", type_suffix_in_column_names), "is_preview"): [np.nan, False, np.nan],
                (_format_path_name("path2", type_suffix_in_column_names), "preview_completion"): [np.nan, 1.0, np.nan],
            }
        )

    expected_df = pd.DataFrame(
        dict(sorted(expected.items())),
        index=pd.MultiIndex.from_tuples([("exp1", 1.0), ("exp1", 2.0), ("exp2", 1.0)], names=["experiment", "step"]),
    )

    pd.testing.assert_frame_equal(df, expected_df)


def _run_definition(run_id: str, attribute_path: str, attribute_type: str = "string_series") -> RunAttributeDefinition:
    return RunAttributeDefinition(
        RunIdentifier(ProjectIdentifier("foo/bar"), SysId(run_id)), AttributeDefinition(attribute_path, attribute_type)
    )


def test_create_string_series_dataframe_with_absolute_timestamp():
    # Given
    series_data = {
        _run_definition("expid1", "path1"): [SeriesValue(1, "aaa", _make_timestamp(2023, 1, 1))],
        _run_definition("expid1", "path2"): [SeriesValue(2, "bbb", _make_timestamp(2023, 1, 3))],
        _run_definition("expid2", "path1"): [SeriesValue(1, "ccc", _make_timestamp(2023, 1, 2))],
    }
    sys_id_label_mapping = {
        SysId("expid1"): "exp1",
        SysId("expid2"): "exp2",
    }

    df = create_series_dataframe(
        series_data=series_data,
        sys_id_label_mapping=sys_id_label_mapping,
        index_column_name="experiment",
        timestamp_column_name="absolute_time",
    )

    # Then
    expected = {
        ("path1", "absolute_time"): [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            np.nan,
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        ],
        ("path1", "value"): ["aaa", np.nan, "ccc"],
        ("path2", "absolute_time"): [
            np.nan,
            datetime(2023, 1, 3, tzinfo=timezone.utc),
            np.nan,
        ],
        ("path2", "value"): [np.nan, "bbb", np.nan],
    }
    expected_df = pd.DataFrame(
        dict(sorted(expected.items())),
        index=pd.MultiIndex.from_tuples([("exp1", 1.0), ("exp1", 2.0), ("exp2", 1.0)], names=["experiment", "step"]),
    )
    pd.testing.assert_frame_equal(df, expected_df)


def test_create_histogram_dataframe_with_absolute_timestamp():
    # Given
    histograms = [
        Histogram(type="COUNTING", edges=[1, 2, 3], values=[10, 20]),
        Histogram(type="COUNTING", edges=[5, 6], values=[100]),
        Histogram(type="COUNTING", edges=[1, 2, 3], values=[11, 19]),
    ]
    series_data = {
        _run_definition("expid1", "path1"): [SeriesValue(1, histograms[0], _make_timestamp(2023, 1, 1))],
        _run_definition("expid1", "path2"): [SeriesValue(2, histograms[1], _make_timestamp(2023, 1, 3))],
        _run_definition("expid2", "path1"): [SeriesValue(1, histograms[2], _make_timestamp(2023, 1, 2))],
    }
    sys_id_label_mapping = {
        SysId("expid1"): "exp1",
        SysId("expid2"): "exp2",
    }

    df = create_series_dataframe(
        series_data=series_data,
        sys_id_label_mapping=sys_id_label_mapping,
        index_column_name="experiment",
        timestamp_column_name="absolute_time",
    )

    # Then
    expected = {
        ("path1", "absolute_time"): [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            np.nan,
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        ],
        ("path1", "value"): [histograms[0], np.nan, histograms[2]],
        ("path2", "absolute_time"): [
            np.nan,
            datetime(2023, 1, 3, tzinfo=timezone.utc),
            np.nan,
        ],
        ("path2", "value"): [np.nan, histograms[1], np.nan],
    }
    expected_df = pd.DataFrame(
        dict(sorted(expected.items())),
        index=pd.MultiIndex.from_tuples([("exp1", 1.0), ("exp1", 2.0), ("exp2", 1.0)], names=["experiment", "step"]),
    )
    pd.testing.assert_frame_equal(df, expected_df)


@pytest.mark.parametrize("type_suffix_in_column_names", [True, False])
@pytest.mark.parametrize("include_preview", [True, False])
def test_create_metrics_dataframe_without_timestamp(type_suffix_in_column_names: bool, include_preview: bool):
    # Given
    data = {
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")), AttributeDefinition("path1", "float_series")
        ): [
            (_make_timestamp(2023, 1, 1), 1, 10.0, False, 1.0),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")), AttributeDefinition("path2", "float_series")
        ): [
            (_make_timestamp(2023, 1, 3), 2, 20.0, False, 1.0),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid2")), AttributeDefinition("path1", "float_series")
        ): [
            (_make_timestamp(2023, 1, 2), 1, 30.0, True, 0.5),
        ],
    }
    sys_id_label_mapping = {
        SysId("sysid1"): "exp1",
        SysId("sysid2"): "exp2",
    }

    df = create_metrics_dataframe(
        metrics_data=data,
        sys_id_label_mapping=sys_id_label_mapping,
        type_suffix_in_column_names=type_suffix_in_column_names,
        include_point_previews=include_preview,
        index_column_name="experiment",
    )

    # Then
    if not include_preview:
        # Flat columns
        expected = {
            _format_path_name("path1", type_suffix_in_column_names): [10.0, np.nan, 30.0],
            _format_path_name("path2", type_suffix_in_column_names): [np.nan, 20.0, np.nan],
        }
    else:
        # MultiIndex columns are returned on include_preview=True
        expected = {
            (_format_path_name("path1", type_suffix_in_column_names), "value"): [10.0, np.nan, 30.0],
            (_format_path_name("path2", type_suffix_in_column_names), "value"): [np.nan, 20.0, np.nan],
            (_format_path_name("path1", type_suffix_in_column_names), "is_preview"): [False, np.nan, True],
            (_format_path_name("path1", type_suffix_in_column_names), "preview_completion"): [1.0, np.nan, 0.5],
            (_format_path_name("path2", type_suffix_in_column_names), "is_preview"): [np.nan, False, np.nan],
            (_format_path_name("path2", type_suffix_in_column_names), "preview_completion"): [np.nan, 1.0, np.nan],
        }

    expected_df = pd.DataFrame(
        dict(sorted(expected.items())),
        index=pd.MultiIndex.from_tuples([("exp1", 1.0), ("exp1", 2.0), ("exp2", 1.0)], names=["experiment", "step"]),
    )

    pd.testing.assert_frame_equal(df, expected_df)


def test_create_metrics_dataframe_random_order():
    # Given
    data = {
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")), AttributeDefinition("path1", "float_series")
        ): [
            (_make_timestamp(2023, 1, 1), 3, 30.0, False, 1.0),
            (_make_timestamp(2023, 1, 1), 2, 20.0, False, 1.0),
            (_make_timestamp(2023, 1, 1), 1, 10.0, False, 1.0),
            (_make_timestamp(2023, 1, 1), 5, 50.0, False, 1.0),
            (_make_timestamp(2023, 1, 1), 4, 40.0, False, 1.0),
        ],
    }
    sys_id_label_mapping = {
        SysId("sysid1"): "exp1",
    }

    df = create_metrics_dataframe(
        metrics_data=data,
        sys_id_label_mapping=sys_id_label_mapping,
        type_suffix_in_column_names=False,
        include_point_previews=False,
        index_column_name="experiment",
    )

    # Then
    expected = {
        "path1": [10.0, 20.0, 30.0, 40.0, 50.0],
    }

    expected_df = pd.DataFrame(
        dict(sorted(expected.items())),
        index=pd.MultiIndex.from_tuples(
            [("exp1", 1.0), ("exp1", 2.0), ("exp1", 3.0), ("exp1", 4.0), ("exp1", 5.0)], names=["experiment", "step"]
        ),
    )

    pd.testing.assert_frame_equal(df, expected_df)


@pytest.mark.parametrize("type_suffix_in_column_names", [True, False])
@pytest.mark.parametrize("include_preview", [True, False])
@pytest.mark.parametrize("timestamp_column_name", [None, "absolute"])
def test_create_empty_metrics_dataframe(
    type_suffix_in_column_names: bool, include_preview: bool, timestamp_column_name: str
):
    # Given empty dataframe

    # When
    df = create_metrics_dataframe(
        metrics_data={},
        sys_id_label_mapping={},
        type_suffix_in_column_names=type_suffix_in_column_names,
        include_point_previews=include_preview,
        timestamp_column_name=timestamp_column_name,
        index_column_name="experiment",
    )

    # Then
    if include_preview or timestamp_column_name:
        expected_df = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([], names=["experiment", "step"]),
            columns=pd.MultiIndex.from_tuples([], names=["path", "metric"]),  # Create empty MultiIndex for columns
        )
        expected_df.columns.names = None, None
    else:
        expected_df = pd.DataFrame(
            {
                "experiment": [],
                "step": [],
            }
        ).set_index(["experiment", "step"])

    pd.testing.assert_frame_equal(df, expected_df, check_index_type=False)


@pytest.mark.parametrize("timestamp_column_name", [None, "absolute"])
def test_create_empty_series_dataframe(timestamp_column_name: str):
    # Given empty dataframe

    # When
    df = create_series_dataframe(
        series_data={},
        sys_id_label_mapping={},
        index_column_name="experiment",
        timestamp_column_name=timestamp_column_name,
    )

    # Then
    if timestamp_column_name:
        expected_df = pd.DataFrame(
            index=pd.MultiIndex.from_tuples([], names=["experiment", "step"]),
            columns=pd.MultiIndex.from_tuples([], names=["path", "metric"]),  # Create empty MultiIndex for columns
        )
        expected_df.columns.names = None, None
    else:
        expected_df = pd.DataFrame(
            {
                "experiment": [],
                "step": [],
            }
        ).set_index(["experiment", "step"])

    pd.testing.assert_frame_equal(df, expected_df, check_index_type=False)


@pytest.mark.parametrize(
    "path", ["value", "step", "experiment", "value", "timestamp", "is_preview", "preview_completion"]
)
@pytest.mark.parametrize("type_suffix_in_column_names", [True, False])
@pytest.mark.parametrize("include_preview", [True, False])
@pytest.mark.parametrize("timestamp_column_name", ["absolute_time"])
def test_create_metrics_dataframe_with_reserved_paths_with_multiindex(
    path: str, type_suffix_in_column_names: bool, include_preview: bool, timestamp_column_name: str
):
    # Given
    data = {
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")), AttributeDefinition(path, "float_series")
        ): [
            (_make_timestamp(2023, 1, 1), 1, 10.0, False, 1.0),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid2")), AttributeDefinition(path, "float_series")
        ): [
            (_make_timestamp(2023, 1, 2), 1, 30.0, True, 0.5),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")),
            AttributeDefinition("other_path", "float_series"),
        ): [
            (_make_timestamp(2023, 1, 3), 2, 20.0, False, 1.0),
        ],
    }
    sys_id_label_mapping = {
        SysId("sysid1"): "exp1",
        SysId("sysid2"): "exp2",
    }

    df = create_metrics_dataframe(
        metrics_data=data,
        sys_id_label_mapping=sys_id_label_mapping,
        timestamp_column_name=timestamp_column_name,
        type_suffix_in_column_names=type_suffix_in_column_names,
        include_point_previews=include_preview,
        index_column_name="experiment",
    )

    # Then
    expected = {
        (_format_path_name(path, type_suffix_in_column_names), "absolute_time"): [
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            np.nan,
            datetime(2023, 1, 2, tzinfo=timezone.utc),
        ],
        (_format_path_name(path, type_suffix_in_column_names), "value"): [10.0, np.nan, 30.0],
        (_format_path_name("other_path", type_suffix_in_column_names), "absolute_time"): [
            np.nan,
            datetime(2023, 1, 3, tzinfo=timezone.utc),
            np.nan,
        ],
        (_format_path_name("other_path", type_suffix_in_column_names), "value"): [np.nan, 20.0, np.nan],
    }
    if include_preview:
        expected.update(
            {
                (_format_path_name(path, type_suffix_in_column_names), "is_preview"): [False, np.nan, True],
                (_format_path_name(path, type_suffix_in_column_names), "preview_completion"): [1.0, np.nan, 0.5],
                (_format_path_name("other_path", type_suffix_in_column_names), "is_preview"): [np.nan, False, np.nan],
                (_format_path_name("other_path", type_suffix_in_column_names), "preview_completion"): [
                    np.nan,
                    1.0,
                    np.nan,
                ],
            }
        )

    expected_df = pd.DataFrame(
        dict(sorted(expected.items())),
        index=pd.MultiIndex.from_tuples([("exp1", 1.0), ("exp1", 2.0), ("exp2", 1.0)], names=["experiment", "step"]),
    )

    pd.testing.assert_frame_equal(df, expected_df)


@pytest.mark.parametrize(
    "path", ["value", "step", "experiment", "value", "timestamp", "is_preview", "preview_completion"]
)
@pytest.mark.parametrize("type_suffix_in_column_names", [True, False])
def test_create_metrics_dataframe_with_reserved_paths_with_flat_index(path: str, type_suffix_in_column_names: bool):
    # Given
    data = {
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")), AttributeDefinition(path, "float_series")
        ): [
            (_make_timestamp(2023, 1, 1), 1, 10.0, False, 1.0),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid2")), AttributeDefinition(path, "float_series")
        ): [
            (_make_timestamp(2023, 1, 2), 1, 30.0, True, 0.5),
        ],
        RunAttributeDefinition(
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("sysid1")),
            AttributeDefinition("other_path", "float_series"),
        ): [
            (_make_timestamp(2023, 1, 3), 2, 20.0, False, 1.0),
        ],
    }
    sys_id_label_mapping = {
        SysId("sysid1"): "exp1",
        SysId("sysid2"): "exp2",
    }

    df = create_metrics_dataframe(
        metrics_data=data,
        sys_id_label_mapping=sys_id_label_mapping,
        type_suffix_in_column_names=type_suffix_in_column_names,
        include_point_previews=False,
        index_column_name="experiment",
    )

    # Then
    expected = {
        _format_path_name(path, type_suffix_in_column_names): [10.0, np.nan, 30.0],
        _format_path_name("other_path", type_suffix_in_column_names): [np.nan, 20.0, np.nan],
    }

    expected_df = pd.DataFrame(
        dict(sorted(expected.items())),
        index=pd.MultiIndex.from_tuples([("exp1", 1.0), ("exp1", 2.0), ("exp2", 1.0)], names=["experiment", "step"]),
    )

    pd.testing.assert_frame_equal(df, expected_df)


def test_create_files_dataframe_empty():
    # given
    files_data = []
    sys_id_label_mapping = {}
    index_column_name = "experiment"

    # when
    dataframe = create_files_dataframe(
        files_data=files_data, sys_id_label_mapping=sys_id_label_mapping, index_column_name=index_column_name
    )

    # then
    assert dataframe.empty
    assert dataframe.index.name == index_column_name
    assert dataframe.columns.names == [None]


def test_create_files_dataframe():
    # given
    files_data = [
        (
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("exp1")),
            AttributeDefinition("attr1", "file"),
            pathlib.Path("/path/to/file1"),
        ),
        (
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("exp2")),
            AttributeDefinition("attr2", "file"),
            pathlib.Path("/path/to/file2"),
        ),
    ]
    sys_id_label_mapping = {
        SysId("exp1"): "experiment_1",
        SysId("exp2"): "experiment_2",
    }
    index_column_name = "experiment"

    # when
    dataframe = create_files_dataframe(
        files_data=files_data, sys_id_label_mapping=sys_id_label_mapping, index_column_name=index_column_name
    )

    # then
    expected_data = [
        {index_column_name: "experiment_1", "attr1": str(pathlib.Path("/path/to/file1"))},
        {index_column_name: "experiment_2", "attr2": str(pathlib.Path("/path/to/file2"))},
    ]
    expected_df = pd.DataFrame(expected_data).set_index(index_column_name)
    expected_df.columns.names = ["attribute"]

    assert_frame_equal(dataframe, expected_df)


def test_create_files_dataframe_index_name_attribute_conflict():
    # given
    files_data = [
        (
            RunIdentifier(ProjectIdentifier("foo/bar"), SysId("exp1")),
            AttributeDefinition("experiment", "file"),
            pathlib.Path("/path/to/file1"),
        ),
    ]
    sys_id_label_mapping = {
        SysId("exp1"): "experiment_1",
    }
    index_column_name = "experiment"

    # when
    dataframe = create_files_dataframe(
        files_data=files_data, sys_id_label_mapping=sys_id_label_mapping, index_column_name=index_column_name
    )

    # then
    expected_data = [
        {"_REPLACE_": "experiment_1", "experiment": str(pathlib.Path("/path/to/file1"))},
    ]
    expected_df = pd.DataFrame(expected_data).set_index("_REPLACE_")
    expected_df.columns.names = ["attribute"]
    expected_df.index.name = index_column_name

    assert_frame_equal(dataframe, expected_df)
