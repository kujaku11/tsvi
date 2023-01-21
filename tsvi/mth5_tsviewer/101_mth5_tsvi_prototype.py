#!/usr/bin/env python
# coding: utf-8

# In[1]:


import param
import panel as pn
import h5py
import pandas as pd
import xarray
import mth5
from mth5.mth5 import MTH5
import numpy as np
from mth5.timeseries import ChannelTS
import mt_metadata
import hvplot
import hvplot.xarray


# In[2]:


pn.extension()


# In[3]:


channel_types = {'ex': 'electric', 'ey': 'electric',
                 'hx' : 'magnetic', 'hy' : 'magnetic', 'hz' : 'magnetic'}

def channel_typer(channel):
    channel_types = {'ex': 'electric', 'ey': 'electric',
                     'hx' : 'magnetic', 'hy' : 'magnetic', 'hz' : 'magnetic'}
    return channel_types[channel]


# In[4]:


plots = pn.Column()


# In[5]:


class Sidebar(param.Parameterized):
    
    datasets                   = {} #This and metadata should be combined into a DataFrame with 
    file_selector              = param.MultiFileSelector()
    selected_files             = param.ListSelector(objects = datasets.keys())
    
    time_series                = []
    x_arrays                   = []
    metadata_columns           = [ "channel_path",
                                   #"file",
                                   #"file_path",
                                   #"mimetype",
                                   "Station",
                                   "Run",
                                   "Channel",
                                   "channel_type",
                                   "data"
                                  ]
    metadata                   = pd.DataFrame(columns = metadata_columns)
    metadata.set_index("channel_path")

    
    channel_types = {'ex': 'electric', 'ey': 'electric',
                     'hx' : 'magnetic', 'hy' : 'magnetic', 'hz' : 'magnetic'}
    
    
    def channel_type(self, channel):
        return Sidebar.channel_types[channel]
    
    def h5pyify(files):
        #converts a list of filepaths into a list of h5py objects.
        Sidebar.h5py_objects = [h5py.File(file) for file in files]
        return Sidebar.h5py_objects
        
    def add_dataset_to_dict(key, value):
        if isinstance(value, h5py.Dataset):
            parts = key.split('/')
            if parts[1] == 'Stations':
                Sidebar.datasets[key] = {'data' : value,
                                         'Station': parts[-3],
                                         'Run': parts[-2],
                                         'Channel': parts[-1],
                                        }
            
    
    def add_dataset_to_dataframe(key, value):
        if isinstance(value, h5py.Dataset):
            parts = key.split('/')
            if parts[1] == 'Stations':
                Sidebar.metadata.loc[key] = [key, 
                                             #file.split('/')[-1], 
                                             #file,
                                             parts[-3],
                                             parts[-2],
                                             parts[-1],
                                             Sidebar.channel_type(part[-1]),
                                             value
                                             ]
                                         
                                         

    def convert_to_datasets(files):
        h5py_files = Sidebar.h5pyify(files) #Intake may handle this better
        for file in h5py_files:
            file.visititems(Sidebar.add_dataset_to_dict)
            #file.visititems(Sidebar.add_dataset_to_dataframe)
            
    def add_metadata(run):
        Sidebar.run_metadata[run] = run.split('/')
    
    @param.depends('file_selector', watch = True)
    def update_selected_files(self):
        Sidebar.convert_to_datasets(self.file_selector)
        self.param["selected_files"].objects = Sidebar.datasets.keys()
        self.metadata = Sidebar.metadata
        
        
    def make_TS_from_channel(self, file, channel_path):
        parts = channel_path.split('/')
        station = parts[-3]
        run = parts[-2]
        channel = parts[-1]
        data = np.array(Sidebar.datasets[channel_path]['data'])
        m = MTH5(file_version= '0.1.0')
        m.open_mth5(file, "r")
        channel_metadata = m.get_channel(station, run, channel).metadata
        run_metadata = m.get_run(station, run).metadata
        station_metadata = m.get_station(station).metadata
        m.close_mth5()
        time_series = mth5.timeseries.ChannelTS(channel_type = channel_typer(channel), data = data, channel_metadata = channel_metadata, run_metadata = run_metadata, station_metadata = station_metadata)
        return time_series
    
    def make_timeseries(self):
        for channel_path in self.selected_files:
            ts = Sidebar.make_TS_from_channel(self, self.file_selector[0], channel_path)
            #ts_slice = ts.get_slice(ts.start, n_samples = 256)
            #Sidebar.time_series.append(ts_slice)
            Sidebar.time_series.append(ts)
            Sidebar.x_arrays.append(ts.to_xarray())
    
    def plot_timeseries(self):
        for array in Sidebar.x_arrays:
            #built_in_plot = ts._ts.plot()
            plots.append(datashade(array.hvplot()))
            
    def make_and_plot_ts(self):
        Sidebar.make_timeseries(self)
        Sidebar.plot_timeseries(self)
    
    plot                       = param.Action(make_and_plot_ts)


# In[6]:


sidebar = Sidebar()
layout  = pn.Row(sidebar, plots).servable()
layout


# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:





# In[ ]:




