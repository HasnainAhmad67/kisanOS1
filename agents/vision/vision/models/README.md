# Where the self-hosted vision model goes

The Vision Agent has NO built-in model and NO cloud fallback. Put an open-source wheat image classifier,
exported to ONNX, in  models/wheat_vision/  (or point VISION_MODEL_DIR at another folder):

    models/wheat_vision/
        model.onnx                 REQUIRED  the classifier
        label_map.json             REQUIRED  model label -> agent class   (copy label_map.example.json)
        config.json                REQUIRED* {"id2label": {"0": "healthy", ...}}  (*or labels.txt, or "labels" in label_map.json)
        preprocessor_config.json   optional  Hugging Face style: size, crop_size, image_mean, image_std
        model_card.json            recommended  name, url, publisher, license, source_status (copy model_card.example.json)

Until these files exist the agent answers "unavailable" (flag model_not_available). It never shows an example result.

## Getting an open-source model (do this once, on a machine with internet)
1. Pick a wheat disease classifier whose license you can use, e.g. a Hugging Face model with healthy / yellow rust /
   brown rust labels. Check its model card: training data (is it field photos? which country?), license, labels.
2. Export to ONNX. For a Hugging Face transformers image-classification model:
       pip install "optimum[onnxruntime]"
       optimum-cli export onnx --model <hf-model-id> --task image-classification models/wheat_vision
   (this writes model.onnx, config.json and preprocessor_config.json). For timm / fastai / PyTorch models use
   torch.onnx.export with an input named like the model expects (one 1x3xHxW float image, one row of scores out).
3. Copy label_map.example.json to label_map.json and edit the left-hand side to the model's REAL label names
   (see config.json). Allowed classes on the right: healthy_looking, yellowing, rust_like_pustules,
   spots_or_blotches, visible_insects, drying, unclear.
4. Copy model_card.example.json to model_card.json and fill it in (the url becomes the model's entry in `sources`).
5. Run:  python -m agents.vision.check_model  your_photo.jpg   and read the labels and scores.

Note: these steps were not run by the person who wrote this agent (the build environment could not download model
weights). Accuracy of whichever model you choose is NOT verified here - test it on real photos first.
