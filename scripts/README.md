# Scripts

The purpose of this folder is a collection of scripts for common use cases.
The scripts use the HARI client to access the API of HARI.
You can use the scripts in three major ways:
1. Execute the script directly with python. Please remember to add the `.env` to your working directory.
1. Use the defined functions in larger scripts
2. Take the code as inspiration for your personalised scripts.

Please be aware that this folder is currently under construction and may include outdated code.
We are working on including more use cases in the future.
Below you can find a description of the different available scripts.

## Available scripts

### Download & Analysis

- `download_data` Downloads the complete specified dataset for local analysis and caches the results locally
  - Call with: `python aint_analysis.py --dataset_id <Dataset ID> -c <Cache Directory>`
  - Example: `python aint_analysis.py --dataset_id 12345678-aaaa-bbbb-cccc-123456789de -c /path/to/cache`
- `aint_anaylsis` Download the specified subset of the desired datasets.
   On this dataset slice a comparison between the provided human and ai annotation run is calculated which includes accuracy, Kullback-leibler divergence between the two annotation runs.
   Moreover, the confidence thresholds for a specified quality and the confidence intervals are calculated.
  - Call with: `python aint_analysis.py --dataset_id <Dataset ID> —subset_id <Optional Subset ID> -c <Cache Directory> -ha <Name of human annotation run> -aa <ID of ai annotation run>`
  - Example: `python aint_analysis.py --dataset_id 12345678-aaaa-bbbb-cccc-123456789de —subset_id 12345678-aaaa-bbbb-cccc-123456789de -c /path/to/cache -ha name_annoation_run -aa 12345678-aaaa-bbbb-cccc-123456789de`

### Subsets

- `create_subsets_from_attribute.py` Creates subsets in a HARI dataset based on all aggregated values of an attribute.
  This can for example be used if a second nano task should only be executed on a specific aggregrated value of the previous task.
    - Call with: `python --dataset_id <Dataset ID> --attribute_id <Attribute ID> --prefix <PREFIX>`
    - Example: `python --dataset_id 12345678-aaaa-bbbb-cccc-123456789de --attribute_id 12345678-aaaa-bbbb-cccc-123456789de --prefix testing`


### AINT

- `get_aint_attribute_info` Get all linked AINT info for an AI annotation run attribute
  - Call with: `python get_aint_attribute_info.py --aint_attribute_id <Attribute ID: UUID>`
- `create_aint` Create and train an AI Nano Task (model). This also create the needed development sets.
  - Call with: `python create_aint.py --name <Name : str> --dataset_id <Dataset ID: UUID> --attribute_id <Attribute ID used for training: UUID> --user_group <Usergroup Name: str>`
- `apply_aint_generic` Apply a trained AI Nano Task model to a new dataset
  - Call with: `python apply_aint_generic.py --name <Name : str> --dataset_id <Dataset ID: UUID> --subset_id <Subset ID: UUID> --aint_model_id <Model ID: UUID> --user_group <Usergroup Name: str>`
- `apply_aint_on_test_data` Apply a trained AI Nano Task model to its associated test set. This can be used to do manual analysis on the test set.
  - Call with: `python apply_aint_on_test_data.py --name <Name : str> --aint_model_id <Model ID: UUID> --user_group <Usergroup Name: str>`
