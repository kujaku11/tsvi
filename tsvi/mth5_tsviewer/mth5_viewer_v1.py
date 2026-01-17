#!/usr/bin/env python
# coding: utf-8
"""
There are four main Panels in this UI
- Sidebar
- Folders
- Channels
- Plot

"""

import h5py
from matplotlib.backends.backend_agg import FigureCanvas
from matplotlib.figure import Figure

import bokeh
import holoviews as hv
import hvplot
import hvplot.xarray
import matplotlib as plt
import numpy as np
import pandas as pd
import panel as pn
import pathlib
import psutil
import time
import xarray

import mt_metadata
import mth5
from mth5.mth5 import MTH5
from mth5 import CHANNEL_DTYPE


from tsvi.mth5_tsviewer.helpers import channel_summary_columns_to_display
from tsvi.mth5_tsviewer.helpers import cpu_usage_widget
from tsvi.mth5_tsviewer.helpers import get_templates_dict
from tsvi.mth5_tsviewer.helpers import make_plots
from tsvi.mth5_tsviewer.helpers import list_h5s_to_plot
from tsvi.mth5_tsviewer.helpers import memory_usage_widget


hv.extension("bokeh")
hv.extension("matplotlib")

xarray.set_options(keep_attrs=True)

# Define Template for this instance
TEMPLATES = get_templates_dict()
template_key = "golden"
template = TEMPLATES[template_key]

CH_SUMMARY_DISPLAY_COLUMNS = channel_summary_columns_to_display()

COLORMAP = "Magma"


class Tsvi(template):
    # some of these should be ivars maybe
    cpu_usage = cpu_usage_widget()
    memory_usage = memory_usage_widget()
    streaming_resources = False

    def __init__(self, *args, **kwargs):
        """
        instance variables:
        self.file_paths: dict
            Keys are
        Parameters
        ----------
        args
        kwargs
        """
        super().__init__(*args)
        self.plot_width = kwargs.get("plot_width", 900)
        self.plot_height = kwargs.get("plot_height", 450)
        self.annotatable = kwargs.get("annotatable", False)  # True)
        self.colormap = COLORMAP
        self.channel_summary_dict = {}
        self.file_paths = {}
        self.xarrays = []
        self.plots = {}
        self.channel_summary = pd.DataFrame(columns=CHANNEL_DTYPE.names)
        self.selected_channels = {}

        # Tab Creation
        self.tabs = pn.Tabs(
            self.make_folders_tab(),
            self.make_channels_tab(),
            self.make_plots_tab(),
            closable=False,
            dynamic=False,
        )
        self.main.append(self.tabs)

        # Annotator
        if self.annotatable:
            self.annotators = {}

        # Sidebar
        self.make_sidebar()

    def make_sidebar(self):
        button_width = 150
        # Define Checkboxes and Buttons
        self.datashade_checkbox = pn.widgets.Checkbox(name="Datashade", value=True)
        self.shared_axes_checkbox = pn.widgets.Checkbox(name="Shared Axes", value=True)

        self.clear_plots_button = pn.widgets.Button(
            name="Clear Plots", button_type="danger", width=button_width
        )
        self.clear_plots_button.on_click(self.clear_plots)

        self.clear_channels_button = pn.widgets.Button(
            name="Clear Channels", button_type="danger", width=button_width
        )
        self.clear_channels_button.on_click(self.clear_channels)

        self.save_notes_input = pn.widgets.TextInput(
            value="Notes.csv", name="Save to .csv"
        )
        self.save_notes_button = pn.widgets.Button(
            name="Save Notes", button_type="success", width=button_width
        )
        self.save_notes_button.on_click(self.save_notes)

        self.load_notes_input = pn.widgets.TextInput(
            value="Notes.csv", name="Load from .csv"
        )
        self.load_notes_button = pn.widgets.Button(
            name="Load Notes", button_type="success", width=button_width
        )
        self.load_notes_button.on_click(self.load_notes)

        self.clear_notes_button = pn.widgets.Button(
            name="Clear Notes", button_type="danger", width=button_width
        )
        self.clear_notes_button.on_click(self.clear_notes)

        self.layout_sidebar()

    def layout_sidebar(self):
        self.sidebar.append(self.cpu_usage)
        self.sidebar.append(self.memory_usage)
        self.sidebar.append(self.datashade_checkbox)
        self.sidebar.append(self.shared_axes_checkbox)
        self.sidebar.append(self.clear_plots_button)
        self.sidebar.append(self.clear_channels_button)
        self.sidebar.append(self.save_notes_input)
        self.sidebar.append(self.save_notes_button)
        self.sidebar.append(self.load_notes_input)
        self.sidebar.append(self.load_notes_button)
        self.sidebar.append(self.clear_notes_button)

    def make_folders_tab(self):
        self.files = pn.widgets.FileSelector(
            name="Files",
            directory="~",
            file_pattern="*.h5",
            height=550,
        )
        self.select_button = pn.widgets.Button(
            name="Select Files", button_type="primary"
        )
        self.select_button.on_click(self.update_channels)
        tab = pn.Column(self.files, self.select_button, name="Folders")
        return tab

    def make_channels_tab(self):
        # self.channels = pn.widgets.MultiSelect(options=[], name="Channels", height=200)
        self.channels = pn.widgets.Tabulator(
            self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS],
            selectable=True,
            height=500,
        )
        self.channels.param.watch(self.select_channels, "selection")

        # plot selected channels button
        self.plot_button = pn.widgets.Button(name="Plot", button_type="primary")
        self.plot_button.on_click(self.make_and_display_plots)

        # self.summary_display = pn.widgets.DataFrame(
        #     self.channel_summary, height=500, width=1000
        # )
        # self.channels.link(
        #     self.summary_display, callbacks={"value": self.display_channel_summary}
        # )

        # Controls
        self.plotting_library = pn.widgets.RadioButtonGroup(
            name="Plotting Library",
            options=[
                "bokeh",
                "matplotlib",
                # "plotly"
            ],
            button_type="primary",
            width=200,
        )
        self.subtract_mean_checkbox = pn.widgets.Checkbox(
            name="Subtract Mean", value=True
        )

        channel_and_plot = pn.Column(self.channels, self.plot_button)
        controls = pn.Column(self.plotting_library, self.subtract_mean_checkbox)

        tab = pn.Column(
            pn.Row(
                channel_and_plot,
                controls,
            ),
            # self.summary_display,
            name="Channels",
        )
        return tab

    def make_plots_tab(self):
        self.plot_cards = []
        self.graphs = pn.Column(sizing_mode="stretch_width", margin=0, max_width=1000)
        tab = pn.Column(self.graphs, name="Plot")
        return tab

    # def make_help_tab(self):
    #    tab = pn.panel()
    #    return

    def start_resource_stream(self):
        if self.streaming_resources:
            return

        def resouce_usage_psutil():
            return psutil.virtual_memory().percent, psutil.cpu_percent()

        def stream_resourcesx():
            mem, cpu = resouce_usage_psutil()
            self.cpu_usage.value = cpu
            self.memory_usage.value = mem

        pn.state.add_periodic_callback(stream_resourcesx, period=1000, count=None)
        self.streaming_resources = True

    def update_channels(self, event):
        """
        This populates the channel_list in the Channels Tab

        h5py References are not JSON serializable, so we convert them to bytes.  It is
        suggested to store the path instead, but this is more straightforward for now.

        N.B. If you had two mth5 files in two different directories, but with the same
        filename, you will encounter problems.

        Parameters
        ----------
        event: param.parameterized.Event
            A dummy variable needed for onclick (and param watchers in general)
        """
        full_df = pd.DataFrame()
        for file_path in self.files.value:
            file_path = pathlib.Path(file_path)
            # file_name = file_path.name
            # self.file_paths[file_name] = file_path
            with MTH5() as m:
                m = m.open_mth5(file_path, mode="r")
                df = m.channel_summary.to_dataframe()
                df["file"] = file_path.as_posix()
                # Store the HDF5 path instead of reference bytes
                df["hdf5_reference"] = df["hdf5_reference"].apply(
                    lambda ref: m.get_reference_path(ref)
                )
                df.drop(
                    columns=["run_hdf5_reference", "station_hdf5_reference"],
                    inplace=True,
                )

            full_df = pd.concat([full_df, df])
        self.channel_summary = full_df.reset_index(drop=True)
        self.channels.value = self.channel_summary[CH_SUMMARY_DISPLAY_COLUMNS]
        self.tabs.active = 1  # swicth user to tab 1
        return

    def select_channels(self, event):
        """
        create a dict of selected channels from the tabulator selection where
        the keys are file names and the values are lists of channel references
        within that file.

        Parameters
        ----------
        event : _type_
            _description_
        """
        self.selected_channels = {}
        if event.new:
            for idx in event.new:
                row = self.channel_summary.iloc[idx]
                file_name = row["file"]
                channel_reference = row["hdf5_reference"]
                try:
                    self.selected_channels[file_name].append(channel_reference)
                except KeyError:
                    self.selected_channels[file_name] = [channel_reference]

    def clear_channels(self, event):
        self.selected_channels = {}
        return

    # def display_channel_summary(self, target, event):
    #     dfs = []
    #     display_df = pd.DataFrame()
    #     for channel in event.new:
    #         key = channel.split("/")[0]
    #         dfs.append(
    #             self.channel_summary_dict[key].loc[
    #                 [channel], CH_SUMMARY_DISPLAY_COLUMNS
    #             ]
    #         )
    #     display_df = pd.concat(dfs)
    #     target.value = display_df
    #     return

    def preprocess_xarrays(self):
        for xarray in self.xarrays:
            if self.subtract_mean_checkbox.value == True:
                xarray = xarray - xarray.mean()

    def make_plots(self):
        make_plots(self)

    def display_plots(self):
        for plot in self.plot_cards:
            self.graphs.append(plot)
        return

    def make_and_display_plots(self, *args, **kwargs):
        self.tabs.active = 2
        self.make_plots()
        self.display_plots()
        return

    def clear_plots(self, event):
        self.xarrays = []
        old_graphs = self.graphs
        self.graphs.objects = []
        del old_graphs.objects[:]
        self.graphs.objects = []
        del self.plot_cards[:]

    def save_notes(self, event):
        # Save notes from annotator dataframe to csv
        df_combined = pd.concat(
            [
                annotator.annotated.dframe().assign(run=label)
                for annotator, label in zip(
                    self.annotators.values(), self.annotators.keys()
                )
            ]
        )
        df_combined.to_csv(self.save_notes_input.value, index=False)

    def load_notes(self, event):
        return

    def clear_notes(self, event):
        # Clear annotator dataframe
        return


tsvi = Tsvi(plot_width=700, plot_height=200)
tsvi.start_resource_stream()
tsvi.servable()
