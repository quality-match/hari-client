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

### Subsets

- `create_subsets_from_attribute.py` Creates subsets in a HARI dataset based on all aggregated values of an attribute.
  This can for example be used if a second nano task should only be executed on a specific aggregrated value of the previous task.
    - Call with: `python --dataset_id <Dataset ID> --attribute_id <Attribute ID> --prefix <PREFIX>`
    - Example: `python --dataset_id 12345678-aaaa-bbbb-cccc-123456789de --attribute_id 12345678-aaaa-bbbb-cccc-123456789de --prefix testing`


### AINT (AI Nano Tasks)

Currently only available to internal QM users.

- `get_aint_attribute_info` Get all linked AINT info for an AI annotation run attribute
  - Run with: `python get_aint_attribute_info.py --ml_attribute_id <Attribute ID: UUID>`
- `create_aint_model` Create and train an AI Nano Task model. This also creates the needed training set.
  - Run with: `python create_aint_model.py --name <Name : str> --dataset_id <Dataset ID: UUID> --attribute_id <Attribute ID: UUID> --subset_id <Subset ID(optional): UUID> --user_group <User Group Name: str>`
- `start_ai_annotation_run` Apply a trained AI Nano Task model to new data to run ai annotation and get model's predictions.
  - Run with: `python start_ai_annotation_run.py --name <Name : str> --dataset_id <Dataset ID: UUID> --subset_id <Subset ID: UUID> --aint_model_id <Model ID: UUID> --user_group <User Group Name: str>`
