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
    channel_summary_columns_to_display,
    cpu_usage_widget,
    memory_usage_widget,
    make_plots,
)

hv.extension("bokeh")
xarray.set_options(keep_attrs=True)

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
]
COLORMAP = "Magma"


class Tsvi(param.Parameterized):

    # Resource widgets (static)
    cpu_usage = cpu_usage_widget()
    memory_usage = memory_usage_widget()

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

        self.plotting_library = pn.widgets.RadioButtonGroup(
            name="Plotting Library",
            options=["bokeh", "matplotlib"],
            button_type="primary",
            width=200,
        )

        self.subtract_mean_checkbox = pn.widgets.Checkbox(
            name="Subtract Mean", value=True
        )

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
            self.plotting_library,
            self.subtract_mean_checkbox,
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
        if event.new:
            for idx in event.new:
                row = self.channel_summary.iloc[idx]
                self.selected_channels.setdefault(row["file"], []).append(
                    row["hdf5_reference"]
                )

    def make_and_display_plots(self, *args):
        self.tabs.active = 1
        self.make_plots()
        self.display_plots()

    def make_plots(self):
        make_plots(self)

    def display_plots(self):
        self.graphs.objects = list(self.plots.values())

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
