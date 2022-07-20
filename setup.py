from setuptools import setup, find_packages
from itertools import chain
from typing import List, Dict

install_requires=[
    "bokeh",
    "param",
    "toolz",
    "cytoolz",
    "pendulum",
    "loguru",
    "panel",
    "h5py",
    "numpy",
    "polars",
    "pandas",
    "holoviews",
    "datashader",
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

