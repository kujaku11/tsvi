#!/usr/bin/env python
# coding: utf-8
"""
There are four main Panels in this UI
- Sidebar
- Folders
- Channels
- Plot

"""
#get_ipython().run_line_magic('matplotlib', 'widget')

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
import psutil
import time
import xarray

import mt_metadata
import mth5
from mth5.mth5 import MTH5

from tsvi.mth5_tsviewer.helpers import channel_summary_columns_to_display
from tsvi.mth5_tsviewer.helpers import cpu_usage_widget
from tsvi.mth5_tsviewer.helpers import list_h5s_to_plot
from tsvi.mth5_tsviewer.helpers import memory_usage_widget



# ipynb command
#pn.extension("ipywidgets")

hv.extension("bokeh")
hv.extension("matplotlib")

xarray.set_options(keep_attrs = True)

# Make template choice dictionary
# More information about template choices and functionality is here:
# https://panel.holoviz.org/user_guide/Templates.html
TEMPLATES = {}
TEMPLATES["bootstrap"] = pn.template.BootstrapTemplate
TEMPLATES["fast"] = pn.template.FastListTemplate
TEMPLATES["golden"] = pn.template.GoldenTemplate
TEMPLATES["grid"] = pn.template.FastGridTemplate

# Define Template for this instance
template_key = "golden"
template = TEMPLATES[template_key]

displayed_columns = channel_summary_columns_to_display()


def create_button(button_type):
    pass

class Tsvi(template):

    cpu_usage = cpu_usage_widget()
    memory_usage = memory_usage_widget()
    streaming_resources = False
        
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plot_width = kwargs.get("plot_width", 900)
        self.plot_height = kwargs.get("plot_height", 450)

        self.cache = {}
        self.file_paths = {}
        self.xarrays = []
        
        # Tab Creation
        self.tabs = pn.Tabs(self.make_folders_tab(),
                            self.make_channels_tab(),
                            self.make_plots_tab(),
                            closable = False,
                            dynamic = False)

        # Annotator
        self.annotator = hv.annotate.instance()
        self.note_boxes = self.annotator(hv.Rectangles(data = None).opts(alpha = 0.5))

        self.main.append(self.tabs)
        
        # Sidebar
        self.make_sidebar()
        self.start_resource_stream()
        

    def make_sidebar(self):
        #Define Checkboxes and Buttons
        self.datashade_checkbox = pn.widgets.Checkbox(name="Datashade", value=True)
        self.shared_axes_checkbox = pn.widgets.Checkbox(name="Shared Axes", value=True)
        self.clear_plots_button = pn.widgets.Button(name="Clear Plots",
                                                    button_type="danger",
                                                    width = 200)
        self.clear_plots_button.on_click(self.clear_plots)
        self.clear_channels_button = pn.widgets.Button(name="Clear Channels",
                                                       button_type="danger",
                                                       width=200)
        self.clear_channels_button.on_click(self.clear_channels)
        # Set up Layout
        self.sidebar.append(self.cpu_usage)
        self.sidebar.append(self.memory_usage)
        self.sidebar.append(self.datashade_checkbox)
        self.sidebar.append(self.shared_axes_checkbox)
        self.sidebar.append(self.clear_plots_button)
        self.sidebar.append(self.clear_channels_button)
        self.start_resource_stream()

    def make_folders_tab(self):
        self.files = pn.widgets.FileSelector(name = "Files",
                                             directory = "~",
                                             file_pattern = "*.h5",
                                             height = 550
                                             )
        self.select_button = pn.widgets.Button(name="Select Files",
                                               button_type="primary")
        self.select_button.on_click(self.update_channels)

        tab = pn.Column(self.files, self.select_button, name = "Folders")

        return tab

    def make_channels_tab(self):
        self.channels = pn.widgets.MultiSelect(objects = [],
                                               name = "Channels",
                                               height = 200)
        self.plot_button = pn.widgets.Button(name = "Plot", button_type = "primary")
        self.plot_button.on_click(self.make_and_display_plots)
        self.channel_summary = pd.DataFrame(columns = displayed_columns)
        self.summary_display = pn.widgets.DataFrame(self.channel_summary,
                                                    height = 500,
                                                    width = 1000)
        self.channels.link(self.summary_display, callbacks = {"value": self.display_channel_summary})

        # Controls
        self.plotting_library = pn.widgets.RadioButtonGroup(name="Plotting Library",
                                                            options = ["bokeh",
                                                                       "matplotlib",
                                                                       #"plotly"
                                                                       ],
                                                            button_type = "primary",
                                                            width = 200)
        self.subtract_mean_checkbox= pn.widgets.Checkbox(name = "Subtract Mean",
                                                         value = True)

        channel_and_plot = pn.Column(self.channels, self.plot_button)
        controls = pn.Column(self.plotting_library, self.subtract_mean_checkbox)

        tab = pn.Column(pn.Row(channel_and_plot, controls,),
                        self.summary_display,
                        name="Channels")
        return tab

    def make_plots_tab(self):
        self.plot_cards = []
        self.graphs = pn.Column()
        tab = pn.Column(self.graphs, name="Plot")
        return tab


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
     
    
    def update_channels(self, *args, **kwargs):
        new_channels = []
        for file_path in self.files.value:
            file_name = file_path.split("/")[-1] #This might not work on Windows
            self.file_paths[file_name] = file_path
            m = MTH5()
            m.open_mth5(file_path, mode = "r")
            df = m.channel_summary.to_dataframe()
            m.close_mth5()
            df["file"] = file_name
            df["channel_path"] = (df["file"] + "/" + df["station"] + "/" + df["run"] + "/" + df["component"])
            df.set_index("channel_path", inplace = True)
            self.cache[file_name] = df
            new_channels.extend(self.cache[file_name].index)
        self.channels.options = list(new_channels)
        self.tabs.active = 1
        return
    
    def clear_channels(self, *args, **params):
        self.channels.options = list()
        return
        
    def display_channel_summary(self, target,  event):
        display_df = pd.DataFrame()
        for channel in event.new:
            display_df = pd.concat([display_df,(tsvi.cache[channel.split("/")[0]].loc[[channel], displayed_columns])])
        target.value = display_df
        return
    
    
    def mth5s_to_xarrays(self):
        #TODO: Look in to chunking at this level check if possible to extract slice at channel level, similar to run level
        used_files = list_h5s_to_plot(self.channels.value)
        for file in used_files:
            m = MTH5()
            m.open_mth5(self.file_paths[file], mode = "r")
            for selected_channel in self.channels.value:
                selected_file, station, run, channel = selected_channel.split("/")
                if selected_file == file:
                    data = m.get_channel(station, run, channel).to_channel_ts().to_xarray()
                    self.xarrays.append(data.rename(data.attrs["mth5_type"]))
            m.close_mth5()
                    
    def preprocess_xarrays(self):
        for xarray in self.xarrays:
            if self.subtract_mean_checkbox.value == True:
                xarray = xarray - xarray.mean()

    def make_plots(self):
        hv.output(backend = self.plotting_library.value)
        new_cards  = []
        used_files = list_h5s_to_plot(self.channels.value)
        # The following for loop doesn't need 3 layers,
        # Better may be to use a dataframe with one column for "file", "station",
        # "run", "channel"
	# This would also allow group-by plotting, etc.
        for file in used_files:
            m = MTH5()
            m.open_mth5(self.file_paths[file], mode = "r")
            for selected_channel in self.channels.value:
                selected_file, station, run, channel = selected_channel.split("/")
                if selected_file == file:
                    data = m.get_channel(station, run, channel).to_channel_ts().to_xarray()
                    ###Cut Here###
                    ylabel = data.type
                    if self.subtract_mean_checkbox.value == True:
                        data = data - data.mean()
                    ###Cut Here###
                    plot = hvplot.hvPlot(data,
                                         width = self.plot_width,
                                         height = self.plot_height,
                                         ylabel = ylabel)
                    if self.plotting_library.value == "bokeh":
                        bound_plot = pn.bind(plot,
                                             datashade = self.datashade_checkbox,
                                             shared_axes = self.shared_axes_checkbox)
                        #bound_plot = plot
                        #bound_plot = data.hvplot()
                    elif self.plotting_library.value == "matplotlib":
                        fig = Figure(figsize = (8,6))
                    
                    annotate_button       = pn.widgets.Button(name = "Annotate", button_type = "primary", width = 100)
                    invert_button         = pn.widgets.Button(name = "Invert", button_type = "primary", width = 100)
                    
                    # Fails becuse "event" not defined below
                    # def invert(self, *args, **params):
                    #   data = -1 * data
                    #
                    # invert_button.on_click(invert(event, data))
                    controls = pn.Column(annotate_button,
                                       invert_button,
                                       sizing_mode = "fixed", width = 200,)
                    plot_pane = pn.Pane(bound_plot)
                    plot_tab = pn.Row(plot_pane,
                                      controls,
                                      name = run + "/" + channel)
                    tabs = pn.Tabs(plot_tab)
                    
                    def annotate(self, *args, **params):
                        plot2 = hv.Curve(data)
                        notes = hv.annotate.instance()
                        note_tab = pn.Row(notes.compose(plot2, (hv.Rectangles(data = None).opts(alpha = 0.5))),
                                          name = "Annotate")
                        tabs.append(note_tab)
                        tabs.active = 1
                    
                    annotate_button.on_click(annotate)
                    
                    
                    new_card = pn.Card(tabs,
                                       title = selected_channel)
                    
                    new_cards.append(new_card)
            m.close_mth5()
        self.plot_cards = new_cards
        return

    
    
    def display_plots(self):
        for plot in self.plot_cards:
            self.graphs.append(plot)
        return
        
    def make_and_display_plots(self, *args, **kwargs):
        self.tabs.active = 2
        self.make_plots()
        self.display_plots()
        #self.tabs.active = 2
        return

    def clear_plots(self, event):
        self.xarrays = [] 
        old_graphs = self.graphs
        self.graphs.objects = []
        del old_graphs.objects[:]
        self.graphs.objects = []
        del self.plot_cards[:]

    def annotate(self, *args, **params):
        plot2 = hv.Curve(data)
        notes = hv.annotate.instance()
        note_tab = pn.Row(notes.compose(plot2, (hv.Rectangles(data = None).opts(alpha = 0.5))),
                        name = "Annotate")
        tabs.append(note_tab)
        tabs.active = 1
            
    


# In[9]:


tsvi = Tsvi(plot_width=900, plot_height=200)
tsvi.show()


# In[35]:


"""

Some things to be aware of between Datashader and Annotators. Datashader converts a holoviews.element
into a holoviews.core.spaces.DynamicMap. When .compose() -ing an Annotator, it requires elements, not DynamicMaps.
This means that the annotator won't work on a Datashaded plot.

One work around is to create a second plot that does not dynamically change between element and DynamicMap
with the push of a button and have this plot be used for the annotator. This works but it means that there are
two different plot objects created for each plot and doubles the loading time for each plot.
"""


# In[16]:
#
#
# tsvi.xarrays



#%matplotlib
#import matplotlib.pyplot as plt


#hv.output(backend = "bokeh")
#pn.extension("ipywidgets")




