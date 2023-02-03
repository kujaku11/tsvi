from setuptools import setup, find_packages
from itertools import chain
from typing import List, Dict

install_requires=[
    "bokeh",
    "cytoolz",
    "datashader",
    "holoviews",
    "hvplot",
    "h5py",
    "loguru",
    "numpy",
    "pandas",
    "panel",
    "param",
    "pendulum",
    "polars",
    "psutil",
    "toolz",
    "mth5",
    "mt_metadata"
]

extras_require: Dict[str, List[str]] = {
}

extras_require['all'] = list(chain(*extras_require.values()))


setup(
    name = "tsvi",
    version = "0.0.1",
    author = "",
    author_email = "brunorpinho10@gmail.com",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires=">=3.9",
    # long_description=read('README'),
)

