import pathlib
import pandas as pd
import panel as pn
import param
import psutil
import xarray

import holoviews as hv
import hvplot.xarray
from holoviews.operation.datashader import datashade
from holoviews.operation import decimate
import colorcet as cc
from bokeh.palettes import Viridis256

from mth5.mth5 import MTH5
from mth5 import CHANNEL_DTYPE, RUN_SUMMARY_DTYPE

from tsvi.mth5_tsviewer.helpers import (
    cpu_usage_widget,
    memory_usage_widget,
)

hv.extension("bokeh")
xarray.set_options(keep_attrs=True)

# --------------------------------------------------------------
# Global Constants
# --------------------------------------------------------------
DATASHADE_THRESHOLD = 500_000

CH_SUMMARY_DISPLAY_COLUMNS = [
    "survey",
    "station",
    "run",
    "component",
    "start",
    "end",
    "n_samples",
    "sample_rate",
    "measurement_type",
]

RUN_SUMMARY_DISPLAY_COLUMNS = [
    "survey",
    "station",
    "run",
    "start",
    "end",
    "n_samples",
    "sample_rate",
    "input_channels",
    "output_channels",
]

COLORMAP = "Magma"


def get_templates_dict():
    templates = {}
    templates["bootstrap"] = pn.template.BootstrapTemplate
    templates["fast"] = pn.template.FastListTemplate
    templates["golden"] = pn.template.GoldenTemplate
    templates["grid"] = pn.template.FastGridTemplate
    return templates


class Tsvi(param.Parameterized):
    # -------------------------
    # Parameters (reactive state)
    # -------------------------
    plot_width = param.Integer(default=900)
    plot_height = param.Integer(default=450)
    plot_width_max = param.Integer(default=1200)

    annotatable = param.Boolean(default=False)
    choose_runs = param.Boolean(
        default=True, doc="True: select runs, False: select channels"
    )
    subtract_mean = param.Boolean(default=True)
    colormap = param.String(default=COLORMAP)

    combine_subplots = param.Boolean(default=True)
    _ordering_version = param.Integer(default=0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------------------------
        # Template
        # -------------------------
        template_key = "golden"
        self.template = get_templates_dict()[template_key](title="TSVI")

        # -------------------------
        # Data state
        # -------------------------
        self.channel_summary = pd.DataFrame(columns=CHANNEL_DTYPE.names)
        self.run_summary = pd.DataFrame(columns=RUN_SUMMARY_DTYPE.names)

        self.selected_channels = {}
        self.selected_runs = {}

        self.data_dict = {}  # key -> xarray object
        self.plot_panes = {}  # key -> pn.pane.HoloViews
        self.datashade_cache = {}  # key -> datashaded hv object

        self.subplot_row_assignments = {}  # key -> row index (1-based int)

        # -------------------------
        # Color palettes and maps
        # -------------------------
        # Semantic MT palettes
        self.semantic_electric_palette = ["#4477AA", "#66CCEE", "#228833"]
        self.semantic_magnetic_palette = ["#EE6677", "#AA3377", "#CCBB44"]
        self.semantic_aux_palette = ["#BBBBBB", "#999999", "#777777"]

        # Other palettes
        self.vibrant_palette = cc.glasbey[:20]

        self.viridis_palette = Viridis256

        # Maps for semantic indexing
        self.electric_index_map = {}
        self.magnetic_index_map = {}
        self.aux_index_map = {}

        # -------------------------
        # Widgets
        # -------------------------
        self.cpu_usage = pn.indicators.Number(
            name="CPU",
            value=0,
            format="{value}%",
            colors=[(50, "green"), (75, "orange"), (100, "red")],
            font_size="13pt",
            title_size="8pt",
            width=50,
        )

        self.memory_usage = pn.indicators.Number(
            name="Memory",
            value=0,
            format="{value}%",
            colors=[(50, "green"), (75, "orange"), (100, "red")],
            font_size="13pt",
            title_size="8pt",
            width=50,
        )

        self.run_or_channel_checkbox = pn.widgets.Checkbox(name="Pick Runs", value=True)
        self.run_or_channel_checkbox.param.watch(self._on_choose_runs_checkbox, "value")

        self.clear_plots_button = pn.widgets.Button(
            name="Clear Plots", button_type="danger"
        )
        self.clear_plots_button.on_click(self.clear_plots)

        self.clear_channels_button = pn.widgets.Button(
            name="Clear Channels", button_type="danger"
        )
        self.clear_channels_button.on_click(self.clear_channels)

        self.plot_button = pn.widgets.Button(name="Plot", button_type="primary")
        self.plot_button.on_click(self._on_plot_button)

        self.subtract_mean_checkbox = pn.widgets.Checkbox(
            name="Subtract Mean", value=True
        )
        self.subtract_mean_checkbox.param.watch(self._on_subtract_mean_changed, "value")

        self.combine_subplots_checkbox = pn.widgets.Checkbox(
            name="Combine Subplots", value=True
        )
        self.combine_subplots_checkbox.param.watch(
            self._on_combine_subplots_changed, "value"
        )

        # Lock color identity (semantic MT colors)
        self.lock_color_identity = pn.widgets.Checkbox(
            name="Lock Color Identity",
            value=False,
        )

        # Palette selector
        self.palette_selector = pn.widgets.Select(
            name="Color Palette",
            options={
                "MT Semantic (Subdued)": "semantic",
                "Vibrant (Glasbey)": "glasbey",
                "Viridis-like": "viridis",
            },
            value="semantic",
        )
        self.palette_selector.param.watch(self._on_palette_changed, "value")
        self.lock_color_identity.param.watch(self._on_palette_changed, "value")

        # Reset ordering button
        self.reset_order_button = pn.widgets.Button(
            name="Reset Ordering",
            button_type="primary",
            width=120,
        )
        self.reset_order_button.on_click(self._reset_ordering)

        # subplot row selectors UI container
        self.subplot_row_panel = pn.Column(name="Subplot Row Assignment")

        # -------------------------
        # Tabs
        # -------------------------
        self.files_tab = self._make_files_tab()
        self.df_tab = self._make_df_tab()
        self.plots_tab = self._make_plots_tab()

        self.tabs = pn.Tabs(
            ("Files", self.files_tab),
            ("DataFrame", self.df_tab),
            ("Plots", self.plots_tab),
            dynamic=False,
        )

        # -------------------------
        # Sidebar
        # -------------------------
        self._build_sidebar()

        # -------------------------
        # Layout
        # -------------------------
        self.template.main[:] = [self.tabs]

        # -------------------------
        # Resource streaming
        # -------------------------
        self._start_resource_stream()

    # =========================================================
    # Sidebar
    # =========================================================
    def _build_sidebar(self):
        self.template.sidebar[:] = [
            self.cpu_usage,
            self.memory_usage,
            self.run_or_channel_checkbox,
            self.subtract_mean_checkbox,
            self.combine_subplots_checkbox,
            self.lock_color_identity,
            self.palette_selector,
            self.reset_order_button,
            self.subplot_row_panel,
            self.plot_button,
            self.clear_plots_button,
            self.clear_channels_button,
        ]

    # =========================================================
    # Tabs
    # =========================================================
    def _make_files_tab(self):
        self.files = pn.widgets.FileSelector(
            name="Select MTH5 Files",
            directory="~",
            file_pattern="*.h5",
            sizing_mode="stretch_width",
        )
        self.files.param.watch(self._on_files_changed, "value")
        return pn.Column(self.files, sizing_mode="stretch_width")

    def _make_df_tab(self):
        self.channels_table = pn.widgets.Tabulator(
            self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS],
            selectable=True,
            sizing_mode="stretch_both",
            margin=(10, 0, 0, 0),
            formatters={
                "start": {"type": "datetime", "format": "iso"},
                "end": {"type": "datetime", "format": "iso"},
            },
        )

        self.channels_table.param.watch(self._on_table_selection, "selection")
        return pn.Column(self.channels_table, sizing_mode="stretch_width")

    def _make_plots_tab(self):
        self.graphs = pn.Column(
            sizing_mode="stretch_width",
            margin=0,
            max_width=self.plot_width_max,
        )
        return pn.Column(self.graphs, sizing_mode="stretch_width")

    # =========================================================
    # Callbacks / param handlers
    # =========================================================
    def _on_choose_runs_checkbox(self, event):
        self.choose_runs = event.new
        self._refresh_channels_tab()

    def _on_files_changed(self, event):
        self._load_summaries_from_files(event.new)
        self._refresh_channels_tab()
        self.tabs.active = 0

    def _on_table_selection(self, event):
        self._update_selected_from_table(event.new)

    def _on_plot_button(self, *events):
        self.tabs.active = 2
        self._build_data_dict()
        self._build_or_update_plots()
        self._update_subplot_row_selectors()
        self._render_plots()

    def _on_subtract_mean_changed(self, event):
        self.subtract_mean = event.new
        if self.data_dict:
            self._build_or_update_plots()
            self._render_plots()

    def _on_combine_subplots_changed(self, event):
        self.combine_subplots = event.new
        self._render_plots()

    def _on_palette_changed(self, event=None):
        if self.data_dict:
            self._build_or_update_plots()
            self._render_plots()

    # =========================================================
    # Data loading and selection
    # =========================================================
    def _load_summaries_from_files(self, file_paths):
        full_df_channels = pd.DataFrame()
        full_df_runs = pd.DataFrame()

        for file_path in file_paths:
            with MTH5() as m:
                m = m.open_mth5(file_path, mode="r")
                run_df = m.run_summary
                run_df["hdf5_reference"] = run_df["run_hdf5_reference"].apply(
                    lambda ref: m.get_reference_path(ref)
                )
                run_df["file"] = file_path
                run_df.drop(columns=["station_hdf5_reference"], inplace=True)

                channel_df = m.channel_summary.to_dataframe()
                channel_df["hdf5_reference"] = channel_df["hdf5_reference"].apply(
                    lambda ref: m.get_reference_path(ref)
                )
                channel_df["file"] = file_path
                channel_df.drop(
                    columns=["run_hdf5_reference", "station_hdf5_reference"],
                    inplace=True,
                )

            full_df_channels = pd.concat([full_df_channels, channel_df])
            full_df_runs = pd.concat([full_df_runs, run_df])

        self.channel_summary = full_df_channels.reset_index(drop=True)
        self.run_summary = full_df_runs.reset_index(drop=True)

    def _refresh_channels_tab(self):
        if self.choose_runs:
            self.channels_table.value = self.run_summary[RUN_SUMMARY_DISPLAY_COLUMNS]
        else:
            self.channels_table.value = self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS]

    def _update_selected_from_table(self, selection):
        self.selected_channels = {}
        self.selected_runs = {}
        if not selection:
            return

        if self.choose_runs:
            for idx in selection:
                row = self.run_summary.iloc[idx]
                self.selected_runs.setdefault(row["file"], []).append(
                    row["hdf5_reference"]
                )
        else:
            for idx in selection:
                row = self.channel_summary.iloc[idx]
                self.selected_channels.setdefault(row["file"], []).append(
                    row["hdf5_reference"]
                )

    def _build_data_dict(self):
        """
        Build self.data_dict: key -> xarray object
        """
        out_dict = {}
        self.datashade_cache = {}

        if self.choose_runs:
            for mth5_fn, runs in self.selected_runs.items():
                with MTH5() as m:
                    m.open_mth5(mth5_fn, mode="r")
                    for run_hdf5_path in runs:
                        run = m.from_reference(run_hdf5_path)
                        data = run.to_runts().dataset
                        run_key = (
                            f"{run.survey_metadata.id}."
                            f"{run.station_metadata.id}."
                            f"{run.metadata.id}"
                        )
                        out_dict[run_key] = data
        else:
            for mth5_fn, channels in self.selected_channels.items():
                with MTH5() as m:
                    m.open_mth5(mth5_fn, mode="r")
                    for hdf5_path in channels:
                        ch = m.from_reference(hdf5_path)
                        data = ch.to_channel_ts().to_xarray()
                        ch_key = (
                            f"{ch.survey_metadata.id}."
                            f"{ch.station_metadata.id}."
                            f"{ch.run_metadata.id}."
                            f"{ch.metadata.component}"
                        )
                        out_dict[ch_key] = data

        self.data_dict = out_dict

    # =========================================================
    # Color logic
    # =========================================================
    def _get_semantic_color(self, ch_key):
        """
        Determine channel color based on MT semantics:
        - Electric: starts with 'e'
        - Magnetic: starts with 'h' or 'b'
        - Auxiliary: anything else
        """
        component = ch_key.split(".")[-1].lower()

        if component.startswith("e"):
            palette = self.semantic_electric_palette
            index = self.electric_index_map.setdefault(
                component, len(self.electric_index_map)
            )
        elif component.startswith("h") or component.startswith("b"):
            palette = self.semantic_magnetic_palette
            index = self.magnetic_index_map.setdefault(
                component, len(self.magnetic_index_map)
            )
        else:
            palette = self.semantic_aux_palette
            index = self.aux_index_map.setdefault(component, len(self.aux_index_map))

        return palette[index % len(palette)]

    def _get_channel_color(self, ch_key, index):
        """
        Returns the color for a channel based on:
        - lock_color_identity checkbox
        - palette_selector choice
        """
        if self.lock_color_identity.value:
            return self._get_semantic_color(ch_key)

        mode = self.palette_selector.value

        if mode == "semantic":
            return self._get_semantic_color(ch_key)

        elif mode == "glasbey":
            return self.vibrant_palette[index % len(self.vibrant_palette)]

        elif mode == "viridis":
            return self.viridis_palette[index % len(self.viridis_palette)]

        return self.vibrant_palette[index % len(self.vibrant_palette)]

    # =========================================================
    # Plotting pipeline
    # =========================================================
    def _build_or_update_plots(self):
        """
        Build or update per-channel panes in self.plot_panes
        based on self.data_dict and current settings.
        """
        self.plot_panes = {}
        keys = list(self.data_dict.keys())

        for idx, key in enumerate(keys):
            data = self.data_dict[key]

            if self.subtract_mean:
                if isinstance(data, xarray.DataArray):
                    data = data - data.mean()
                elif isinstance(data, xarray.Dataset):
                    data = data - data.mean()

            if self.choose_runs and isinstance(data, xarray.Dataset):
                for j, ch in enumerate(data.data_vars):
                    ch_da = data[ch]
                    ch_key = f"{key}.{ch_da.component}"
                    color_index = idx + j
                    pane = self._make_channel_pane(ch_da, ch_key, color_index)
                    self.plot_panes[ch_key] = pane
            else:
                color_index = idx
                pane = self._make_channel_pane(data, key, color_index)
                self.plot_panes[key] = pane

        self._init_row_assignments()

    def _make_channel_pane(self, ch_data, ch_key, color_index):
        """
        Create a pn.pane.HoloViews for a single channel with fully dynamic
        datashader behavior (resamples on zoom/pan).
        """

        color = self._get_channel_color(ch_key, color_index)

        # Base hvPlot curve (static)
        plot_fn = hvplot.hvPlot(
            ch_data,
            height=self.plot_height,
            cmap=self.colormap,
            ylabel=getattr(ch_data, "units", ""),
            title=ch_key,
            responsive=True,
            max_width=self.plot_width_max,
            xlabel="",
        )

        base_curve = plot_fn(shared_axes=True)

        # Decide if datashader is needed
        use_datashader = len(ch_data) > DATASHADE_THRESHOLD

        if use_datashader:
            # Wrap base curve in a DynamicMap so datashader stays dynamic
            # dmap = hv.DynamicMap(lambda: base_curve)

            # Apply datashader dynamically
            shaded = datashade(
                base_curve,
                aggregator="any",
                height=self.plot_height,
            )

            # Hover overlay (static decimated curve)
            hover_curve = decimate(base_curve).opts(
                color=color,
                line_width=1.5,
                tools=["hover"],
            )

            # Combine dynamic raster + static hover
            curve = shaded * hover_curve

        else:
            # No datashader needed
            curve = base_curve.opts(color=color, tools=["hover"])

        # Styling
        curve = curve.opts(
            show_grid=True,
            gridstyle={"grid_line_color": "lightgray", "grid_line_alpha": 0.5},
            xticks=20,
        )

        # IMPORTANT: return the HoloViews object directly, not a Pane
        # Wrapping in a Pane freezes dynamic behavior.
        return pn.pane.HoloViews(
            curve,
            sizing_mode="stretch_width",
            max_width=self.plot_width_max,
        )

    def _init_row_assignments(self):
        keys = list(self.plot_panes.keys())
        if not self.subplot_row_assignments or set(
            self.subplot_row_assignments.keys()
        ) != set(keys):
            self.subplot_row_assignments = {key: i + 1 for i, key in enumerate(keys)}
            self._ordering_version += 1

    def _update_subplot_row_selectors(self):
        self.subplot_row_panel.clear()
        keys = list(self.plot_panes.keys())
        n = len(keys)
        row_options = [str(i + 1) for i in range(n)]

        for key in keys:
            current_row = self.subplot_row_assignments.get(key, 1)
            selector = pn.widgets.Select(
                options=row_options,
                value=str(current_row),
                width=60,
            )

            def _make_callback(k):
                def _cb(event):
                    self.subplot_row_assignments[k] = int(event.new)
                    self._ordering_version += 1
                    self._render_plots()

                return _cb

            selector.param.watch(_make_callback(key), "value")
            row = pn.Row(pn.pane.Markdown(f"**{key}**", width=200), selector)
            self.subplot_row_panel.append(row)

    def _reset_ordering(self, event=None):
        keys = list(self.plot_panes.keys())
        self.subplot_row_assignments = {k: i + 1 for i, k in enumerate(keys)}
        self._ordering_version += 1
        self._update_subplot_row_selectors()
        self._render_plots()

    def _render_plots(self):
        if not self.plot_panes:
            self.graphs.objects = []
            return

        row_map = {}
        for key, row_idx in self.subplot_row_assignments.items():
            row_map.setdefault(row_idx, []).append(key)

        sorted_rows = sorted(row_map.keys())
        panes = []

        for row_idx in sorted_rows:
            keys = row_map[row_idx]
            if not keys:
                continue

            if not self.combine_subplots or len(keys) == 1:
                panes.append(self.plot_panes[keys[0]])
            else:
                hv_objs = [self.plot_panes[k].object for k in keys]

                # Build overlay and collate to merge DynamicMaps correctly
                overlay = hv.Overlay(hv_objs).collate()

                pane = pn.pane.HoloViews(
                    overlay,
                    sizing_mode="stretch_width",
                    max_width=self.plot_width_max,
                )
                panes.append(pane)

        column = pn.Column(
            *panes,
            sizing_mode="stretch_width",
            margin=0,
            max_width=self.plot_width_max,
        )

        self.graphs.objects = [
            pn.Card(
                column,
                title="Time Series Plots",
                sizing_mode="stretch_width",
                max_width=self.plot_width_max,
            )
        ]

    # =========================================================
    # Clear / reset
    # =========================================================
    def clear_plots(self, event=None):
        self.data_dict = {}
        self.plot_panes = {}
        self.datashade_cache = {}
        self.subplot_row_assignments = {}
        self.graphs.objects = []
        self.subplot_row_panel.clear()

    def clear_channels(self, event=None):
        self.selected_channels = {}
        self.selected_runs = {}
        self.channel_summary = pd.DataFrame(columns=CHANNEL_DTYPE.names)
        self.run_summary = pd.DataFrame(columns=RUN_SUMMARY_DTYPE.names)
        self._refresh_channels_tab()

    # =========================================================
    # Resource Streaming
    # =========================================================
    def _start_resource_stream(self):
        def update_resources():
            mem = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent()
            self.cpu_usage.value = cpu
            self.memory_usage.value = mem

        pn.state.add_periodic_callback(update_resources, period=1000)

    # =========================================================
    # Entry Point
    # =========================================================
    def view(self):
        return self.template


tsvi = Tsvi(plot_width=700, plot_height=200)
tsvi.template.servable()
