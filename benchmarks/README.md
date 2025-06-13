# Benchmarks

## Using the benchmarks script

To run the benchmarks, you can use the `benchmark.py` script.
Specify the parameters to the script as follows:
- REUSE_PREVIOUS_CONFIGURATION
  - This is used to populate the remaining parameters with the values from the previous run taken from the latest config in [results](results).

- REUSE_SAME_MEDIA_BINARY = True
  - if True, the same media binary will be used for all medias
- NUM_MEDIAS = 2
  - how many medias should be created
- NUM_MEDIA_OBJECTS_BY_MEDIA = 2
  - how many media objects should be created for each media
- NUM_ATTRIBUTES_BY_MEDIA = 10
  - how many attributes should be created for each media
- NUM_ATTRIBUTES_BY_MEDIA_OBJECT = 2
  - how many attributes should be created for each media object


For example, to run the benchmarks with x media and y attributes, you can use the following command:

## Adding new benchmarks

After running the benchmark-script, the results are stored in the `user_results` folder, which is not tracked by git.
If you want to add new benchmarks, you can move a/some result(s) from the `user_results` folder to the `results` folder.
