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

*How to find out your user group?*
This is the group your users is associated with. It is usually a project name we provide to you during setup. Please contact us if this information is not known.

## Available scripts

### Upload


- `upload_generic_dataset` Shows how to upload a complete dataset in this script for one media
  - Call with `python upload_generic_dataset.py --dataset_name <Dataset Name> --image_url <URL> --user_group <USER_GROUP>`
  - Example: `python upload_generic_dataset.py --dataset_name MyTestDataset --image_url https://cdn.prod.website-files.com/650ac10b593e0cfe15061ca9/65562bc58364e8a5e4de4479_H41-p-800.png --user_group USER`
- `upload_coco_like_dataset` Uploads a complete dataset in the MSCOCO Format
  -  Call with `python upload_coco_like_dataset.py --dataset_name <Dataset Name> --image_directory <Path> --annotations_file <Path> --user_group <USER_GROUP>`
  - Example: `python upload_coco_like_dataset.py --dataset_name ms_coco_2017_val --image_directory /Path/to/my/data/mscoco/val2017 --annotations_file /Path/to/my/data/mscoco/annotations/instances_val2017.json --user_group USER`
- `upload_dataset_with_own_attributes` Uploads a complete dataset with own annotation attributes e.g. for training AINTs. This example makes up data during the upload and must be filled with your data.
  - Call with `python upload_dataset_with_own_attributes.py --root_directory <Path> --source_dataset_name <Name> --question "<Question describing task> --attribute_name <Name of Attribute> --user_group <USER_GROUP>"`
  - Example: `python upload_dataset_with_own_attributes.py --root_directory /Path/to/my/data --source_dataset_name Quality --question "How is the quality of the image?" --attribute_name image_quality --user_group USER`
- `trigger_metadata_rebuild` Triggers the metadata rebuild like crop generation, missing thumbnails, wrong histogram calculations.
  - Call with `python trigger_metadata_rebuild.py --dataset_id <Dataset ID> --subset_id <Attribute ID>`
  - Example: `python trigger_metadata_rebuild.py --dataset_id 12345678-aaaa-bbbb-cccc-123456789de --subset_id 12345678-aaaa-bbbb-cccc-123456789de`



### Subsets

- `create_subsets_from_attribute.py` Creates subsets in a HARI dataset based on all aggregated values of an attribute.
  This can for example be used if a second nano task should only be executed on a specific aggregrated value of the previous task.
    - Call with: `python create_subsets_from_attribute.py --dataset_id <Dataset ID> --attribute_id <Attribute ID> --prefix <PREFIX>`
    - Example: `python create_subsets_from_attribute.py --dataset_id 12345678-aaaa-bbbb-cccc-123456789de --attribute_id 12345678-aaaa-bbbb-cccc-123456789de --prefix testing`
