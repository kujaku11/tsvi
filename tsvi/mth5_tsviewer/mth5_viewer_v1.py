import pathlib
import pandas as pd
import panel as pn
import param
import psutil
import xarray

import holoviews as hv
import hvplot.xarray

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
# Threshold for enabling datashader
DATASHADE_THRESHOLD = 200_000
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
    """
    Make template choice dictionary
    More information about template choices and functionality is here:
    https://panel.holoviz.org/user_guide/Templates.html
    Returns
    templates: dict

    -------

    """
    templates = {}
    templates["bootstrap"] = pn.template.BootstrapTemplate
    templates["fast"] = pn.template.FastListTemplate
    templates["golden"] = pn.template.GoldenTemplate
    templates["grid"] = pn.template.FastGridTemplate
    return templates


# =========================================================
# Main TSVI Class
# =========================================================
class Tsvi(param.Parameterized):
    """
    A simple Panel application to plot timeseries contained
    within a MTH5 file.

    Parameters
    ----------
    param : _type_
        _description_

    Returns
    -------
    _type_
        _description_
    """

    # Parameters
    plot_width = param.Integer(default=900)
    plot_height = param.Integer(default=450)
    annotatable = param.Boolean(default=False)
    choose_runs = param.Boolean(default=False)
    plot_width_max = param.Integer(default=1000)
    colormap = param.String(default=COLORMAP)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # -------------------------
        # Template
        # -------------------------
        from tsvi.mth5_tsviewer.helpers import get_templates_dict

        template_key = "golden"
        self.template = get_templates_dict()[template_key](title="TSVI")

        # -------------------------
        # State
        # -------------------------
        self.channel_summary = pd.DataFrame(columns=CHANNEL_DTYPE.names)
        self.run_summary = pd.DataFrame(columns=RUN_SUMMARY_DTYPE.names)
        self.selected_channels = {}
        self.selected_runs = {}
        self.xarrays = []
        self.plots = {}

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

        self.run_or_channel_checkbox = pn.widgets.Checkbox(
            name="Pick Runs", value=False
        )
        self.run_or_channel_checkbox.param.watch(self.choose_runs_or_channels, "value")

        self.clear_plots_button = pn.widgets.Button(
            name="Clear Plots", button_type="danger"
        )
        self.clear_plots_button.on_click(self.clear_plots)

        self.clear_channels_button = pn.widgets.Button(
            name="Clear Channels", button_type="danger"
        )
        self.clear_channels_button.on_click(self.clear_channels)

        self.plot_button = pn.widgets.Button(name="Plot", button_type="primary")
        self.plot_button.on_click(self.make_and_display_plots)

        self.subtract_mean_checkbox = pn.widgets.Checkbox(
            name="Subtract Mean", value=True
        )
        # Subplot row selectors (initialized empty, populated after plots are made)
        self.subplot_row_selectors = {}  # key: channel key, value: Select widget
        self.subplot_row_panel = pn.Column(name="Subplot Row Assignment")
        # No plot_order_selector to watch; selectors will be created dynamically

        # -------------------------
        # Tabs
        # -------------------------
        self.files_tab = self.make_files_tab()
        self.df_tab = self.make_df_tab()
        self.plots_tab = self.make_plots_tab()

        self.tabs = pn.Tabs(
            ("Files", self.files_tab),
            ("DataFrame", self.df_tab),
            ("Plots", self.plots_tab),
            dynamic=False,
        )

        # -------------------------
        # Sidebar
        # -------------------------
        self.build_sidebar()

        # -------------------------
        # Layout
        # -------------------------
        self.template.main[:] = [self.tabs]

        # -------------------------
        # Resource streaming
        # -------------------------
        self.start_resource_stream()

    # =========================================================
    # Sidebar
    # =========================================================
    def build_sidebar(self):
        self.template.sidebar[:] = [
            self.cpu_usage,
            self.memory_usage,
            self.run_or_channel_checkbox,
            self.subtract_mean_checkbox,
            self.subplot_row_panel,
            self.plot_button,
            self.clear_plots_button,
            self.clear_channels_button,
        ]

    # =========================================================
    # Tabs
    # =========================================================
    def make_files_tab(self):
        # FileSelector at the top
        self.files = pn.widgets.FileSelector(
            name="Select MTH5 Files",
            directory="~",
            file_pattern="*.h5",
            sizing_mode="stretch_width",
        )
        self.files.param.watch(self.update_channels, "value")

        return pn.Column(self.files, sizing_mode="stretch_width")

    def make_df_tab(self):

        # Tabulator below
        self.channels_table = pn.widgets.Tabulator(
            self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS],
            selectable=True,
            sizing_mode="stretch_both",
            margin=(10, 0, 0, 0),
        )
        self.channels_table.param.watch(self.select_channels, "selection")

        # Layout: FileSelector (row 1), Tabulator (row 2)
        return pn.Column(self.channels_table, sizing_mode="stretch_width")

    def make_plots_tab(self):
        self.graphs = pn.Column(
            sizing_mode="stretch_width",
            margin=0,
            max_width=1000,
        )
        return pn.Column(self.graphs, sizing_mode="stretch_width")

    # =========================================================
    # Callbacks
    # =========================================================
    def choose_runs_or_channels(self, event):
        if event.new:
            self.choose_runs = True
            print("Choosing runs")
        else:
            self.choose_runs = False
            print("Choosing channels")

        self.refresh_channels_tab()

    def update_channels(self, event):
        print("Selected files:", event.new)

        full_df_channels = pd.DataFrame()
        full_df_runs = pd.DataFrame()
        for file_path in event.new:  # event.new is list[pathlib.Path]
            print(f"Processing file: {file_path}")
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
        self.refresh_channels_tab()
        self.tabs.active = 0

    def refresh_channels_tab(self):
        if self.choose_runs:
            self.channels_table.value = self.run_summary[RUN_SUMMARY_DISPLAY_COLUMNS]
        else:
            self.channels_table.value = self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS]

    def select_channels(self, event):
        self.selected_channels = {}
        self.selected_runs = {}
        if event.new:
            for idx in event.new:
                if self.choose_runs:
                    row = self.run_summary.iloc[idx]
                    self.selected_runs.setdefault(row["file"], []).append(
                        row["hdf5_reference"]
                    )
                else:
                    row = self.channel_summary.iloc[idx]
                    self.selected_channels.setdefault(row["file"], []).append(
                        row["hdf5_reference"]
                    )

    def make_and_display_plots(self, *args):
        self.tabs.active = 2
        self.make_plots()
        self.display_plots()

    def plot_channel_data(self, ch_data, ch_key):

        # Decide whether to use datashader
        use_datashader = len(ch_data) > DATASHADE_THRESHOLD

        plot_fn = hvplot.hvPlot(
            ch_data,
            height=self.plot_height,
            cmap=self.colormap,
            ylabel=ch_data.units,
            title=ch_key,
            responsive=True,
            max_width=self.plot_width_max,
            xlabel="",
        )

        # Store callable for external use
        self.plots[ch_key] = plot_fn

        # Build the actual plot
        if use_datashader:
            curve = plot_fn(datashade=True, shared_axes=True)
        else:
            curve = plot_fn(shared_axes=True)

        # Apply axis visibility
        curve = curve.opts(
            # xaxis=xaxis_opt,
            show_grid=True,
            gridstyle={"grid_line_color": "lightgray", "grid_line_alpha": 0.5},
            xticks=20,
        )

        # Wrap in a Panel pane
        pane = pn.pane.HoloViews(
            curve, sizing_mode="stretch_width", max_width=self.plot_width_max
        )
        return pane

    def make_plots(self):
        """
        Build vertically stacked, shared-axis time-series subplots.
        Datashader is OFF by default, but automatically enabled for large datasets.
        No reactive wrapper is used.
        """

        data_dict = self.get_mth5_data_as_xarrays()
        print(f"Plotting: {data_dict.keys()}")
        panes = []
        self.plot_panes = {}  # key: plot key, value: pane

        for selected_channel, data in data_dict.items():

            # Optional preprocessing
            if self.subtract_mean_checkbox.value:
                data = data - data.mean()

            if self.choose_runs:
                for ch in data.data_vars:
                    ch_da = data[ch]
                    ch_key = f"{selected_channel}.{ch_da.component}"
                    pane = self.plot_channel_data(ch_da, ch_key)
                    self.plot_panes[ch_key] = pane
            else:
                pane = self.plot_channel_data(data, selected_channel)
                self.plot_panes[selected_channel] = pane

        # Set up subplot row selectors in the sidebar
        plot_keys = list(self.plot_panes.keys())
        self.subplot_row_selectors = {}
        self.subplot_row_panel.clear()
        n = len(plot_keys)
        row_options = [str(i + 1) for i in range(n)]
        for i, ch_key in enumerate(plot_keys):
            selector = pn.widgets.Select(
                options=row_options,
                value=row_options[i],
                width=60,
            )
            selector.param.watch(self.display_plots, "value")
            self.subplot_row_selectors[ch_key] = selector
            row = pn.Row(pn.pane.Markdown(f"**{ch_key}**", width=150), selector)
            self.subplot_row_panel.append(row)
        # Initial display
        self.display_plots()

    def get_mth5_data_as_xarrays(self):
        """
        Updated to use MTH5 context manager and selected channels dict
        is now keyed by filename and values are list of HDF5 path to the
        channel data.

        Parameters
        ----------
        selected_channels: dict
            Dictionary where keys are filenames and values are lists of HDF5 paths to the
            channel data.

        Returns
        -------

        """
        out_dict = {}
        if self.choose_runs:
            print("Getting runs")
            for mth5_fn, runs in self.selected_runs.items():
                with MTH5() as m:
                    m.open_mth5(mth5_fn, mode="r")
                    for run_hdf5_path in runs:
                        run = m.from_reference(run_hdf5_path)
                        data = run.to_runts().dataset
                        run_key = f"{run.survey_metadata.id}.{run.station_metadata.id}.{run.metadata.id}"
                        out_dict[run_key] = data
        else:
            print("Getting channels")
            for mth5_fn, channels in self.selected_channels.items():
                with MTH5() as m:
                    m.open_mth5(mth5_fn, mode="r")
                    if not self.choose_runs:
                        for hdf5_path in channels:
                            # hdf5_path is the string path to the channel (e.g., '/station/run/channel')
                            ch = m.from_reference(hdf5_path)
                            data = ch.to_channel_ts().to_xarray()
                            ch_key = f"{ch.survey_metadata.id}.{ch.station_metadata.id}.{ch.run_metadata.id}.{ch.metadata.component}"
                            out_dict[ch_key] = data

        return out_dict

    def display_plots(self, *events):
        # Group channels by subplot row number (as string)
        if not hasattr(self, "plot_panes") or not self.plot_panes:
            self.graphs.objects = []
            return

        # Build mapping: row number (str) -> list of channel keys
        row_map = {}
        for ch_key, selector in self.subplot_row_selectors.items():
            row = selector.value
            row_map.setdefault(row, []).append(ch_key)

        # Sort rows numerically
        sorted_rows = sorted(row_map.keys(), key=lambda x: int(x))
        panes = []
        for row in sorted_rows:
            keys = row_map[row]
            # Overlay all channels assigned to this row
            if len(keys) == 1:
                panes.append(self.plot_panes[keys[0]])
            else:
                # Overlay: extract HoloViews objects from panes
                overlays = [self.plot_panes[k].object for k in keys]
                from holoviews import Overlay

                overlay = overlays[0]
                for o in overlays[1:]:
                    overlay = overlay * o
                # Wrap overlay in a Panel pane
                pane = pn.pane.HoloViews(
                    overlay, sizing_mode="stretch_width", max_width=self.plot_width_max
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

    def clear_plots(self, event=None):
        self.xarrays = []
        self.plots = {}
        self.graphs.objects = []

    def clear_channels(self, event=None):
        self.selected_channels = {}
        self.channel_summary = pd.DataFrame(columns=CHANNEL_DTYPE.names)
        self.refresh_channels_tab()

    # =========================================================
    # Resource Streaming
    # =========================================================
    def start_resource_stream(self):
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
