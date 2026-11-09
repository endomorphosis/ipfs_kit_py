"""
Data Science Integration Examples for IPFS FSSpec.

This module contains examples showing how to integrate IPFS with popular
data science libraries through the FSSpec interface.

Usage:
    python -m examples.data_science_examples

Requirements:
    - pandas
    - pyarrow
    - dask (optional)
    - scikit-learn (optional)
    - matplotlib (optional)
    - seaborn (optional)
"""

import os
import io
import time
import tempfile
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import json
from ipfs_kit_py.ipfs_kit import IPFSKit
import matplotlib.pyplot as plt

# Set to True to use a running IPFS daemon, False to use gateway only
USE_LOCAL_DAEMON = False

# Demo printing functions
def print_header(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80)

def print_subheader(title):
    """Print a subsection header."""
    print("\n" + "-" * 80)
    print(f" {title} ".center(80, "-"))
    print("-" * 80)

def print_step(step):
    """Print a step in the workflow."""
    print(f"\n>> {step}")


def create_sample_data():
    """Create sample datasets for demonstration."""
    print_step("Creating sample data...")
    
    # Create a basic DataFrame
    np.random.seed(42)  # For reproducibility
    n_samples = 1000
    
    data = {
        'id': np.arange(n_samples),
        'timestamp': pd.date_range(start='2023-01-01', periods=n_samples, freq='H'),
        'category': np.random.choice(['A', 'B', 'C', 'D'], size=n_samples),
        'value1': np.random.randn(n_samples),
        'value2': np.random.rand(n_samples) * 100,
        'flag': np.random.choice([True, False], size=n_samples)
    }
    
    df = pd.DataFrame(data)
    
    # Create some additional columns for analysis
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['value_sum'] = df['value1'] + df['value2']
    df['value_product'] = df['value1'] * df['value2']
    
    # Save to various formats
    with tempfile.TemporaryDirectory() as tmp_dir:
        # CSV
        csv_path = os.path.join(tmp_dir, "sample_data.csv")
        df.to_csv(csv_path, index=False)
        
        # Parquet
        parquet_path = os.path.join(tmp_dir, "sample_data.parquet")
        df.to_parquet(parquet_path, index=False)
        
        # JSON
        json_path = os.path.join(tmp_dir, "sample_data.json")
        df.to_json(json_path, orient='records', lines=True)
        
        # Feather
        feather_path = os.path.join(tmp_dir, "sample_data.feather")
        df.to_feather(feather_path)
        
        # Create multiple parquet files for partitioned dataset demo
        os.makedirs(os.path.join(tmp_dir, "partitioned"), exist_ok=True)
        for category in df['category'].unique():
            part_df = df[df['category'] == category]
            part_path = os.path.join(tmp_dir, "partitioned", f"category={category}.parquet")
            part_df.to_parquet(part_path, index=False)
        
        # Initialize IPFS
        if USE_LOCAL_DAEMON:
            kit = IPFSKit()
            fs = kit.get_filesystem(use_gateway_fallback=True)
        else:
            kit = IPFSKit()
            fs = kit.get_filesystem(
                gateway_only=True,
                gateway_urls=[
                    "https://ipfs.io/ipfs/",
                    "https://gateway.pinata.cloud/ipfs/"
                ]
            )
        
        # Add files to IPFS
        print_step("Adding sample data to IPFS...")
        csv_cid = kit.ipfs_add_file(csv_path)["Hash"]
        print(f"CSV CID: {csv_cid}")
        
        parquet_cid = kit.ipfs_add_file(parquet_path)["Hash"]
        print(f"Parquet CID: {parquet_cid}")
        
        json_cid = kit.ipfs_add_file(json_path)["Hash"]
        print(f"JSON CID: {json_cid}")
        
        feather_cid = kit.ipfs_add_file(feather_path)["Hash"]
        print(f"Feather CID: {feather_cid}")
        
        # Add partitioned dataset
        partitioned_cid = kit.ipfs_add_path(os.path.join(tmp_dir, "partitioned"))["Hash"]
        print(f"Partitioned Dataset CID: {partitioned_cid}")
        
        # Return the CIDs and filesystem for further examples
        return {
            'csv_cid': csv_cid,
            'parquet_cid': parquet_cid,
            'json_cid': json_cid,
            'feather_cid': feather_cid,
            'partitioned_cid': partitioned_cid,
            'fs': fs,
            'kit': kit,
            'df': df  # Original DataFrame for comparison
        }


def pandas_examples(resources):
    """Examples of using pandas with IPFS."""
    print_header("PANDAS INTEGRATION EXAMPLES")
    fs = resources['fs']
    
    # Example 1: Read CSV from IPFS
    print_subheader("Reading CSV from IPFS")
    csv_path = f"ipfs://{resources['csv_cid']}"
    start_time = time.time()
    df_csv = pd.read_csv(csv_path, storage_options={'fs': fs})
    csv_time = time.time() - start_time
    
    print(f"Read {len(df_csv)} rows from CSV in {csv_time:.4f} seconds")
    print("\nFirst 5 rows:")
    print(df_csv.head())
    print("\nDataFrame info:")
    buffer = io.StringIO()
    df_csv.info(buf=buffer)
    print(buffer.getvalue())
    
    # Example 2: Read Parquet from IPFS
    print_subheader("Reading Parquet from IPFS")
    parquet_path = f"ipfs://{resources['parquet_cid']}"
    start_time = time.time()
    df_parquet = pd.read_parquet(parquet_path, storage_options={'fs': fs})
    parquet_time = time.time() - start_time
    
    print(f"Read {len(df_parquet)} rows from Parquet in {parquet_time:.4f} seconds")
    print(f"Performance comparison: Parquet is {csv_time/parquet_time:.2f}x faster than CSV")
    
    # Example 3: Read JSON from IPFS
    print_subheader("Reading JSON from IPFS")
    json_path = f"ipfs://{resources['json_cid']}"
    try:
        df_json = pd.read_json(json_path, lines=True, storage_options={'fs': fs})
        print(f"Successfully read {len(df_json)} rows from JSON")
    except Exception as e:
        print(f"Error reading JSON: {e}")
        # Alternative approach for JSON
        with fs.open(json_path, 'r') as f:
            json_data = [json.loads(line) for line in f]
        df_json = pd.DataFrame(json_data)
        print(f"Successfully read {len(df_json)} rows from JSON using alternative method")
    
    # Example 4: Read Feather from IPFS
    print_subheader("Reading Feather from IPFS")
    feather_path = f"ipfs://{resources['feather_cid']}"
    try:
        start_time = time.time()
        df_feather = pd.read_feather(feather_path, storage_options={'fs': fs})
        feather_time = time.time() - start_time
        
        print(f"Read {len(df_feather)} rows from Feather in {feather_time:.4f} seconds")
        print(f"Performance comparison:")
        print(f"- Feather is {csv_time/feather_time:.2f}x faster than CSV")
        print(f"- Feather is {parquet_time/feather_time:.2f}x faster than Parquet")
    except Exception as e:
        print(f"Error reading Feather: {e}")
    
    # Example 5: Perform typical pandas operations
    print_subheader("Performing pandas operations")
    
    # Group by analysis
    print_step("Group by analysis")
    grouped = df_parquet.groupby('category').agg({
        'value1': ['mean', 'std', 'min', 'max'],
        'value2': ['mean', 'std', 'min', 'max'],
        'id': 'count'
    })
    print(grouped)
    
    # Time series resampling
    print_step("Time series resampling")
    ts_data = df_parquet.set_index('timestamp')
    daily = ts_data['value1'].resample('D').mean()
    print(daily.head())
    
    # DataFrame transformation
    print_step("DataFrame transformation")
    df_transformed = df_parquet.copy()
    df_transformed['value1_normalized'] = (df_transformed['value1'] - df_transformed['value1'].mean()) / df_transformed['value1'].std()
    df_transformed['value2_log'] = np.log1p(df_transformed['value2'])
    print(df_transformed[['value1', 'value1_normalized', 'value2', 'value2_log']].head())
    
    # Create temporary file for the transformed data
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
        tmp_path = tmp.name
    
    # Save the transformed data
    df_transformed.to_parquet(tmp_path)
    
    # Add to IPFS
    print_step("Adding transformed data to IPFS")
    transformed_cid = resources['kit'].ipfs_add_file(tmp_path)["Hash"]
    print(f"Transformed data CID: {transformed_cid}")
    
    # Clean up
    os.unlink(tmp_path)
    
    return transformed_cid


def pyarrow_examples(resources):
    """Examples of using PyArrow with IPFS."""
    print_header("PYARROW INTEGRATION EXAMPLES")
    fs = resources['fs']
    
    # Example 1: Read Parquet directly with PyArrow
    print_subheader("Reading Parquet with PyArrow")
    parquet_path = f"ipfs://{resources['parquet_cid']}"
    
    start_time = time.time()
    with fs.open(parquet_path, 'rb') as f:
        table = pq.read_table(f)
    arrow_time = time.time() - start_time
    
    print(f"Read PyArrow table with {table.num_rows} rows in {arrow_time:.4f} seconds")
    print("\nTable schema:")
    print(table.schema)
    
    # Example 2: PyArrow compute functions
    print_subheader("PyArrow compute functions")
    
    # Calculate statistics directly on Arrow data
    print_step("Calculating statistics on Arrow columns")
    numeric_col = table.column('value1')
    
    stats = {
        'min': pa.compute.min(numeric_col).as_py(),
        'max': pa.compute.max(numeric_col).as_py(),
        'mean': pa.compute.mean(numeric_col).as_py(),
        'sum': pa.compute.sum(numeric_col).as_py(),
        'std': pa.compute.stddev(numeric_col).as_py(),
        'var': pa.compute.variance(numeric_col).as_py()
    }
    
    print(json.dumps(stats, indent=2))
    
    # Example 3: Filtering with PyArrow compute
    print_subheader("Filtering with PyArrow compute")
    
    # Create a filter for value1 > 0
    filter_expr = pa.compute.greater(table.column('value1'), 0)
    filtered_indices = pa.compute.filter(pa.array(range(table.num_rows)), filter_expr)
    filtered_table = table.take(filtered_indices)
    
    print(f"Original table: {table.num_rows} rows")
    print(f"Filtered table (value1 > 0): {filtered_table.num_rows} rows")
    
    # Example 4: Convert to pandas for further processing
    print_subheader("Converting to pandas")
    
    start_time = time.time()
    df = filtered_table.to_pandas()
    convert_time = time.time() - start_time
    
    print(f"Converted to pandas DataFrame in {convert_time:.4f} seconds")
    print("\nPandas DataFrame:")
    print(df.head())
    
    return table


def visualization_examples(resources, df_pandas, arrow_table=None):
    """Examples of creating visualizations from IPFS data."""
    print_header("VISUALIZATION EXAMPLES")
    
    # Check if matplotlib is available
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        has_viz = True
    except ImportError:
        print("Matplotlib or Seaborn not available. Skipping visualization examples.")
        has_viz = False
        return
    
    if not has_viz:
        return
    
    # Set the style
    sns.set(style="whitegrid")
    
    # Example 1: Basic distribution plot
    print_subheader("Distribution Plot")
    plt.figure(figsize=(10, 6))
    sns.histplot(df_pandas['value1'], kde=True)
    plt.title('Distribution of value1')
    plt.tight_layout()
    
    # Create temporary file for the plot
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    # Save the plot
    plt.savefig(tmp_path)
    plt.close()
    
    # Add to IPFS
    print_step("Adding visualization to IPFS")
    viz_cid = resources['kit'].ipfs_add_file(tmp_path)["Hash"]
    print(f"Visualization CID: {viz_cid}")
    print(f"View at: https://ipfs.io/ipfs/{viz_cid}")
    
    # Clean up
    os.unlink(tmp_path)
    
    # Example 2: Categorical plot
    print_subheader("Categorical Plot")
    plt.figure(figsize=(12, 6))
    sns.boxplot(x='category', y='value1', data=df_pandas)
    plt.title('value1 by Category')
    plt.tight_layout()
    
    # Create temporary file for the plot
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    # Save the plot
    plt.savefig(tmp_path)
    plt.close()
    
    # Add to IPFS
    print_step("Adding categorical visualization to IPFS")
    cat_viz_cid = resources['kit'].ipfs_add_file(tmp_path)["Hash"]
    print(f"Categorical visualization CID: {cat_viz_cid}")
    print(f"View at: https://ipfs.io/ipfs/{cat_viz_cid}")
    
    # Clean up
    os.unlink(tmp_path)
    
    # Example 3: Time series plot
    print_subheader("Time Series Plot")
    ts_data = df_pandas.set_index('timestamp')
    plt.figure(figsize=(14, 6))
    daily = ts_data['value1'].resample('D').mean()
    daily.plot()
    plt.title('Daily Average of value1')
    plt.tight_layout()
    
    # Create temporary file for the plot
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    # Save the plot
    plt.savefig(tmp_path)
    plt.close()
    
    # Add to IPFS
    print_step("Adding time series visualization to IPFS")
    ts_viz_cid = resources['kit'].ipfs_add_file(tmp_path)["Hash"]
    print(f"Time series visualization CID: {ts_viz_cid}")
    print(f"View at: https://ipfs.io/ipfs/{ts_viz_cid}")
    
    # Clean up
    os.unlink(tmp_path)
    
    return [viz_cid, cat_viz_cid, ts_viz_cid]


def machine_learning_examples(resources, df_pandas):
    """Examples of machine learning with data from IPFS."""
    print_header("MACHINE LEARNING EXAMPLES")
    
    # Check if scikit-learn is available
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_squared_error, r2_score
        import joblib
        has_sklearn = True
    except ImportError:
        print("Scikit-learn not available. Skipping machine learning examples.")
        has_sklearn = False
        return
    
    if not has_sklearn:
        return
    
    # Example 1: Prepare data for machine learning
    print_subheader("Preparing data for ML")
    
    # Create a regression task to predict value1 from other features
    print_step("Creating features and target")
    
    # Select features and target
    features = ['value2', 'hour', 'id']
    target = 'value1'
    
    # Prepare data
    X = df_pandas[features]
    y = df_pandas[target]
    
    # Add categorical features via one-hot encoding
    X = pd.get_dummies(df_pandas, columns=['category'], prefix=['cat'])
    
    # Drop unnecessary columns
    X = X.drop(columns=['timestamp', 'date', 'value1', 'value_sum', 'value_product', 'flag'])
    
    print(f"Features shape: {X.shape}")
    print(f"Target shape: {y.shape}")
    print("\nFeature columns:")
    print(X.columns.tolist())
    
    # Example 2: Split data and train a model
    print_subheader("Training a RandomForestRegressor")
    
    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"Training set: {X_train.shape[0]} samples")
    print(f"Test set: {X_test.shape[0]} samples")
    
    # Train a random forest regressor
    print_step("Training model")
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    
    start_time = time.time()
    model.fit(X_train, y_train)
    train_time = time.time() - start_time
    
    print(f"Model trained in {train_time:.4f} seconds")
    
    # Evaluate the model
    print_step("Evaluating model")
    y_pred = model.predict(X_test)
    
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    print(f"Mean Squared Error: {mse:.4f}")
    print(f"R² Score: {r2:.4f}")
    
    # Example 3: Save model to IPFS
    print_subheader("Saving model to IPFS")
    
    # Create temporary file for the model
    with tempfile.NamedTemporaryFile(suffix='.joblib', delete=False) as tmp:
        tmp_path = tmp.name
    
    # Save the model
    joblib.dump(model, tmp_path)
    
    # Add to IPFS
    model_cid = resources['kit'].ipfs_add_file(tmp_path)["Hash"]
    print(f"Model CID: {model_cid}")
    
    # Clean up
    os.unlink(tmp_path)
    
    # Example 4: Load model from IPFS and make predictions
    print_subheader("Loading model from IPFS and making predictions")
    
    fs = resources['fs']
    model_path = f"ipfs://{model_cid}"
    
    # Load the model
    with fs.open(model_path, 'rb') as f:
        loaded_model = joblib.load(f)
    
    print("Model loaded successfully")
    
    # Make predictions with loaded model
    y_pred_loaded = loaded_model.predict(X_test)
    
    # Verify predictions match
    pred_match = np.allclose(y_pred, y_pred_loaded)
    print(f"Predictions from loaded model match original: {pred_match}")
    
    # Feature importance
    print_step("Feature importance")
    importance = pd.DataFrame({
        'Feature': X.columns,
        'Importance': loaded_model.feature_importances_
    }).sort_values('Importance', ascending=False)
    
    print(importance.head(10))
    
    return model_cid


def dask_examples(resources):
    """Examples of using Dask with IPFS."""
    print_header("DASK INTEGRATION EXAMPLES")
    
    # Check if dask is available
    try:
        import dask.dataframe as dd
        has_dask = True
    except ImportError:
        print("Dask not available. Skipping Dask examples.")
        has_dask = False
        return
    
    if not has_dask:
        return
    
    fs = resources['fs']
    parquet_path = f"ipfs://{resources['parquet_cid']}"
    partitioned_path = f"ipfs://{resources['partitioned_cid']}"
    
    # Example 1: Read a single Parquet file with Dask
    print_subheader("Reading a single Parquet file with Dask")
    
    start_time = time.time()
    ddf = dd.read_parquet(parquet_path, storage_options={'fs': fs})
    read_time = time.time() - start_time
    
    print(f"Read Dask DataFrame from Parquet in {read_time:.4f} seconds")
    print(f"Dask DataFrame divisions: {ddf.divisions}")
    print(f"Dask DataFrame dtypes:")
    print(ddf.dtypes)
    
    # Example 2: Lazy computation with Dask
    print_subheader("Lazy computation with Dask")
    
    print_step("Defining computation")
    # Define a computation (not executed yet)
    result = ddf.groupby('category')['value1'].mean()
    
    print("Computation graph created but not executed")
    
    # Trigger computation
    print_step("Executing computation")
    start_time = time.time()
    computed_result = result.compute()
    compute_time = time.time() - start_time
    
    print(f"Computation completed in {compute_time:.4f} seconds")
    print("Result:")
    print(computed_result)
    
    # Example 3: Working with partitioned data
    print_subheader("Working with partitioned data")
    
    # This example would work with actual partitioned data in IPFS
    # For simplicity, we're reusing the same parquet file
    try:
        print_step("Reading partitioned dataset")
        part_ddf = dd.read_parquet(
            partitioned_path + "/*.parquet",
            storage_options={'fs': fs}
        )
        
        print(f"Partitioned Dask DataFrame divisions: {part_ddf.divisions}")
        print(f"Partitioned Dask DataFrame dtypes:")
        print(part_ddf.dtypes)
        
        # Perform computation on partitioned data
        print_step("Computing on partitioned data")
        part_result = part_ddf.groupby('category')['value1'].mean().compute()
        print("Result from partitioned data:")
        print(part_result)
    except Exception as e:
        print(f"Error with partitioned data: {e}")
        print("Note: This example requires a properly partitioned dataset in IPFS")
    
    return computed_result.to_dict()


def full_workflow_example(resources):
    """A complete data science workflow example using IPFS."""
    print_header("COMPLETE DATA SCIENCE WORKFLOW EXAMPLE")
    
    fs = resources['fs']
    kit = resources['kit']
    
    # Step 1: Load data from IPFS
    print_subheader("Step 1: Load data from IPFS")
    parquet_path = f"ipfs://{resources['parquet_cid']}"
    
    df = pd.read_parquet(parquet_path, storage_options={'fs': fs})
    print(f"Loaded dataset with {len(df)} rows and {len(df.columns)} columns")
    
    # Step 2: Exploratory Data Analysis
    print_subheader("Step 2: Exploratory Data Analysis")
    
    # Summary statistics
    print_step("Summary statistics")
    print(df.describe())
    
    # Category distribution
    print_step("Category distribution")
    category_counts = df['category'].value_counts()
    print(category_counts)
    
    # Correlation analysis
    print_step("Correlation analysis")
    numeric_cols = df.select_dtypes(include=['number'])
    corr = numeric_cols.corr()
    print(corr)
    
    # Step 3: Feature Engineering
    print_subheader("Step 3: Feature Engineering")
    
    df_processed = df.copy()
    
    # Time-based features
    print_step("Creating time-based features")
    df_processed['dayofweek'] = df_processed['timestamp'].dt.dayofweek
    df_processed['month'] = df_processed['timestamp'].dt.month
    df_processed['is_weekend'] = df_processed['dayofweek'].isin([5, 6])
    
    # Derived numeric features
    print_step("Creating derived numeric features")
    df_processed['value_ratio'] = df_processed['value1'] / df_processed['value2'].where(df_processed['value2'] != 0, 1)
    df_processed['value1_zscore'] = (df_processed['value1'] - df_processed['value1'].mean()) / df_processed['value1'].std()
    df_processed['value2_log'] = np.log1p(np.abs(df_processed['value2']))
    
    # Categorical encodings
    print_step("Encoding categorical features")
    df_processed = pd.get_dummies(df_processed, columns=['category'], prefix='cat')
    
    print(f"Processed dataframe has {len(df_processed.columns)} columns")
    print("New columns:")
    new_cols = set(df_processed.columns) - set(df.columns)
    print(sorted(list(new_cols)))
    
    # Step 4: Save processed data to IPFS
    print_subheader("Step 4: Save processed data to IPFS")
    
    # Save to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp:
        tmp_path = tmp.name
    
    df_processed.to_parquet(tmp_path)
    
    # Add to IPFS
    processed_cid = kit.ipfs_add_file(tmp_path)["Hash"]
    print(f"Processed data CID: {processed_cid}")
    
    # Clean up
    os.unlink(tmp_path)
    
    # Step 5: Modeling
    print_subheader("Step 5: Modeling")
    
    try:
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import mean_squared_error, r2_score
        has_sklearn = True
    except ImportError:
        print("Scikit-learn not available. Skipping modeling steps.")
        has_sklearn = False
    
    if has_sklearn:
        # Prepare data for modeling
        print_step("Preparing modeling data")
        
        # Target variable
        target = 'value1'
        
        # Features (exclude target, timestamp, and date)
        features = df_processed.columns.tolist()
        features.remove(target)
        features.remove('timestamp')
        features.remove('date')
        
        X = df_processed[features]
        y = df_processed[target]
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        print(f"Training set: {X_train.shape[0]} samples, {X_train.shape[1]} features")
        print(f"Test set: {X_test.shape[0]} samples")
        
        # Train multiple models
        print_step("Training multiple models")
        
        models = {
            "Linear Regression": LinearRegression(),
            "Random Forest": RandomForestRegressor(n_estimators=100, random_state=42),
            "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, random_state=42)
        }
        
        results = {}
        
        for name, model in models.items():
            print(f"Training {name}...")
            model.fit(X_train, y_train)
            
            # Evaluate
            y_pred = model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)
            
            results[name] = {
                'MSE': mse,
                'R2': r2,
                'model': model
            }
            
            print(f"  MSE: {mse:.4f}")
            print(f"  R²: {r2:.4f}")
        
        # Choose best model
        print_step("Selecting best model")
        best_model_name = min(results, key=lambda k: results[k]['MSE'])
        best_model = results[best_model_name]['model']
        
        print(f"Best model: {best_model_name}")
        print(f"MSE: {results[best_model_name]['MSE']:.4f}")
        print(f"R²: {results[best_model_name]['R2']:.4f}")
        
        # Save best model to IPFS
        print_step("Saving best model to IPFS")
        
        # Save to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.joblib', delete=False) as tmp:
            tmp_path = tmp.name
        
        import joblib
        joblib.dump(best_model, tmp_path)
        
        # Add to IPFS
        model_cid = kit.ipfs_add_file(tmp_path)["Hash"]
        print(f"Best model CID: {model_cid}")
        
        # Clean up
        os.unlink(tmp_path)
        
        # Step 6: Make predictions with model loaded from IPFS
        print_subheader("Step 6: Make predictions with model from IPFS")
        
        # Load model from IPFS
        print_step("Loading model from IPFS")
        model_path = f"ipfs://{model_cid}"
        
        with fs.open(model_path, 'rb') as f:
            loaded_model = joblib.load(f)
        
        print("Model loaded successfully")
        
        # Make predictions
        print_step("Making predictions on test data")
        y_pred = loaded_model.predict(X_test)
        
        # Create prediction dataframe
        pred_df = pd.DataFrame({
            'actual': y_test,
            'predicted': y_pred,
            'error': y_test - y_pred
        })
        
        print("Prediction summary:")
        print(pred_df.describe())
        
        # Save predictions to IPFS
        print_step("Saving predictions to IPFS")
        
        # Save to a temporary file
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
            tmp_path = tmp.name
        
        pred_df.to_csv(tmp_path, index=True)
        
        # Add to IPFS
        preds_cid = kit.ipfs_add_file(tmp_path)["Hash"]
        print(f"Predictions CID: {preds_cid}")
        
        # Clean up
        os.unlink(tmp_path)
        
        # Step 7: Visualize results
        print_subheader("Step 7: Visualize results")
        
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            has_viz = True
        except ImportError:
            print("Matplotlib or Seaborn not available. Skipping visualization.")
            has_viz = False
        
        if has_viz:
            # Create visualizations
            print_step("Creating visualizations")
            
            # Scatter plot of actual vs predicted
            plt.figure(figsize=(10, 6))
            plt.scatter(y_test, y_pred, alpha=0.5)
            plt.plot([y_test.min(), y_test.max()], [y_test.min(), y_test.max()], 'k--')
            plt.xlabel('Actual')
            plt.ylabel('Predicted')
            plt.title('Actual vs Predicted Values')
            plt.tight_layout()
            
            # Save to a temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
            
            plt.savefig(tmp_path)
            plt.close()
            
            # Add to IPFS
            viz_cid = kit.ipfs_add_file(tmp_path)["Hash"]
            print(f"Visualization CID: {viz_cid}")
            print(f"View at: https://ipfs.io/ipfs/{viz_cid}")
            
            # Clean up
            os.unlink(tmp_path)
    
    # Step 8: Create a report and save to IPFS
    print_subheader("Step 8: Create a report and save to IPFS")
    
    # Create a markdown report
    report = f"""# Data Science Workflow Report

## Dataset Overview
- Original CID: {resources['parquet_cid']}
- Number of samples: {len(df)}
- Number of features: {len(df.columns)}
- Categories: {', '.join(sorted(df['category'].unique()))}

## Processed Dataset
- Processed CID: {processed_cid}
- Number of features after processing: {len(df_processed.columns)}

## EDA Results
- Category distribution:
```
{category_counts.to_string()}
```

- Correlation between value1 and value2: {corr.loc['value1', 'value2']:.4f}

"""
    
    if has_sklearn:
        report += f"""
## Modeling Results
- Best model: {best_model_name}
- Model CID: {model_cid}
- MSE: {results[best_model_name]['MSE']:.4f}
- R²: {results[best_model_name]['R2']:.4f}
- Predictions CID: {preds_cid}

"""
    
    if has_viz:
        report += f"""
## Visualizations
- Actual vs Predicted: [View on IPFS Gateway](https://ipfs.io/ipfs/{viz_cid})

"""
    
    report += f"""
## Workflow Summary
This report was generated from a complete data science workflow using IPFS for data storage
and retrieval. The workflow demonstrates how to use IPFS with pandas, PyArrow, 
scikit-learn, and matplotlib/seaborn for a full data science pipeline.

Report generated at: {pd.Timestamp.now()}
"""
    
    # Save the report to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as tmp:
        tmp_path = tmp.name
    
    with open(tmp_path, 'w') as f:
        f.write(report)
    
    # Add to IPFS
    report_cid = kit.ipfs_add_file(tmp_path)["Hash"]
    print(f"Report CID: {report_cid}")
    print(f"View report at: https://ipfs.io/ipfs/{report_cid}")
    
    # Clean up
    os.unlink(tmp_path)
    
    return {
        'processed_cid': processed_cid,
        'model_cid': model_cid if has_sklearn else None,
        'report_cid': report_cid
    }


def main():
    """Main function to run all examples."""
    print_header("IPFS FSSPEC DATA SCIENCE INTEGRATION EXAMPLES")
    
    # Create sample data and store in IPFS
    resources = create_sample_data()
    
    # Pandas examples
    transformed_cid = pandas_examples(resources)
    
    # PyArrow examples
    arrow_table = pyarrow_examples(resources)
    
    # Visualization examples
    viz_cids = visualization_examples(resources, resources['df'], arrow_table)
    
    # Machine learning examples
    model_cid = machine_learning_examples(resources, resources['df'])
    
    # Dask examples
    dask_results = dask_examples(resources)
    
    # Full workflow example
    workflow_results = full_workflow_example(resources)
    
    print_header("SUMMARY OF EXAMPLES")
    print(f"Original data CIDs:")
    print(f"- CSV: {resources['csv_cid']}")
    print(f"- Parquet: {resources['parquet_cid']}")
    print(f"- JSON: {resources['json_cid']}")
    print(f"- Feather: {resources['feather_cid']}")
    
    print(f"\nTransformed data CID: {transformed_cid}")
    
    if viz_cids:
        print(f"\nVisualization CIDs:")
        for i, cid in enumerate(viz_cids):
            print(f"- Visualization {i+1}: {cid}")
    
    if model_cid:
        print(f"\nMachine learning model CID: {model_cid}")
    
    if workflow_results:
        print(f"\nFull workflow results:")
        print(f"- Processed data CID: {workflow_results['processed_cid']}")
        if workflow_results['model_cid']:
            print(f"- Best model CID: {workflow_results['model_cid']}")
        print(f"- Report CID: {workflow_results['report_cid']}")
        print(f"- View report at: https://ipfs.io/ipfs/{workflow_results['report_cid']}")


if __name__ == "__main__":
    main()