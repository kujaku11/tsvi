import holoviews as hv
import hvplot
import panel as pn
import numpy as np

import h5py
from mth5.mth5 import MTH5


def cpu_usage_widget():
    cpu_usage = pn.indicators.Number(
        name="CPU",
        value=0,
        format="{value}%",
        colors=[(50, "green"), (75, "orange"), (100, "red")],
        font_size="13pt",
        title_size="8pt",
        width=50,
    )
    return cpu_usage


def memory_usage_widget():
    memory_usage = pn.indicators.Number(
        name="Memory",
        value=0,
        format="{value}%",
        colors=[(50, "green"), (75, "orange"), (100, "red")],
        font_size="13pt",
        title_size="8pt",
        width=50,
    )
    return memory_usage


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


def invert(event, data):
    data = -1 * data
    return data

    # def get_card_controls():
    # THe idea here is to track the buttons /widgets that we want beside the plot
    #     annotate_button = pn.widgets.Button(name = "Annotate", button_type = "primary", width = 100)
    #     invert_button = pn.widgets.Button(name = "Invert", button_type = "primary", width = 100)
    #     # def invert(self, *args, **params):
    #     #   data = -1 * data
    #     # invert_button.on_click(invert(event, data))
    #     controls = pn.Column(annotate_button,
    #                          invert_button,
    #                          sizing_mode = "fixed", width = 200,)
    #     return controls
