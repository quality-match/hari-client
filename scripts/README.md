# Scripts

The purpose of this folder is a collection of scripts for common use cases.
The scripts use the HARI client to access the API of HARI.
You can use the scripts in three major ways:
1. Execute the script directly with python. Please remember to add the `.env` to your working directory.
2. Use the defined functions in larger scripts
3. Take the code as inspiration for your personalised scripts.

Please be aware that this folder is currently under construction and may include outdated code.
We are working on including more use cases in the future.
Below you can find a description of the different available scripts.

*How to find out your user group?*
This is the group your user is associated with. It is usually a project name we provide to you during setup. Please contact us if this information is not known.

## Available scripts

### Data Upload

- `upload_single_image` Shows how to upload a complete dataset in this script for one media
  - RUN with `python upload_single_image.py --dataset_name <Dataset Name> --image_url <URL> --user_group <USER_GROUP>`
- `upload_coco_like_dataset` Uploads a complete dataset in the MSCOCO Format
  - RUN with `python upload_coco_like_dataset.py --dataset_name <Dataset Name> --image_directory <Path> --annotations_file <Path> --user_group <USER_GROUP>`
- `upload_yolo_like_dataset` Uploads a complete dataset in the YOLO Format
  - RUN with `python upload_yolo_like_dataset.py --dataset_name <Dataset Name> --image_directory <Path> --labels_directory <Path> --classes_filename <Path> --user_group <USER_GROUP>`
- `upload_dataset_with_own_annotation_attributes` Uploads dataset with the user's own annotation attributes e.g. for training AINTs. This example makes up data during the upload and must be filled with your data.
  - RUN with `python upload_dataset_with_own_annotation_attributes.py --root_directory <Path> --source_dataset_name <Name> --target_dataset_name <Name> --question "<Question describing task> --attribute_name <Name of Attribute> --user_group <USER_GROUP>"`
- `trigger_metadata_rebuild` Triggers the dataset metadata rebuild that includes creating default visualizations for thumbnails and crops, updating the histograms for advanced filtering, etc.
  - RUN with `python trigger_metadata_rebuild.py --dataset_id <Dataset ID> --subset_id <Subset ID>`

### Subsets

- `create_subsets_from_attribute.py` Creates subsets in a HARI dataset based on all aggregated values of an attribute.
  This can for example be used if a second nano task should only be executed on a specific aggregrated value of the previous task.
    - Call with: `python create_subsets_from_attribute.py --dataset_id <Dataset ID> --attribute_id <Attribute ID> --prefix <PREFIX>`
    - Example: `python create_subsets_from_attribute.py --dataset_id 12345678-aaaa-bbbb-cccc-123456789de --attribute_id 12345678-aaaa-bbbb-cccc-123456789de --prefix testing`
