from .csv import CSVDataSource
from .synthetic import SyntheticDataSource

ParquetDataSource = None
H5DataSource = None
JSONDataSource = None

DATASOURCES = {
    'synthetic': SyntheticDataSource,
    'csv': CSVDataSource,
    'parquet': ParquetDataSource,
    'h5': H5DataSource,
    'json': JSONDataSource,
}
